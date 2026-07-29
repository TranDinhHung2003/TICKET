@echo off
chcp 65001 > nul
echo ============================================
echo  Facebook Group Poster - Build EXE
echo  (ban thuong — source van extract duoc)
echo ============================================
echo.
echo Muon bao ve code: chay build_secure.bat
echo Muon manh hon:    chay build_nuitka.bat
echo.

:: Kiểm tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Khong tim thay Python. Hay cai Python 3.11+
    pause
    exit /b 1
)

:: Cài dependencies nếu chưa có
echo [1/3] Cai dat dependencies...
pip install -r requirements.txt -q
pip install pyinstaller -q

echo.
echo [2/3] Build file EXE...
pyinstaller fb_poster.spec --clean --noconfirm

echo.
if exist "dist\FacebookGroupPoster.exe" (
    echo [3/3] BUILD THANH CONG!
    echo.
    echo File EXE nam tai: dist\FacebookGroupPoster.exe
    echo.
    echo Kich thuoc:
    dir "dist\FacebookGroupPoster.exe" | findstr "FacebookGroupPoster"
    echo.
    start "" "dist\"
) else (
    echo [LOI] Build that bai. Xem log tren de biet nguyen nhan.
)

pause
