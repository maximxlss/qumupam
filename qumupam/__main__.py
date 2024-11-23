import os
import sys
import platform
import time
from pytermgui import tim
from qumupam.utilities import (
    download_adb,
    get_unsafe_to_uninstall,
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
    check_aapt2_works,
    download_aapt2,
)


def main():
    adb_status = check_for_adb()

    if adb_status == ADBStatus.Unavailible:
        tim.print("[grey]INFO:[/] Downloading ADB...")
        download_adb()
        tim.print("[green]SUCCESS:[/] Done!")
        adb_status = check_for_adb()

    if adb_status == ADBStatus.NoDevice:
        tim.print(
            "[orange]WARNING:[/] No device detected! Possible causes:\n"
            "         - Developer Mode is off (check in the app on the phone)\n"
            "         - Unsupported ADB drivers (you can get the official ones here: "
            "[~https://developer.oculus.com/downloads/package/oculus-adb-drivers/]"
            "https://developer.oculus.com/downloads/package/oculus-adb-drivers/[/~])\n"
            "         - Faulty USB port, power only cable, etc.\n"
            "[grey]INFO:[/] Waiting for device..."
        )
        wait_for_device()

    if not check_aapt2_works():
        download_aapt2()

    tim.print(
        "[grey]INFO:[/] Gathering package information...\n"
        "[green]HINT:[/]This can be slow on the first run, be patient!"
    )
    all_packages = get_packages()
    users = get_users()

    user = prompt_for_user(users)

    if user is None:
        return

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
        new_packages = set(new_packages)
        pending_install = new_packages.difference(user.packages)
        pending_uninstall = user.packages.difference(new_packages)

    preserve_data = True
    if pending_uninstall != set():
        preserve_data = prompt_for_preserve_data()
        if preserve_data is None:
            return

    unsafe_to_uninstall = get_unsafe_to_uninstall(users)

    pending_unsafe = pending_uninstall.intersection(unsafe_to_uninstall)
    remove_packages = False

    if pending_unsafe != set():
        tim.print(
            "[red]IMPORTANT WARNING:[/] You are trying to uninstall packages from the "
            "last user that has them. That would break them, and to avoid confusion, "
            "it's advised to remove them completely (or if you want to install them "
            "on another account, do that first). The following packages are affected:\n"
            + "".join(f"        - {package}\n" for package in pending_unsafe)
            + 'To remove them, type "remove" and press enter.\n'
            'To leave them broken, type "break" and press enter.\n'
            "To skip them and continue, press enter.\n"
        )
        inp = input("> ")
        if inp == "remove":
            remove_packages = True
        elif inp != "break":
            pending_uninstall.difference_update(pending_unsafe)

    time_start = time.time()

    errors_encountered = False

    if mode != Mode.UninstallAll and pending_install == set():
        tim.print("[grey]INFO:[/] No packages to install!")
    elif pending_install != set():
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

    if mode != Mode.InstallAll and pending_uninstall == set():
        tim.print("[grey]INFO:[/] No packages to uninstall!")
    elif pending_uninstall != set():
        for package in pending_uninstall:
            if remove_packages and package in pending_unsafe:
                output = uninstall(package, None, preserve_data=preserve_data)
            else:
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
    try:
        main()
    finally:
        if (
            platform.system() == "Windows"
            and getattr(sys, "frozen", False)
            and hasattr(sys, "_MEIPASS")
        ):
            os.system("pause")
