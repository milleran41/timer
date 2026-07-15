# Microsoft Store MSIX build

This project includes `build_store_package.py`, a helper script that prepares a Microsoft Store `.msix` package from `dist/timer.exe`.

## 1. Product identity

`build_store_package.py` already contains the FineTimer identity from Microsoft Partner Center:

```python
PACKAGE_NAME = "CodeWerkStudio.FineTimer"
PUBLISHER = "CN=9BAA081B-9857-4C15-9E43-E9B9F5577B14"
PUBLISHER_DISPLAY_NAME = "CodeWerk Studio"
APP_DISPLAY_NAME = "FineTimer"
APP_DESCRIPTION = "Compact desktop timer by CodeWerk Studio."
PACKAGE_VERSION = "1.0.0.0"
```

Microsoft Store product URL:

```text
https://apps.microsoft.com/detail/9MWTDPLL3C5M
```

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
dist/FineTimer.msix
```

## Notes

- `timer.exe` is copied from `dist/timer.exe`.
- PNG package assets are generated from `icon.ico` when Pillow is available.
- If Pillow is not installed, the script creates valid fallback PNG assets.
- If Partner Center asks for a signed package, sign the `.msix` with `SignTool.exe` using the certificate that matches the `Publisher`.
