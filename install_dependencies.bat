@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo 依赖安装失败，请检查网络或 Python 安装。
  pause
  exit /b 1
)
echo.
echo 基础依赖安装完成。
echo 如需 HEIC/HEIF 和相机 RAW 支持，可继续运行 install_optional_formats.bat。
pause
