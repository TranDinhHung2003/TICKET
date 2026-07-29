@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo  License Server - Facebook Group Poster
echo ============================================
echo.

if not defined LICENSE_ADMIN_KEY set LICENSE_ADMIN_KEY=doi-admin-key-ngay
if not defined LICENSE_PORT set LICENSE_PORT=8787
if not defined LICENSE_BUY_CONTACT set LICENSE_BUY_CONTACT=Zalo: 0xxx - doi so cua ban

echo Admin key: %LICENSE_ADMIN_KEY%
echo Port: %LICENSE_PORT%
echo Contact page: %LICENSE_BUY_CONTACT%
echo.

python -m pip install flask requests -q
python -m license_server
pause
