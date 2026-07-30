"""
AES-256-GCM mã hóa source/bytecode khi build.
Không phải bảo mật tuyệt đối — chỉ nâng độ khó khi bị bung EXE / dịch ngược.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes

MAGIC = b"FBP1"  # Facebook Poster protected blob v1
NONCE_LEN = 12
TAG_LEN = 16


def derive_key(passphrase: str | bytes, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """PBKDF2-HMAC-SHA256 → 32-byte key."""
    if isinstance(passphrase, str):
        passphrase = passphrase.encode("utf-8")
    salt = salt or get_random_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", passphrase, salt, 200_000, dklen=32)
    return key, salt


def encrypt_bytes(plain: bytes, key: bytes) -> bytes:
    """Trả về: MAGIC | nonce(12) | tag(16) | ciphertext."""
    nonce = get_random_bytes(NONCE_LEN)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plain)
    return MAGIC + nonce + tag + ciphertext


def decrypt_bytes(blob: bytes, key: bytes) -> bytes:
    if len(blob) < 4 + NONCE_LEN + TAG_LEN or not blob.startswith(MAGIC):
        raise ValueError("Blob không hợp lệ hoặc sai định dạng bảo vệ")
    nonce = blob[4:4 + NONCE_LEN]
    tag = blob[4 + NONCE_LEN:4 + NONCE_LEN + TAG_LEN]
    ciphertext = blob[4 + NONCE_LEN + TAG_LEN:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    return cipher.decrypt_and_verify(ciphertext, tag)


def encrypt_file(src: Path, dest: Path, key: bytes) -> None:
    plain = src.read_bytes()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(encrypt_bytes(plain, key))


def obfuscate_key_bytes(key: bytes, mask: bytes | None = None) -> tuple[bytes, bytes]:
    """XOR key với mask ngẫu nhiên — nhúng vào launcher, khó copy trần."""
    mask = mask or get_random_bytes(len(key))
    if len(mask) != len(key):
        raise ValueError("mask length mismatch")
    hidden = bytes(a ^ b for a, b in zip(key, mask))
    return hidden, mask


def restore_key_bytes(hidden: bytes, mask: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(hidden, mask))


def make_build_passphrase() -> str:
    """Passphrase build — ưu tiên biến môi trường, không thì tạo mới."""
    env = os.environ.get("FB_POSTER_PROTECT_KEY", "").strip()
    if env:
        return env
    # Tạo key mới mỗi lần build (mỗi EXE một khóa)
    return get_random_bytes(24).hex()
