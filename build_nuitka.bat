@echo off
chcp 65001 > nul
echo ============================================
echo  Facebook Group Poster - BUILD NUITKA
echo  (Bien dich Python -^> C/binary, kho reverse)
echo ============================================
echo.
echo Day la lop bao ve MANH nhat ^(mien phi^).
echo Lan dau co the mat 5-15 phut.
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Khong tim thay Python
    pause
    exit /b 1
)

echo [1/2] Cai Nuitka + deps...
pip install -r requirements.txt -q
pip install nuitka ordered-set zstandard pycryptodomex -q

echo.
echo [2/2] Bien dich onefile ^(tkinter^)...
python -m nuitka ^
  --onefile ^
  --windows-disable-console ^
  --enable-plugin=tk-inter ^
  --assume-yes-for-downloads ^
  --output-filename=FacebookGroupPoster.exe ^
  --output-dir=dist_nuitka ^
  --remove-output ^
  gui_app.py

echo.
if exist "dist_nuitka\FacebookGroupPoster.exe" (
    echo BUILD NUITKA THANH CONG!
    echo File: dist_nuitka\FacebookGroupPoster.exe
    start "" "dist_nuitka\"
) else (
    echo [LOI] Build Nuitka that bai — xem log tren.
)

pause
