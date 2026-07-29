@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo  Facebook Group Poster - BUILD NUITKA
echo  Bien dich Python sang binary C
echo ============================================
echo.
echo Ban bao ve manh nhat [mien phi].
echo Lan dau co the mat 5-15 phut.
echo.

call :find_python
if not defined PYTHON (
    echo [LOI] Khong tim thay Python.
    echo Hay cai Python 3.11+ tu https://www.python.org/downloads/
    echo Quan trong: tick "Add python.exe to PATH"
    echo Sau do mo lai CMD va chay lai file nay.
    pause
    exit /b 1
)

echo Dung Python: %PYTHON%
%PYTHON% --version
echo.

echo [1/2] Cai Nuitka + deps...
%PYTHON% -m pip install -r requirements.txt -q
%PYTHON% -m pip install nuitka ordered-set zstandard pycryptodomex -q
if errorlevel 1 (
    echo [LOI] Cai package that bai
    pause
    exit /b 1
)

echo.
echo [2/2] Bien dich onefile + tkinter...
%PYTHON% -m nuitka --onefile --windows-disable-console --enable-plugin=tk-inter --assume-yes-for-downloads --output-filename=FacebookGroupPoster.exe --output-dir=dist_nuitka --remove-output gui_app.py
if errorlevel 1 (
    echo [LOI] Nuitka build that bai. Xem log phia tren.
    pause
    exit /b 1
)

echo.
if exist "dist_nuitka\FacebookGroupPoster.exe" (
    echo BUILD NUITKA THANH CONG!
    echo File: dist_nuitka\FacebookGroupPoster.exe
    start "" "dist_nuitka\"
) else (
    echo [LOI] Khong thay file EXE sau khi build.
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
