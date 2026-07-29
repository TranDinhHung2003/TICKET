@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo  Facebook Group Poster - Build EXE
echo  Ban thuong - source van extract duoc
echo ============================================
echo.
echo Muon bao ve code: chay build_secure.bat
echo Muon manh hon:    chay build_nuitka.bat
echo.

call :find_python
if not defined PYTHON (
    echo [LOI] Khong tim thay Python. Hay cai Python 3.11+
    echo https://www.python.org/downloads/
    echo Tick: Add python.exe to PATH
    pause
    exit /b 1
)

echo Dung Python: %PYTHON%
%PYTHON% --version
echo.

echo [1/3] Cai dat dependencies...
%PYTHON% -m pip install -r requirements.txt -q
%PYTHON% -m pip install pyinstaller -q
if errorlevel 1 (
    echo [LOI] Cai package that bai
    pause
    exit /b 1
)

echo.
echo [2/3] Build file EXE...
%PYTHON% -m PyInstaller fb_poster.spec --clean --noconfirm
if errorlevel 1 (
    echo [LOI] PyInstaller that bai
    pause
    exit /b 1
)

echo.
if exist "dist\FacebookGroupPoster.exe" (
    echo [3/3] BUILD THANH CONG!
    echo.
    echo File EXE nam tai: dist\FacebookGroupPoster.exe
    echo.
    dir "dist\FacebookGroupPoster.exe" | findstr "FacebookGroupPoster"
    echo.
    start "" "dist\"
) else (
    echo [LOI] Build that bai. Xem log tren.
)

pause
exit /b 0

:find_python
set "PYTHON="
where py >nul 2>&1
if not errorlevel 1 (
    py -3 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON=py -3"
        goto :eof
    )
)
where python >nul 2>&1
if not errorlevel 1 (
    python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON=python"
        goto :eof
    )
)
where python3 >nul 2>&1
if not errorlevel 1 (
    python3 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON=python3"
        goto :eof
    )
)
goto :eof
