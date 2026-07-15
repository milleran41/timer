# Microsoft Store MSIX build

This project includes `build_store_package.py`, a helper script that prepares a Microsoft Store `.msix` package from `dist/timer.exe`.

## 1. Fill Partner Center values

Open `build_store_package.py` and replace the values at the top:

```python
PACKAGE_NAME = "MillerAndreas.Timer"
PUBLISHER = "CN=PASTE_YOUR_PUBLISHER_ID_HERE"
PUBLISHER_DISPLAY_NAME = "Andreas Miller"
APP_DISPLAY_NAME = "Timer"
APP_DESCRIPTION = "Simple desktop timer by CodeWerk."
PACKAGE_VERSION = "1.0.0.0"
```

Use the exact package identity and publisher values from Microsoft Partner Center.

## 2. Install Windows SDK

The script needs `MakeAppx.exe` from Windows SDK.

Install Windows SDK from Microsoft:

```text
https://developer.microsoft.com/windows/downloads/windows-sdk/
```

During installation, include the MSIX/Appx packaging tools.

## 3. Build the package

From the repository folder:

```powershell
python build_store_package.py
```

If Python is not in PATH, use the full path to your Python executable.

The output file will be:

```text
dist/timer.msix
```

## Notes

- `timer.exe` is copied from `dist/timer.exe`.
- PNG package assets are generated from `icon.ico` when Pillow is available.
- If Pillow is not installed, the script creates valid fallback PNG assets.
- If Partner Center asks for a signed package, sign the `.msix` with `SignTool.exe` using the certificate that matches the `Publisher`.
