@echo off
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Python was not found. Install Python 3.11 or later.
  exit /b 1
)

for /f "delims=" %%V in ('python -c "import sys; sys.path.insert(0, 'src'); from chat_message_agent.version import __version__; print(__version__)"') do set "APP_VERSION=%%V"
if not defined APP_VERSION (
  echo [ERROR] Unable to read application version.
  exit /b 1
)
set "EXE_NAME=chat-message-agent-v%APP_VERSION%.exe"
echo Building chat-message-agent version %APP_VERSION%

python -m pip install -r requirements-dev.txt
if errorlevel 1 exit /b 1

if exist build rmdir /s /q build
if exist dist\chat-message-agent.exe del /q dist\chat-message-agent.exe
if exist dist\chat-message-agent-v*.exe del /q dist\chat-message-agent-v*.exe

python scripts\generate_version_info.py build\version_info.txt
if errorlevel 1 exit /b 1

python -m PyInstaller --noconfirm chat-message-agent.spec
if errorlevel 1 exit /b 1

if not exist "dist\%EXE_NAME%" (
  echo [ERROR] dist\%EXE_NAME% was not generated.
  exit /b 1
)

for /f "delims=" %%V in ('dist\%EXE_NAME% --version') do set "EXE_VERSION=%%V"
if not "%EXE_VERSION%"=="%APP_VERSION%" (
  echo [ERROR] EXE version %EXE_VERSION% does not match %APP_VERSION%.
  exit /b 1
)

echo [SUCCESS] dist\%EXE_NAME% version %APP_VERSION%
exit /b 0
