@echo off
chcp 65001 >nul
cd /d "%~dp0"
py -3 photo_selector.py
if errorlevel 1 (
  echo.
  echo 启动失败。请先运行 install_dependencies.bat 安装依赖。
  pause
)
