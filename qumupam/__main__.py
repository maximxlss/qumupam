import os
import sys
import platform
import time
from pytermgui import tim
from qumupam.utilities import (
    install_success_regex,
    uninstall_success_regex,
    ADBStatus,
    Mode,
    check_for_adb,
    get_packages,
    get_users,
    install_existing,
    prompt_for_mode,
    prompt_for_packages,
    prompt_for_preserve_data,
    prompt_for_user,
    uninstall,
    wait_for_device,
)


def main():
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

    tim.print(
        "[grey]INFO:[/] Gathering package information...\n"
        "[green]HINT:[/]This can be slow on the first run, be patient!"
    )
    all_packages = get_packages()
    users = get_users()

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

    if (
        platform.system() == "Windows"
        and getattr(sys, "frozen", False)
        and hasattr(sys, "_MEIPASS")
    ):
        os.system("pause")


if __name__ == "__main__":
    main()
