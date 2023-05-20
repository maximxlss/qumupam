#!/usr/bin/env python3

import os
import re
from subprocess import check_output
import subprocess
import sys
import platform
from enum import Enum
import time
from typing import NamedTuple, Optional

try:
    from pytermgui import tim
    import inquirer as inq
except ImportError:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "pytermgui", "inquirer"]
    )
    from pytermgui import tim
    import inquirer as inq


class ADBStatus(Enum):
    Ready = 0
    Unavailible = 1
    NoDevice = 2


def run_cmd(cmd: list[str]) -> str:
    return check_output(cmd, text=True, encoding="UTF-8")


def run_pm(cmd: list[str]) -> str:
    return run_cmd(["adb", "shell", "pm", " ".join(cmd)])


def check_for_adb() -> ADBStatus:
    try:
        adb_output = run_cmd(["adb", "devices"])
    except FileNotFoundError:
        return ADBStatus.Unavailible

    if adb_output == "List of devices attached\n\n":
        return ADBStatus.NoDevice

    return ADBStatus.Ready


def wait_for_device():
    run_cmd(["adb", "wait-for-device"])


def get_packages(uid=None, third_party_only=True) -> set[str]:
    pm_command = ["list", "packages"]
    if uid is not None:
        pm_command += ["--user", str(uid)]
    if third_party_only:
        pm_command += ["-3"]

    pm_output = run_pm(pm_command)

    packages = [s.removeprefix("package:") for s in pm_output.split()]

    return set(packages)


class User(NamedTuple):
    name: str
    uid: int
    packages: set[str]


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

        packages = get_packages(uid)

        users.append(User(name, uid, packages))

    return users


def install_existing(package: str, uid: int) -> str:
    return run_pm(["install-existing", "--user", str(uid), package])


def uninstall(package: str, uid: Optional[int], preserve_data=True) -> str:
    pm_command = ["uninstall"]
    if uid is not None:
        pm_command += ["--user", str(uid)]
    if preserve_data:
        pm_command += ["-k"]
    pm_command += [package]
    return run_pm(pm_command)


# def get_unsafe_to_uninstall(users: list[User]) -> set[str]:
#     """Returns packages that are installed for only one user.
#     These would be removed completely on uninstall"""
#     seen = set()
#     safe = set()
#     for user in users:
#         safe.update(user.packages.intersection(seen))
#         seen.update(user.packages)
#     return seen.difference(safe)


def prompt_for_user(users) -> Optional[User]:
    choices = [(user.name, user) for user in users]

    if len(users) == 1 or choices[0][1].uid == 0:
        choices[0] = (choices[0][0] + " (main)", users[0])

    questions = [
        inq.List(
            "user",
            message="Select user:",
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
            message="Mode:",
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


def prompt_for_packages(all_packages, cur_packages) -> Optional[set[str]]:
    questions = [
        inq.Checkbox(
            "packages",
            message="Select packages (right to select, left to deselect):",
            choices=sorted(list(all_packages)),
            default=list(cur_packages),
        )
    ]

    answers = inq.prompt(questions)

    if answers is None:
        return None

    return set(answers["packages"])


install_success_regex = re.compile(r"Package (.*) installed for user: (.*)")
uninstall_success_regex = re.compile(r"Success")


def _main():
    adb_status = check_for_adb()

    if adb_status == ADBStatus.Unavailible:
        if platform.system() != "Windows":
            return tim.print(
                "[red]ERROR:[/] ADB is unavailible! Install ADB and rerun the script."
            )
        return tim.print(
            "[red]ERROR:[/] ADB is unavailible! Install drivers from "
            "[~https://developer.oculus.com/downloads/package/oculus-adb-drivers/]"
            "https://developer.oculus.com/downloads/package/oculus-adb-drivers/[/~]"
            " and rerun the script\n"
            "[limegreen]HINT:[/] To install the drivers, right click on "
            "[limegreen italic]android_winusb.inf[/] and click "
            "[limegreen italic]install[/]"
        )
    elif adb_status == ADBStatus.NoDevice:
        tim.print(
            "[orange]WARNING:[/] No device detected! Possible causes:\n"
            "         - Developer Mode is off (check in the app on the phone)\n"
            "         - Unsupported ADB drivers\n"
            "         - Faulty USB port, power only cable, etc.\n"
            "[grey]INFO:[/] Waiting for device..."
        )
        wait_for_device()

    users = get_users()
    all_packages = get_packages()

    user = prompt_for_user(users)

    if user is None:
        return

    if user.uid == 0 or len(users) == 1:
        tim.print(
            "[red]WARNING:[/] You are trying to use this tool on the main account. "
            "Uninstalling from the main account [red]removes the app completely[/] "
            "(including from additional accounts) and you would need to reinstall "
            "it from scratch to use again. Installing is also pointless. "
            'Type "remove" when prompted for confirmation if you are sure.'
        )

    mode = prompt_for_mode()

    if mode is None:
        return

    pending_install = set()
    pending_uninstall = set()

    if mode == Mode.InstallAll:
        pending_install = all_packages.difference(user.packages)
    elif mode == Mode.UninstallAll:
        pending_uninstall = user.packages
    elif mode == Mode.Select:
        new_packages = prompt_for_packages(all_packages, user.packages)
        if new_packages is None:
            return
        pending_install = new_packages.difference(user.packages)
        pending_uninstall = user.packages.difference(new_packages)

    preserve_data = True
    if pending_uninstall != set():
        preserve_data = prompt_for_preserve_data()
        if preserve_data is None:
            return

    time_start = time.time()

    errors_encountered = False

    if pending_install == set():
        tim.print("[grey]INFO:[/] No packages to install!")
    else:
        tim.print("[grey]INFO:[/] Starting install...")
        for package in pending_install:
            output = install_existing(package, user.uid)
            if not install_success_regex.match(output):
                tim.print(
                    "[orange]WARNING:[/] Encountered the following "
                    f"unexpected output while installing {package}:\n"
                    "         - " + output
                )
                errors_encountered = True
            else:
                tim.print(f"[green]SUCCESS:[/] Installed {package}.")

    if pending_uninstall == set():
        tim.print("[grey]INFO:[/] No packages to uninstall!")
    else:
        if user.uid == 0 or len(users) == 1:
            if input("Confirmation: ") != "remove":
                return tim.print(
                    "[grey]INFO:[/] Exiting.\n"
                    "[green]HINT:[/] If you are confused, read warnings."
                )
        tim.print("[grey]INFO:[/] Starting uninstall...")
        for package in pending_uninstall:
            output = uninstall(package, user.uid, preserve_data=preserve_data)
            if not uninstall_success_regex.match(output):
                tim.print(
                    "[orange]WARNING:[/] Encountered the following "
                    f"unexpected output while uninstalling {package}:\n"
                    "         - " + output
                )
                errors_encountered = True
            else:
                tim.print(f"[green]SUCCESS:[/] Uninstalled {package}.")

    if errors_encountered:
        tim.print(
            "[orange]WARNING:[/] Oh no! It seems there were some errors. "
            "See above for details."
        )

    time_passed = time.time() - time_start

    tim.print(f"[green]SUCCESS:[/] Operation finished in {time_passed:.3f} seconds.")


if __name__ == "__main__":
    _main()

    if platform.system() == "Windows" and getattr(sys, 'frozen', False) \
       and hasattr(sys, '_MEIPASS'):
        os.system("pause")
