#!/bin/bash
# Build bản bảo vệ AES + PyInstaller
set -e
cd "$(dirname "$0")"

echo "============================================"
echo " Facebook Group Poster - BUILD BẢO VỆ"
echo " (AES-256-GCM + PyInstaller)"
echo "============================================"

echo "[1/4] Cài dependencies..."
pip3 install -r requirements.txt -q
pip3 install pyinstaller pycryptodomex -q

echo "[2/4] Mã hóa source → bytecode AES..."
python3 protect/build_protected.py

echo "[3/4] Đóng gói binary..."
PYI="${HOME}/.local/bin/pyinstaller"
command -v pyinstaller >/dev/null && PYI="pyinstaller"
$PYI fb_poster_secure.spec --clean --noconfirm

echo "[4/4] Xong — xem dist/"
ls -lh dist/FacebookGroupPoster* 2>/dev/null || ls -lh dist/
