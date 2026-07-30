@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo  Facebook Group Poster - BUILD BAO VE
echo  AES-256-GCM + PyInstaller onefile
echo ============================================
echo.

call :find_python
if not defined PYTHON (
    echo [LOI] Khong tim thay Python 3.11+.
    echo Cai tai: https://www.python.org/downloads/
    echo Tick: Add python.exe to PATH
    pause
    exit /b 1
)

echo Dung Python: %PYTHON%
%PYTHON% --version
echo.

echo [1/4] Cai dat dependencies build...
%PYTHON% -m pip install -r requirements.txt -q
%PYTHON% -m pip install -r requirements-build.txt -q
%PYTHON% -m pip install pyinstaller pycryptodomex -q
if errorlevel 1 (
    echo [LOI] Cai package that bai
    pause
    exit /b 1
)

echo.
echo [2/4] Ma hoa source thanh bytecode AES...
if defined FB_POSTER_PROTECT_KEY (
    echo     Dung khoa FB_POSTER_PROTECT_KEY
) else (
    echo     Tu sinh khoa moi moi lan build
)
%PYTHON% protect\build_protected.py
if errorlevel 1 (
    echo [LOI] Ma hoa that bai
    pause
    exit /b 1
)

echo.
echo [3/4] Dong goi EXE bao ve...
%PYTHON% -m PyInstaller fb_poster_secure.spec --clean --noconfirm
if errorlevel 1 (
    echo [LOI] PyInstaller that bai
    pause
    exit /b 1
)

echo.
if exist "dist\FacebookGroupPoster.exe" (
    echo [4/4] BUILD BAO VE THANH CONG!
    echo.
    echo File: dist\FacebookGroupPoster.exe
    echo.
    echo Luu y:
    echo  - Source trong EXE da ma hoa AES
    echo  - Khong phai bao mat 100%%
    echo  - Ban manh hon: chay build_nuitka.bat
    echo.
    dir "dist\FacebookGroupPoster.exe" | findstr "FacebookGroupPoster"
    start "" "dist\"
) else (
    echo [LOI] Khong thay file EXE
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
