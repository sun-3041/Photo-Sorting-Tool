@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 -m pip install -r requirements-optional.txt
if errorlevel 1 (
  echo.
  echo 可选格式组件安装失败，请检查网络或 Python 安装。
  pause
  exit /b 1
)
echo.
echo HEIC/HEIF 和相机 RAW 支持已安装。
pause
