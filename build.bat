@echo off
REM YT Downloader - Build Script for Windows
REM Simply run: build.bat

echo.
echo ====================================
echo YT Downloader - Build Script
echo ====================================
echo.

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Building executable... (this will take 3-7 minutes on first build)
echo.

REM Run PyInstaller
python -m PyInstaller main.py --onefile --windowed --name ytdownloader --icon image.ico --add-data "image.ico:." --collect-all requests --collect-all certifi --collect-all yt_dlp --hidden-import=yt_dlp --hidden-import=yt_dlp.extractor --hidden-import=yt_dlp.postprocessor

if errorlevel 1 (
    echo.
    echo ERROR: Build failed
    pause
    exit /b 1
)

REM Clean up
echo.
echo Cleaning up...
if exist build rmdir /s /q build
if exist ytdownloader.spec del ytdownloader.spec
if exist __pycache__ rmdir /s /q __pycache__

echo.
echo ====================================
echo SUCCESS! Build complete
echo ====================================
echo.
echo Your executable is ready at:
echo   dist\ytdownloader.exe
echo.
echo To run it:
echo   Just double-click dist\ytdownloader.exe
echo.
echo To share it:
echo   Send dist\ytdownloader.exe to others
echo   They just need to double-click it (no Python required)
echo.
pause
