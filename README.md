# Carrier Command 2 Dedicated Server on Linux

How to install, configure, and run the Carrier Command 2 (CC2) `dedicated_server.exe` on Linux via Wine.

## Installation

CC2 (incl. its dedicated server binary) can be installed via [SteamCMD](https://developer.valvesoftware.com/wiki/SteamCMD) with `steamcmd +@sSteamCmdForcePlatformType windows +force_install_dir ~/.wine/drive_c/CC2_server +login $STEAM_USERNAME +app_update 1489630 validate +quit`.
However, the resulting installation lacks required DLLs, without which the server will fail with the log message `failed to initialise SteamGameServer` and no further details ([geometa.co.uk support ticket](https://geometa.co.uk/support/carriercommand/2287)).
The missing DLLs (`steamclient.dll`, `tier0_s.dll`, and `vstdlib_s.dll`) are shipped with the regular Steam *Windows* client (not Linux SteamCMD).

A more streamlined installation approach is to copy the files required to run the dedicated server from a local Windows installation of the Steam client and CC2.
The following PowerShell commands can be used to locate, pack, and upload a ~150 MB ZIP archive containing all required files to a Linux host, which will later run the dedicated server via Wine:

```pwsh
$steam_dir = (Get-ItemProperty -Path Registry::HKCU\SOFTWARE\Valve\Steam).SteamPath
$cc2_dir = (Get-ItemProperty -Path "Registry::HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 1489630").InstallLocation
Compress-Archive -CompressionLevel Fastest -Path "$steam_dir/steamclient.dll","$steam_dir/tier0_s.dll","$steam_dir/vstdlib_s.dll","$cc2_dir/dedicated_server.exe","$cc2_dir/steam_api.dll","$cc2_dir/steam_appid.txt","$cc2_dir/rom_*" -DestinationPath "CC2_server.zip"
scp CC2_server.zip user@host:~/
```

The Linux host needs only a regular Wine installation (Wine 8.0 on Debian Bookworm is known to work).
No [winetricks](https://github.com/Winetricks/winetricks) are required.
On the Linux host, create the required directory structure and unpack the uploaded ZIP archive:

```sh
mkdir -p ~/.wine/drive_c/CC2_server
unzip CC2_server.zip -d ~/.wine/drive_c/CC2_server
```

## Configuration

This repository includes a default [`server_config.xml`](.wine/drive_c/CC2_server/server_config.xml).
Edit the file to suit your needs.
The config defaults to load a `save.xml` file placed in [`C:/CC2_server/saved_games/slot_0/`](.wine/drive_c/CC2_server/saved_games/slot_0/) if it exists.
You can upload any `save.xml` file from your local CC2 installation.

## Running the Server

Start the server as follows (preferably in a `screen`/`tmux` session).
The command line includes `WINEDLLOVERRIDES` to disable superfluous services.

```sh
cd ~/.wine/drive_c/CC2_server
WINEDLLOVERRIDES="explorer.exe=d;services.exe=d;wbemprox.dll=d" wine dedicated_server.exe
```

Note that when running on a headless server (no GUI), Wine will print error messages regarding the failure to open graphical windows (e.g., `0024:err:winediag:nodrv_CreateWindow Application tried to create a window, but no driver could be loaded.`).
These errors can be ignored, as the CC2 `dedicated_server.exe` is a command line only program.

To run the CC2 server as a background service, this repository includes a [systemd.service file](.config/systemd/user/cc2-server.service).
Note that you may need to [`loginctl enable-linger $USERNAME`](https://manpages.debian.org/bookworm/systemd/loginctl.1.en.html#User_Commands) as root to ensure the service is not terminated when the user logs out and that the server will be started automatically after system boot.


## Known Issues

* The dedicated server can load save games, but cannot write save games!
  All progress will be lost when the dedicated server is stopped.
  [1](https://geometa.co.uk/support/carriercommand/2227)
  [2](https://geometa.co.uk/support/carriercommand/13520)
  [3](https://geometa.co.uk/support/carriercommand/26425)
  [4](https://steamcommunity.com/app/1489630/discussions/0/3413181885098097346/)
  [5](https://steamcommunity.com/app/1489630/discussions/0/5400412918960408530/)
* Performance on VM (with dedicated vCPUs) is significantly worse than running the same save game on a Windows client in single player, despite each thread of the dedicated server limited to ~50% CPU load.
  Needs further investigation. Possibly a thread synchronization bottleneck.
  **TODO**: Try unvirtualized and with [NTSYNC](https://lore.kernel.org/lkml/20241213193511.457338-1-zfigura@codeweavers.com/).

## Additional Documentation

* <https://geometa.co.uk/wiki/carrier_command_2/view/dedicated_servers>

## Debugging (Memo to Self)

### Identify missing libraries

Configure [Wine debug channels](https://gitlab.winehq.org/wine/wine/-/wikis/Debug-Channels) via `WINEDEBUG`:
```sh
WINEDEBUG="warn+module" wine dedicated_server.exe
```

Output:
```
00:00:00:0002 : starting server...
...
0024:warn:module:load_dll Failed to load module L"steamclient.dll"; status=c0000135
00:00:00:0009 : failed to initialise SteamGameServer
00:00:00:0009 : shutting down...
00:00:00:0009 : stopping server...
```

### Find save game directory

Run server with `save_name="slot_0"` in `server_configuration.xml` and use `strace` to find file operations on paths that smell like a save game:
```sh
strace -f -e trace=%file wine dedicated_server.exe >/tmp/log 2>&1 ; grep -E 'saved_games|slot_0|save.xml' /tmp/log
```

Output:
```
[pid nnnnn] statx(AT_FDCWD, "/home/cc2/.wine/dosdevices/c:/CC2_server/saved_games/slot_0/save.xml", AT_STATX_SYNC_AS_STAT|AT_NO_AUTOMOUNT, STATX_BASIC_STATS, 0x1cde82c) = -1 ENOENT (No such file or directory)
[pid nnnnn] statx(AT_FDCWD, "/home/cc2/.wine/dosdevices/c:/CC2_server/saved_games", AT_STATX_SYNC_AS_STAT|AT_NO_AUTOMOUNT, STATX_BASIC_STATS, 0x1cde34c) = -1 ENOENT (No such file or directory)
```
