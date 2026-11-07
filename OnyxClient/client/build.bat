@echo off
REM Construit client\dist\OnyxClient.exe (Python 3.13 via uv)
cd /d "%~dp0"
if not exist .venv (
  uv venv --python 3.13 .venv || exit /b 1
  uv pip install --python .venv -r requirements.txt || exit /b 1
)
.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean MacroClient.spec
