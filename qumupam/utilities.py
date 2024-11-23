#!/usr/bin/env python3

from io import BytesIO
from pathlib import Path
import platform
import re
import stat
from subprocess import CalledProcessError, check_output, DEVNULL
from enum import Enum
import sys
from typing import Iterable, NamedTuple, Optional
import inquirer as inq
from tempfile import TemporaryDirectory
import urllib.request
from tqdm import tqdm
from cachier import cachier
import zipfile


AAPT2_PATH_ON_DEVICE = "/data/local/tmp/aapt2"
ADB_URL_WINDOWS = (
    "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
)
ADB_URL_LINUX = (
    "https://dl.google.com/android/repository/platform-tools-latest-linux.zip"
)
ADB_URL_MAC = (
    "https://dl.google.com/android/repository/platform-tools-latest-darwin.zip"
)


def get_adb_url():
    if platform.system() == "Windows":
        return ADB_URL_WINDOWS
    elif platform.system() == "Linux":
        return ADB_URL_LINUX
    elif platform.system() == "Darwin":
        return ADB_URL_MAC
    else:
        raise NotImplementedError(f"No ADB for system {platform.system()}")


ADB_FOLDER = Path.home() / ".cache" / "qumupam-adb"
ADB_PATH = ADB_FOLDER / "platform-tools" / "adb"


if platform.system() == "Windows":
    ADB_PATH = ADB_PATH.with_suffix(".exe")


class ADBStatus(Enum):
    Ready = 0
    Unavailible = 1
    NoDevice = 2


def run_cmd(cmd: list[str], silent=False) -> str:
    return check_output(
        cmd, text=True, encoding="UTF-8", stderr=DEVNULL if silent else sys.stderr
    )


def run_pm(cmd: list[str], silent=False) -> str:
    return run_cmd([ADB_PATH, "shell", "pm", *cmd], silent)


def download_adb():
    url = get_adb_url()

    with urllib.request.urlopen(url) as f:
        data = f.read()

    ADB_FOLDER.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(BytesIO(data)) as archive:
        archive.extractall(ADB_FOLDER)

    if platform.system() != "Windows":
        ADB_PATH.chmod(ADB_PATH.stat().st_mode | stat.S_IEXEC)


def check_for_adb() -> ADBStatus:
    if not ADB_PATH.exists():
        return ADBStatus.Unavailible

    adb_output = run_cmd([ADB_PATH, "devices"])

    if (
        adb_output == "List of devices attached\n\n"
        or "no devices/emulators found" in adb_output
    ):
        return ADBStatus.NoDevice

    return ADBStatus.Ready


def wait_for_device():
    run_cmd([ADB_PATH, "wait-for-device"])


class Package(NamedTuple):
    name: str
    label: Optional[str]

    def __str__(self):
        if self.label is None:
            return self.name
        else:
            return f"{self.label} ({self.name})"


def get_packages(uid=None, third_party_only=True, progress_bar=True) -> set[Package]:
    pm_command = ["list", "packages", "-f"]
    if uid is not None:
        pm_command += ["--user", str(uid)]
    else:
        pm_command += ["-a"]
    if third_party_only:
        pm_command += ["-3"]

    pm_output = run_pm(pm_command).split()

    packages = []

    if progress_bar:
        pm_output_it = tqdm(pm_output)
    else:
        pm_output_it = iter(pm_output)

    for line in pm_output_it:
        line = line.removeprefix("package:")
        i = line.rfind("=")
        name = line[i + 1 :]
        apk = line[:i]
        packages.append(Package(name, get_apk_label(apk)))

    return set(packages)


def download_aapt2():
    url = "https://github.com/rendiix/termux-aapt/raw/main/prebuilt-binary-android-12%2B/arm64/aapt2"

    with urllib.request.urlopen(url) as f:
        data = f.read()

    with TemporaryDirectory() as tdir:
        path = Path(tdir) / "aapt2"
        path = str(path)

        with open(path, "wb") as f:
            f.write(data)

        run_cmd([ADB_PATH, "push", path, AAPT2_PATH_ON_DEVICE])

    run_cmd([ADB_PATH, "shell", "chmod", "+x", AAPT2_PATH_ON_DEVICE])


def run_aapt2(cmd: list[str], silent=False) -> str:
    return run_cmd([ADB_PATH, "shell", AAPT2_PATH_ON_DEVICE, *cmd], silent)


def check_aapt2_works() -> bool:
    try:
        run_aapt2(["-h"], silent=True)
        return True
    except CalledProcessError as e:
        return e.returncode == 1


@cachier(pickle_reload=False)
def get_apk_label(path: str) -> Optional[str]:
    try:
        aapt2_out = run_aapt2(["dump", "badging", path], silent=True).split("\n")
    except CalledProcessError:
        return None

    label_line = next((s for s in aapt2_out if s.startswith("application-label")), None)

    if label_line is None:
        return None

    a = label_line.find("'")
    b = label_line.rfind("'", a + 1)

    return label_line[a + 1 : b]


def get_apk_path(package_name) -> str:
    return run_pm(["path", package_name]).strip().removeprefix("package:")


def get_package_label(package_name) -> Optional[str]:
    apk = get_apk_path(package_name)
    return get_apk_label(apk)


class User(NamedTuple):
    name: str
    uid: int
    packages: set[Package]


def get_users() -> list[User]:
    pm_output = run_pm(["list", "users"])

    pm_output = pm_output.removeprefix("Users:\n")
    pm_output = [s.removeprefix("\tUserInfo{") for s in pm_output.split("\n")]
    pm_output = pm_output[:-1]

    users = []
    for s in pm_output:
        a = s.find(":")
        b = s.find(":", a + 1)
        name = s[a + 1 : b]
        uid = int(s[:a])

        packages = get_packages(uid, progress_bar=False)

        users.append(User(name, uid, packages))

    return users


def install_existing(package: Package, uid: int) -> str:
    return run_pm(["install-existing", "--user", str(uid), package.name])


def uninstall(package: Package, uid: Optional[int], preserve_data=True) -> str:
    pm_command = ["uninstall"]
    if uid is not None:
        pm_command += ["--user", str(uid)]
    if preserve_data:
        pm_command += ["-k"]
    pm_command += [package.name]
    return run_pm(pm_command)


def get_unsafe_to_uninstall(users: list[User]) -> set[str]:
    """Returns packages that are installed for only one user.
    These should be removed completely on uninstall, or will be
    left hanging with no ability to install back (without reinstalling)."""
    seen = set()
    safe = set()
    for user in users:
        safe.update(user.packages.intersection(seen))
        seen.update(user.packages)
    return seen.difference(safe)


def prompt_for_user(users) -> Optional[User]:
    choices = [(user.name, user) for user in users]

    if len(users) == 1 or choices[0][1].uid == 0:
        choices[0] = (choices[0][0] + " (main)", users[0])

    questions = [
        inq.List(
            "user",
            message="Select user",
            choices=choices,
            default=users[1] if len(users) > 1 else users[0],
            carousel=True,
        ),
    ]

    answers = inq.prompt(questions)

    if answers is None:
        return None

    return answers["user"]


class Mode(Enum):
    InstallAll = 0
    UninstallAll = 1
    Select = 2


def prompt_for_preserve_data() -> Optional[bool]:
    questions = [
        inq.Confirm(
            name="preserve_data",
            message="Preserve data and cache after uninstalling?",
            default=True,
        )
    ]

    answers = inq.prompt(questions)

    if answers is None:
        return None

    return answers["preserve_data"]


def prompt_for_mode() -> Optional[Mode]:
    questions = [
        inq.List(
            "mode",
            message="Mode",
            choices=[
                (
                    "Install (show) all available third-party packages for "
                    "specified user",
                    Mode.InstallAll,
                ),
                (
                    "Uninstall (hide) all third-party (including optional oculus "
                    "packages) packages for specified user",
                    Mode.UninstallAll,
                ),
                (
                    "Select packages to be installed (shown) for specified user",
                    Mode.Select,
                ),
            ],
            carousel=True,
        ),
    ]

    answers = inq.prompt(questions)

    if answers is None:
        return None

    return answers["mode"]


def prompt_for_packages(
    all_packages: Iterable[Package], cur_packages: Iterable[Package]
) -> Optional[Iterable[Package]]:
    all_packages = list(all_packages)
    cur_packages = list(cur_packages)

    all_packages.sort(key=str)

    questions = [
        inq.Checkbox(
            "packages",
            message="Select packages (right to select, left to deselect)",
            choices=[(str(package), package) for package in all_packages],
            default=cur_packages,
        )
    ]

    answers = inq.prompt(questions)

    if answers is None:
        return None

    return answers["packages"]


install_success_regex = re.compile(r"Package (.*) installed for user: (.*)")
uninstall_success_regex = re.compile(r"Success")
