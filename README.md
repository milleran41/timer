# Timer / FineTimer

Compact Windows timer with a black, white and yellow interface, circular progress, sound alerts and animated transitions. The interface is in English.

## Release Details

- Portable update: **2026-11-20** (build date, not an embedded version number). The EXE has no embedded FileVersion/ProductVersion.
- The existing MSIX package remains **1.0.1.0**. Microsoft Store and MSIX are not updated by this portable release.
- The downloadable EXE is the existing ready build, published without rebuilding.
- Size: **51,008,654 bytes**.
- SHA-256: `27e63e28d35ff6766a25c99e3e28dd5ce6c0778ee8c8e132e251642d55487ac8`.
- [FineTimer in Microsoft Store](https://apps.microsoft.com/detail/9MWTDPLL3C5M).

The portable update actively restores its topmost position above ordinary windows and windowed/borderless games. True exclusive fullscreen is **not supported**. Compatibility with a particular game, fullscreen optimizations and display configuration is not universal.

## Window and Game Visibility

`win_overlay.py` reasserts the timer's topmost position after foreground-window changes and once per second while it is visible. The automatic raise uses `SWP_NOACTIVATE`: it does not activate the timer or move/resize other applications. The timer also returns inside the visible desktop after screen geometry changes. It does not inject code into games.

- Ordinary windows and windowed games: supported topmost mechanism.
- Borderless fullscreen games: intended supported mode; test the specific game and display configuration.
- Fullscreen optimizations: behavior depends on the actual presentation mode and game.
- True exclusive fullscreen: not supported; use a windowed/borderless mode if the timer is hidden.

The owner reports successful manual game checks, without listing game names or exact presentation modes. This publication check confirmed a visible topmost window in the ready EXE. Countdown, pause/reset, local settings, sound dispatch and overlay guards were tested separately against the matching source. Automated tests did not run real games or confirm audible output.

## Screenshot

![Timer screenshot](screenshot.png)

The image is a 2x Qt rendering of the standard 160x160 widget from the previously verified source, not a desktop capture. The drawing and time-dialog code are unchanged in this portable update, so the image is retained. Both current modules, `timer.py` and `win_overlay.py`, were verified against the code embedded in the new ready EXE.

## Download

[Download Timer](https://github.com/milleran41/timer/raw/main/dist/timer.exe)

## System Requirements

- Platform: Windows 10/11 (64-bit)
- Download: Ready-to-run `.exe` for Windows

## How to use

1. Download `timer.exe`.
2. Open the program with a double-click.
3. Double-click the timer window to set hours, minutes, and seconds.
4. Confirming a positive duration starts the countdown. Press the left button to start or pause it.
5. Press the middle button to reset the timer.
6. Press the right button to close the program.

## Controls

- Double-click on the timer: open the time setup window
- Mouse wheel: change the timer value when it is not running
- Drag with the mouse: move the timer window on the screen

## Additional Features

- Animated appearance, closing, digits and warning effects.
- Guarded audio initialization: an unavailable audio device does not abort startup.
- Optional Store rating prompt after several completed sessions, with "Not now" and "Don't ask again" choices.
- Rating preferences and completed-session counts are stored locally in `%LOCALAPPDATA%\TimerApp\settings.json`, not in the repository or download.

## Project files

- `timer.py`: source code
- `win_overlay.py`: Windows topmost keeper and foreground-event handling
- `dist/timer.exe`: ready-to-run Windows build
- `build_store_package.py`: helper script for creating a Microsoft Store `.msix` package
- `timer.spec`: PyInstaller configuration using the repository-relative icon. No build was performed for this update.
- `build.bat`: supplied Windows build script, pinning PyInstaller 6.22.0 for the recorded startup compatibility issue. It was not executed for this publication.
- `icon.ico`: current application icon
- `timer.html`: separate historical browser variant, not the source of the Windows EXE

Source runtime dependencies are PyQt6, pygame and NumPy. The ready EXE includes its runtime; users do not need Python. Never commit signing certificates, private keys, local profiles or build intermediates.

## Microsoft Store package

To create `dist/timer.msix` for Microsoft Store, fill the Partner Center values at the top of `build_store_package.py`, install Windows SDK with `MakeAppx.exe`, then run:

```powershell
python build_store_package.py
```

More details: [docs/microsoft-store-msix.md](docs/microsoft-store-msix.md)
