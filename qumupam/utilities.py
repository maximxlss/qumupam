#!/usr/bin/env python3

import re
from subprocess import check_output
from enum import Enum
from typing import NamedTuple, Optional
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