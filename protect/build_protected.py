#!/usr/bin/env python3
"""
Build bản bảo vệ:
1. Mã hóa gui_app.py (+ fb_poster/) bằng AES-256-GCM
2. Tạo bootstrap nhỏ (launcher) chứa khóa đã XOR
3. Xuất thư mục build_protected/ sẵn sàng cho PyInstaller

Chạy:
  python protect/build_protected.py
  # hoặc khóa cố định:
  set FB_POSTER_PROTECT_KEY=your-long-secret
  python protect/build_protected.py
"""
from __future__ import annotations

import marshal
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from protect.crypto_util import (  # noqa: E402
    derive_key,
    encrypt_bytes,
    make_build_passphrase,
    obfuscate_key_bytes,
)

OUT = ROOT / "build_protected"
PAYLOAD_DIR = OUT / "payloads"
BOOTSTRAP = OUT / "run_protected.py"


BOOTSTRAP_TEMPLATE = r'''# -*- coding: utf-8 -*-
"""Bootstrap bảo vệ — không chứa logic nghiệp vụ."""
from __future__ import annotations

import marshal
import sys
from pathlib import Path

# Khóa đã XOR (sinh lúc build) — không lưu plaintext
_H = bytes([@@HIDDEN@@])
_M = bytes([@@MASK@@])

_MAGIC = b"FBP1"


def _key() -> bytes:
    return bytes(a ^ b for a, b in zip(_H, _M))


def _resource(name: str) -> Path:
    """Tìm file payload trong onefile (sys._MEIPASS) hoặc cạnh script."""
    bases = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bases.append(Path(sys._MEIPASS))
    bases.append(Path(__file__).resolve().parent)
    bases.append(
        Path(sys.executable).resolve().parent
        if getattr(sys, "frozen", False)
        else Path.cwd()
    )
    for base in bases:
        p = base / "payloads" / name
        if p.is_file():
            return p
        p = base / name
        if p.is_file():
            return p
    raise FileNotFoundError(f"Không tìm thấy payload: {name}")


def _decrypt(blob: bytes) -> bytes:
    from Cryptodome.Cipher import AES

    if not blob.startswith(_MAGIC) or len(blob) < 4 + 12 + 16:
        raise RuntimeError("File bảo vệ bị hỏng hoặc đã bị sửa")
    nonce = blob[4:16]
    tag = blob[16:32]
    ct = blob[32:]
    cipher = AES.new(_key(), AES.MODE_GCM, nonce=nonce)
    try:
        return cipher.decrypt_and_verify(ct, tag)
    except Exception as exc:
        raise RuntimeError(
            "Không giải mã được mã nguồn bảo vệ.\n"
            "File EXE có thể đã bị sửa / crack."
        ) from exc


def main():
    try:
        blob = _resource("gui_app.pye").read_bytes()
    except FileNotFoundError as exc:
        raise SystemExit(
            "Thiếu payload bảo vệ (gui_app.pye).\n"
            "Hãy build bằng: python protect/build_protected.py && build_secure.bat"
        ) from exc

    raw = _decrypt(blob)
    code = marshal.loads(raw)
    g = {
        "__name__": "__main__",
        "__file__": "<protected:gui_app>",
        "__package__": None,
        "__builtins__": __builtins__,
    }
    exec(code, g)


if __name__ == "__main__":
    main()
'''


def _compile_to_marshal(py_path: Path) -> bytes:
    """Compile .py → marshal(code object)."""
    src = py_path.read_text(encoding="utf-8")
    code = compile(src, str(py_path.name), "exec", dont_inherit=True)
    return marshal.dumps(code)


def build() -> Path:
    if OUT.exists():
        shutil.rmtree(OUT)
    PAYLOAD_DIR.mkdir(parents=True)

    passphrase = make_build_passphrase()
    key, _salt = derive_key(passphrase)
    hidden, mask = obfuscate_key_bytes(key)

    gui = ROOT / "gui_app.py"
    if not gui.is_file():
        raise SystemExit("Không tìm thấy gui_app.py")
    marshaled = _compile_to_marshal(gui)
    (PAYLOAD_DIR / "gui_app.pye").write_bytes(encrypt_bytes(marshaled, key))

    pkg = ROOT / "fb_poster"
    if pkg.is_dir():
        for py in pkg.rglob("*.py"):
            out_name = py.relative_to(ROOT).as_posix().replace("/", "__") + "e"
            marshaled = _compile_to_marshal(py)
            (PAYLOAD_DIR / out_name).write_bytes(encrypt_bytes(marshaled, key))

    text = BOOTSTRAP_TEMPLATE.replace(
        "@@HIDDEN@@", ", ".join(str(b) for b in hidden)
    ).replace(
        "@@MASK@@", ", ".join(str(b) for b in mask)
    )
    BOOTSTRAP.write_text(text, encoding="utf-8")

    (OUT / "BUILD_INFO.txt").write_text(
        "Protected build generated.\n"
        "Payload: AES-256-GCM encrypted Python bytecode.\n"
        "Keep FB_POSTER_PROTECT_KEY secret if you reuse it across builds.\n"
        f"gui_app.pye size: {(PAYLOAD_DIR / 'gui_app.pye').stat().st_size} bytes\n",
        encoding="utf-8",
    )

    print("=" * 50)
    print("BUILD PROTECTED OK →", OUT)
    print("Payload:", PAYLOAD_DIR / "gui_app.pye")
    print("Bootstrap:", BOOTSTRAP)
    if not __import__("os").environ.get("FB_POSTER_PROTECT_KEY"):
        print()
        print("⚠ Khóa build đã tự sinh (mỗi lần build khác nhau).")
        print("  Để cố định khóa giữa các bản:")
        print("  set FB_POSTER_PROTECT_KEY=chuoi-bi-mat-dai-cua-ban")
    else:
        print("Đã dùng FB_POSTER_PROTECT_KEY từ môi trường.")
    print("=" * 50)
    return OUT


if __name__ == "__main__":
    build()
