@echo off
chcp 65001 > nul
echo ============================================
echo  Facebook Group Poster - BUILD BAO VE
echo  (AES-256-GCM + PyInstaller onefile)
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Khong tim thay Python 3.11+
    pause
    exit /b 1
)

echo [1/4] Cai dat dependencies build...
pip install -r requirements.txt -q
pip install pyinstaller pycryptodomex -q

echo.
echo [2/4] Ma hoa source -^> bytecode AES...
if defined FB_POSTER_PROTECT_KEY (
    echo     Dung khoa FB_POSTER_PROTECT_KEY tu moi truong
) else (
    echo     Tu sinh khoa moi ^(moi lan build khac nhau^)
)
python protect\build_protected.py
if errorlevel 1 (
    echo [LOI] Ma hoa that bai
    pause
    exit /b 1
)

echo.
echo [3/4] Dong goi EXE bao ve...
pyinstaller fb_poster_secure.spec --clean --noconfirm
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
    echo  - Source trong EXE da ma hoa AES, khong mo .py ra doc duoc
    echo  - Khong phai bao mat 100%% — van co the bi reverse neu quyet tam
    echo  - Ban manh hon: dung build_nuitka.bat ^(bien dich C^)
    echo.
    dir "dist\FacebookGroupPoster.exe" | findstr "FacebookGroupPoster"
    start "" "dist\"
) else (
    echo [LOI] Khong thay file EXE
)

pause
