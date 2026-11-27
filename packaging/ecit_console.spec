# PyInstaller spec — run from the project root:  pyinstaller packaging/ecit_console.spec
import sys
from pathlib import Path

root = Path(SPECPATH).parent
icon = str(root / "resources" / "ecit_icon.png")   # square; Pillow converts it to .ico/.icns

a = Analysis([str(root / "main.py")], pathex=[str(root)],
             datas=[(str(root / "resources"), "resources"), (str(root / "docs"), "docs")],
             excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.Qt3DCore"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="ECIT Admin Console",
          console=False, icon=icon)
coll = COLLECT(exe, a.binaries, a.datas, name="ECIT Admin Console")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="ECIT Admin Console.app", icon=icon,
                 bundle_identifier="il.co.ecit.adminconsole",
                 info_plist={"CFBundleShortVersionString": "0.1.0", "NSHighResolutionCapable": True})
