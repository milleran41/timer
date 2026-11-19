# Timer / FineTimer

Compact Windows timer with a black, white and yellow interface, circular progress, sound alerts and animated transitions. The interface is in English.

## Release Details

- MSIX package version: **1.0.1.0**. The EXE has no embedded FileVersion/ProductVersion.
- The downloadable EXE is the existing ready build, published without rebuilding.
- Size: **51,026,824 bytes**.
- SHA-256: `9972ae738ce374c79e1114e9da85a2cad4763ee97682394b96a146ca058f70a3`.
- [FineTimer in Microsoft Store](https://apps.microsoft.com/detail/9MWTDPLL3C5M).

The window requests always-on-top placement. Visibility over exclusive fullscreen games is **not guaranteed**; that known limitation has not been verified as fixed.

## Screenshot

![Timer screenshot](screenshot.png)

The image is a 2x Qt rendering of the standard 160x160 widget from the verified source, not a desktop capture. Compiling `timer.py` was verified to produce the same code as the ready EXE's embedded Python module.

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
- `dist/timer.exe`: ready-to-run Windows build
- `build_store_package.py`: helper script for creating a Microsoft Store `.msix` package
- `timer.spec`: PyInstaller configuration using the repository-relative icon. No build was performed for this update.
- `icon.ico`: current application icon
- `timer.html`: separate historical browser variant, not the source of the Windows EXE

Source runtime dependencies are PyQt6, pygame and NumPy. The ready EXE includes its runtime; users do not need Python. Never commit signing certificates, private keys, local profiles or build intermediates.

## Microsoft Store package

To create `dist/timer.msix` for Microsoft Store, fill the Partner Center values at the top of `build_store_package.py`, install Windows SDK with `MakeAppx.exe`, then run:

```powershell
python build_store_package.py
```

More details: [docs/microsoft-store-msix.md](docs/microsoft-store-msix.md)
