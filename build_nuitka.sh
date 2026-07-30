#!/bin/bash
# Build Nuitka — biên dịch Python → binary (bảo vệ mạnh)
set -e
cd "$(dirname "$0")"

echo "============================================"
echo " Facebook Group Poster - BUILD NUITKA"
echo "============================================"

pip3 install -r requirements.txt -q
pip3 install nuitka ordered-set zstandard -q

python3 -m nuitka \
  --onefile \
  --enable-plugin=tk-inter \
  --assume-yes-for-downloads \
  --output-filename=FacebookGroupPoster \
  --output-dir=dist_nuitka \
  --remove-output \
  gui_app.py

ls -lh dist_nuitka/FacebookGroupPoster* 2>/dev/null || ls -lh dist_nuitka/
