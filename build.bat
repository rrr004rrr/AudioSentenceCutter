@echo off
echo ============================================
echo  AI 音檔分割工具 - PyInstaller 打包
echo ============================================
echo.

REM Check pyinstaller
pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 未偵測到 PyInstaller，正在安裝...
    pip install pyinstaller
)

echo [1/2] 清除舊的建置資料...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

echo [2/2] 開始打包...
pyinstaller ^
  --onefile ^
  --noconsole ^
  --name "AI音檔分割工具" ^
  --add-data "ui;ui" ^
  --add-data "core;core" ^
  --add-data "utils;utils" ^
  --hidden-import "faster_whisper" ^
  --hidden-import "pyqtgraph" ^
  --hidden-import "pydub" ^
  --hidden-import "numpy" ^
  main.py

if %errorlevel% equ 0 (
    echo.
    echo ============================================
    echo  打包成功！
    echo  輸出位置: dist\AI音檔分割工具.exe
    echo ============================================
) else (
    echo.
    echo [ERROR] 打包失敗，請檢查錯誤訊息。
)
pause
