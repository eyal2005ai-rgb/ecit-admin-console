@echo off
REM Builds the app folder and a setup .exe (unsigned). Run on Windows from the project root.
REM Needs Python 3.10+ and Inno Setup 6 (https://jrsoftware.org/isinfo.php).
python -m venv .venv || exit /b 1
call .venv\Scripts\activate
pip install -r requirements-dev.txt || exit /b 1
python -m pytest -q tests || exit /b 1
rmdir /s /q build dist 2>nul
pyinstaller --noconfirm packaging\ecit_console.spec || exit /b 1
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" packaging\installer.iss || exit /b 1
echo Done: dist\ECIT-Admin-Console-0.1.0-setup.exe
echo Unsigned: SmartScreen will show "More info" ^> "Run anyway".
