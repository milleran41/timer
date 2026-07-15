from __future__ import annotations

import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path
from xml.sax.saxutils import escape


# Product identity from Microsoft Partner Center.
PACKAGE_NAME = "CodeWerkStudio.FineTimer"
PUBLISHER = "CN=9BAA081B-9857-4C15-9E43-E9B9F5577B14"
PUBLISHER_DISPLAY_NAME = "CodeWerk Studio"
APP_DISPLAY_NAME = "FineTimer"
APP_DESCRIPTION = "Compact desktop timer by CodeWerk Studio."
PACKAGE_VERSION = "1.0.0.0"
APPLICATION_ID = "Timer"
PROCESSOR_ARCHITECTURE = "x64"


# Local project files.
PROJECT_ROOT = Path(__file__).resolve().parent
EXE_PATH = PROJECT_ROOT / "dist" / "timer.exe"
ICON_PATH = PROJECT_ROOT / "icon.ico"
OUTPUT_MSIX = PROJECT_ROOT / "dist" / "FineTimer.msix"


def fail(message: str, code: int = 1) -> None:
    print(f"ERROR: {message}")
    raise SystemExit(code)


def find_makeappx() -> Path | None:
    candidates: list[Path] = []

    sdk_dir = os.environ.get("WindowsSdkDir")
    if sdk_dir:
        candidates.extend(Path(sdk_dir).glob("bin/*/x64/MakeAppx.exe"))
        candidates.extend(Path(sdk_dir).glob("bin/*/x86/MakeAppx.exe"))

    program_roots = [
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("ProgramFiles"),
    ]
    for root in filter(None, program_roots):
        kits = Path(root) / "Windows Kits" / "10" / "bin"
        candidates.extend(kits.glob("*/x64/MakeAppx.exe"))
        candidates.extend(kits.glob("*/x86/MakeAppx.exe"))
        candidates.extend((Path(root) / "Windows Kits" / "10" / "App Certification Kit").glob("[Mm]akeappx.exe"))

    for candidate in sorted(candidates, reverse=True):
        if candidate.exists():
            return candidate
    return None


def png_chunk(kind: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(kind)
    crc = zlib.crc32(data, crc)
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", crc & 0xFFFFFFFF)


def write_simple_png(path: Path, width: int, height: int) -> None:
    """Write a dependency-free fallback icon with a simple CodeWerk-style T mark."""
    bg = (16, 8, 25, 255)
    accent = (199, 255, 57, 255)
    glow = (255, 79, 216, 255)
    rows = []
    bar_h = max(4, height // 7)
    stem_w = max(4, width // 5)
    top_y = height // 4
    stem_x0 = (width - stem_w) // 2
    stem_x1 = stem_x0 + stem_w
    for y in range(height):
        row = bytearray()
        row.append(0)
        for x in range(width):
            in_top = top_y <= y < top_y + bar_h and width // 5 <= x <= width - width // 5
            in_stem = top_y <= y <= height - height // 5 and stem_x0 <= x <= stem_x1
            in_glow = top_y + bar_h <= y <= top_y + bar_h * 2 and stem_x0 - stem_w <= x <= stem_x1 + stem_w
            if in_top or in_stem:
                row.extend(accent)
            elif in_glow:
                row.extend(glow)
            else:
                row.extend(bg)
        rows.append(bytes(row))

    raw = b"".join(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + png_chunk(b"IDAT", zlib.compress(raw, 9))
        + png_chunk(b"IEND", b"")
    )


def create_assets(assets_dir: Path) -> None:
    sizes = {
        "Square44x44Logo.png": (44, 44),
        "Square71x71Logo.png": (71, 71),
        "Square150x150Logo.png": (150, 150),
        "Wide310x150Logo.png": (310, 150),
        "Square310x310Logo.png": (310, 310),
        "StoreLogo.png": (50, 50),
    }
    assets_dir.mkdir(parents=True, exist_ok=True)

    try:
        from PIL import Image  # type: ignore

        if not ICON_PATH.exists():
            raise FileNotFoundError(ICON_PATH)
        source = Image.open(ICON_PATH)
        for name, (width, height) in sizes.items():
            frame = source.copy()
            frame.thumbnail((width, height), Image.LANCZOS)
            canvas = Image.new("RGBA", (width, height), (16, 8, 25, 255))
            x = (width - frame.width) // 2
            y = (height - frame.height) // 2
            canvas.alpha_composite(frame.convert("RGBA"), (x, y))
            canvas.save(assets_dir / name)
        print("Created PNG assets from icon.ico using Pillow.")
        return
    except Exception as exc:
        print(f"Pillow/icon conversion is not available ({exc}).")
        print("Creating valid fallback PNG assets instead.")

    for name, (width, height) in sizes.items():
        write_simple_png(assets_dir / name, width, height)


def write_manifest(package_dir: Path) -> None:
    manifest = f"""<?xml version="1.0" encoding="utf-8"?>
<Package
  xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
  xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
  xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
  IgnorableNamespaces="uap rescap">
  <Identity
    Name="{escape(PACKAGE_NAME)}"
    Publisher="{escape(PUBLISHER)}"
    Version="{escape(PACKAGE_VERSION)}"
    ProcessorArchitecture="{escape(PROCESSOR_ARCHITECTURE)}" />
  <Properties>
    <DisplayName>{escape(APP_DISPLAY_NAME)}</DisplayName>
    <PublisherDisplayName>{escape(PUBLISHER_DISPLAY_NAME)}</PublisherDisplayName>
    <Logo>Assets\\StoreLogo.png</Logo>
  </Properties>
  <Dependencies>
    <TargetDeviceFamily
      Name="Windows.Desktop"
      MinVersion="10.0.17763.0"
      MaxVersionTested="10.0.22621.0" />
  </Dependencies>
  <Resources>
    <Resource Language="en-us" />
  </Resources>
  <Applications>
    <Application
      Id="{escape(APPLICATION_ID)}"
      Executable="timer.exe"
      EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements
        DisplayName="{escape(APP_DISPLAY_NAME)}"
        Description="{escape(APP_DESCRIPTION)}"
        BackgroundColor="#100819"
        Square150x150Logo="Assets\\Square150x150Logo.png"
        Square44x44Logo="Assets\\Square44x44Logo.png">
        <uap:DefaultTile
          Wide310x150Logo="Assets\\Wide310x150Logo.png"
          Square310x310Logo="Assets\\Square310x310Logo.png"
          Square71x71Logo="Assets\\Square71x71Logo.png" />
      </uap:VisualElements>
    </Application>
  </Applications>
  <Capabilities>
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
</Package>
"""
    (package_dir / "AppxManifest.xml").write_text(manifest, encoding="utf-8", newline="\r\n")


def build_package() -> None:
    if not EXE_PATH.exists():
        fail(f"Cannot find {EXE_PATH}. Build the executable first.")

    makeappx = find_makeappx()
    if not makeappx:
        fail(
            "MakeAppx.exe was not found. Install Windows SDK, then run this script again.\n"
            "Reliable alternative: install 'Windows SDK' from Microsoft and enable "
            "'MSIX Packaging Tools' / 'Windows SDK Signing Tools for Desktop Apps'.",
            code=2,
        )

    OUTPUT_MSIX.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="timer_msix_") as temp:
        package_dir = Path(temp) / "package"
        package_dir.mkdir()

        shutil.copy2(EXE_PATH, package_dir / "timer.exe")
        create_assets(package_dir / "Assets")
        write_manifest(package_dir)

        if OUTPUT_MSIX.exists():
            OUTPUT_MSIX.unlink()

        command = [
            str(makeappx),
            "pack",
            "/d",
            str(package_dir),
            "/p",
            str(OUTPUT_MSIX),
            "/o",
        ]
        print("Running MakeAppx:")
        print(" ".join(f'"{part}"' if " " in part else part for part in command))
        subprocess.run(command, check=True)

    print()
    print(f"Done: {OUTPUT_MSIX}")
    print("Next step: upload this .msix in Microsoft Partner Center.")
    print("If Partner Center asks for a signed package, sign it with SignTool using the certificate that matches Publisher.")


if __name__ == "__main__":
    build_package()
