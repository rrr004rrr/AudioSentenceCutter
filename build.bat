@echo off
chcp 65001 >nul
echo ============================================
echo  AI 音檔分割工具 - PyInstaller 打包
echo ============================================
echo.

REM Check pyinstaller (via python -m so user-site installs are found)
python -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] 未偵測到 PyInstaller，正在安裝...
    python -m pip install --user pyinstaller
)

echo [1/3] 清除舊的建置資料...
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

REM cmd.exe cannot reliably pass non-ASCII args to subprocesses, so build with
REM an ASCII --name and rename via PowerShell (which handles UTF-8) afterwards.
echo [2/3] 開始打包...
REM build.spec collects all required packages and raises the recursion
REM limit needed for the faster_whisper / ctranslate2 transitive graph.
python -m PyInstaller --clean build.spec

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] 打包失敗，請檢查錯誤訊息。
    pause
    exit /b 1
)

echo [3/3] 重新命名輸出檔...
REM Retry the rename — Windows Defender often locks the freshly-written
REM .exe for several seconds while scanning it.
powershell -NoProfile -Command "$old='dist\AudioSentenceCutter.exe'; $new='dist\AI音檔分割工具.exe'; if (Test-Path $new) { Remove-Item $new -Force }; for ($i=0; $i -lt 10; $i++) { try { Rename-Item -LiteralPath $old -NewName 'AI音檔分割工具.exe' -ErrorAction Stop; break } catch { Start-Sleep -Seconds 2 } }"

echo.
echo ============================================
echo  打包成功！
echo  輸出位置: dist\AI音檔分割工具.exe
echo ============================================
pause
