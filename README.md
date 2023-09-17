# QUMUPAM - QUest Multi User PAckage Manager
A little tool to manage packages on Meta Quest with multiple users.

## ❗️Disclaimer❗️
### NEEDS TESTING, BE CAREFUL.
- I have tested this myself on Quest 2, installing/uninstalling apps and preserving/deleting savedata (with [com.ForwardXP.nuke](https://www.oculus.com/experiences/quest/2706567592751319/), for example) and it works __for me__.
- Please start using this from apps you don't need/apps you can easily recover, if that works, continue on with the others.
- I plan on removing this disclaimer as I get some feedback at [issue #1](https://github.com/maximxlss/qumupam/issues/1) discussion

## ⚡ Quickstart
### Windows
1. Download [qumupam.exe](https://github.com/maximxlss/qumupam/releases/download/latest/qumupam.exe)
2. Connect your Quest in Developer Mode and run `qumupam.exe`
3. Dismiss the SmartScreen popup (it is actually basically impossible to make it not show that popup)
### Linux
1. Run `pip install git+https://github.com/maximxlss/qumupam`
2. Connect your Quest in Developer Mode and run `qumupam`

## 💬 Motivation
Recently, I wanted to lend my Quest to another person, but wanted them to have a separate account. Luckily, for some time now Quest supports multiple accounts. However, there is no way to share sideloaded apps to another account without completely reinstalling the app. Moreover, I couldn't find ANY info on how do you do that.

## 📄 Descriprion
Meet QUMUPAM - a tool made to do exactly that! It can "install" and "uninstall" packages to and from different accounts on your Quest. You can install/uninstall all apps or choose which would be available. This _does not_ take up space, see notes.

## ⚠️ Dangers
- This has the potential to delete your apps and saves. Please be careful and read whatever the tool says to you.
- Although the tool uses official tools internally and has very little room for critical bugs, it technically can break on some apps, breaking them or deleting data. I can't guarantee your data safety.

## 📓 Notes
- Install/uninstall is effectively show/hide in this context. I only use install/uninstall because it's how it's called internally.
- The way this tool works is not exclusive to Meta Quest. It probably works for any android system with multiple users, but I didn't test that and don't plan on doing that.
- If you make Beat Saber installed only on one account and install BMBF, you can bring it back on the other accounts and it will be modded there too.
