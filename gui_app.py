"""
Facebook Group Poster — Ứng dụng GUI Desktop
Đăng bài quảng cáo lên nhiều nhóm Facebook tự động.
"""

import json
import os
import random
import re
import shutil
import sys
import threading
import time
import tkinter as tk
import uuid
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from urllib.parse import unquote

import requests

try:
    import license_client as lic
except ImportError:
    lic = None  # type: ignore

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

APP_TITLE = "Facebook Group Poster"
APP_VERSION = "1.7.3"
APP_COPYRIGHT = "© Bản quyền thuộc về TranDinhHung"
APP_SUPPORT_ZALO = "0981227703"
APP_SUPPORT_PHONE = "0981227703"
MOBILE_URL = "https://mbasic.facebook.com"

# Thư mục dữ liệu cục bộ — mở lại tool giữ cookies / nhóm / bài nháp
DATA_DIR = Path.home() / ".fb_poster"
COOKIES_FILE = DATA_DIR / "cookies.json"
LEGACY_COOKIES_FILE = Path.home() / ".fb_poster_cookies.json"
GROUPS_FILE = DATA_DIR / "groups.json"
DRAFT_FILE = DATA_DIR / "draft.json"
IMAGES_DIR = DATA_DIR / "images"
TOKENS_FILE = DATA_DIR / "tokens.json"
LICENSE_FILE = DATA_DIR / "license.json"

# Server xác minh bản quyền — đổi URL khi bạn deploy
# hoặc để khách/admin sửa trong Cài đặt.
DEFAULT_LICENSE_SERVER = os.environ.get(
    "FB_LICENSE_SERVER", "http://127.0.0.1:8787"
)


def _ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    # Migrate cookies cũ → thư mục mới
    if not COOKIES_FILE.exists() and LEGACY_COOKIES_FILE.exists():
        try:
            shutil.copy2(LEGACY_COOKIES_FILE, COOKIES_FILE)
        except Exception:
            pass


def _read_json(path: Path, default=None):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _write_json(path: Path, data) -> None:
    _ensure_data_dir()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# Theme cam – trắng
COLOR_BG = "#FFF7F0"
COLOR_PANEL = "#FFFFFF"
COLOR_CARD = "#FFFFFF"
COLOR_SURFACE = "#FFE8D6"
COLOR_ACCENT = "#F97316"
COLOR_ACCENT_LIGHT = "#FB923C"
COLOR_ACCENT2 = "#EA580C"
COLOR_TEXT = "#1C1917"
COLOR_TEXT_DIM = "#78716C"
COLOR_SUCCESS = "#16A34A"
COLOR_ERROR = "#DC2626"
COLOR_WARNING = "#EA580C"
COLOR_PENDING = "#D97706"
COLOR_BUTTON = "#F97316"
COLOR_BUTTON_HOVER = "#EA580C"
COLOR_INPUT_BG = "#FFFBF7"
COLOR_INPUT_FG = "#1C1917"
COLOR_BORDER = "#FED7AA"
COLOR_HEADER = "#F97316"
COLOR_HEADER_TEXT = "#FFFFFF"


# ──────────────────────────────────────────────────────────────────────────────
# Facebook Session Backend
# ──────────────────────────────────────────────────────────────────────────────

class FacebookBackend:
    MOBILE_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Mobile Safari/537.36"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    }
    DESKTOP_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.MOBILE_HEADERS)
        self.logged_in = False
        self._proxy = None
        self._desktop_mode = False
        self._tokens_cache: dict = {}
        self._tokens_cache_time: float = 0.0
        # post_id đã dùng trong lần chạy batch — tránh xác minh nhầm bài nhóm trước
        self._used_post_ids: set[str] = set()

    def reset_batch_state(self):
        """Gọi trước mỗi lần đăng hàng loạt — xóa cache đăng bài cũ."""
        self._used_post_ids.clear()
        self._tokens_cache.clear()
        self._tokens_cache_time = 0.0
        # Xóa tokens.json cũ — tránh tái dùng fb_dtsg từ lần chạy trước
        try:
            if TOKENS_FILE.exists():
                TOKENS_FILE.unlink()
        except Exception:
            pass

    def clear_posting_cache(self):
        """Xóa toàn bộ cache đăng bài (token/dtsg), giữ cookies đăng nhập."""
        self.reset_batch_state()
        self._tokens_cache.clear()

    def refresh_session_for_group(self, group_id: str) -> tuple[bool, str]:
        """
        Làm mới session trước mỗi nhóm:
        - Nạp lại cookies từ đĩa (bỏ state bẩn trong RAM)
        - Xóa token cache
        - Mở trang nhóm để lấy fb_dtsg mới
        """
        self._tokens_cache.clear()
        self._tokens_cache_time = 0.0

        # Reload cookies sạch từ file đã lưu
        cookie_path = COOKIES_FILE if COOKIES_FILE.exists() else LEGACY_COOKIES_FILE
        if cookie_path.exists():
            try:
                data = json.loads(cookie_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data.get("c_user"):
                    self._apply_cookies(data)
            except Exception as exc:
                return False, f"Không nạp lại cookies: {exc}"

        self._use_desktop_session()
        try:
            # Làm mới cookie session với Facebook
            self.session.get("https://www.facebook.com/", timeout=12)
            time.sleep(0.5)
            resp = self.session.get(
                f"https://www.facebook.com/groups/{group_id}",
                timeout=15,
            )
            tokens = self._extract_fb_tokens(resp.text)
            if tokens.get("fb_dtsg"):
                self._tokens_cache = {
                    **tokens,
                    "__user": self._get_user_id(),
                }
                self._tokens_cache_time = time.time()
                return True, "ok"
            return False, "Không lấy được fb_dtsg mới từ trang nhóm"
        except Exception as exc:
            return False, str(exc)

    def set_proxy(self, proxy: str):
        """Đặt proxy (http://host:port hoặc socks5://host:port)."""
        if proxy:
            self._proxy = {"http": proxy, "https": proxy}
            self.session.proxies.update(self._proxy)
        else:
            self._proxy = None
            self.session.proxies.clear()

    def test_connection(self) -> tuple[bool, str]:
        """Kiểm tra kết nối tới Facebook."""
        test_urls = [
            "https://mbasic.facebook.com/",
            "https://m.facebook.com/",
            "https://www.facebook.com/",
        ]
        for url in test_urls:
            try:
                r = self.session.get(url, timeout=10)
                if r.status_code < 500:
                    return True, url
            except requests.exceptions.ProxyError:
                return False, "proxy_error"
            except requests.exceptions.SSLError:
                return False, "ssl_error"
            except Exception:
                continue
        return False, "unreachable"

    def _use_desktop_session(self):
        """Dùng User-Agent desktop — bắt buộc khi cookies lấy từ Chrome."""
        self.session.headers.clear()
        self.session.headers.update(self.DESKTOP_HEADERS)
        self._desktop_mode = True

    def _use_mobile_session(self):
        self.session.headers.clear()
        self.session.headers.update(self.MOBILE_HEADERS)
        self._desktop_mode = False

    def _get_user_id(self) -> str:
        for c in self.session.cookies:
            if c.name == "c_user":
                return c.value
        return ""

    def _apply_cookies(self, cookies: dict) -> bool:
        """Gắn cookies vào session cho mọi domain Facebook."""
        self.session.cookies.clear()
        for name, value in cookies.items():
            value = unquote(str(value).strip())
            for domain in (".facebook.com", "www.facebook.com", ".www.facebook.com"):
                self.session.cookies.set(name, value, domain=domain, path="/")
        if "c_user" in cookies:
            self._use_desktop_session()
            self.logged_in = True
            return True
        self.logged_in = False
        return False

    def verify_session(self) -> tuple[bool, str]:
        """Kiểm tra cookies còn hoạt động không."""
        uid = self._get_user_id()
        if not uid:
            return False, "Thiếu cookie c_user — export lại cookies từ Chrome"

        self._use_desktop_session()
        try:
            resp = self.session.get(
                "https://www.facebook.com/",
                timeout=20,
                allow_redirects=True,
            )
            url_lower = resp.url.lower()
            text_head = resp.text[:3000].lower()

            if "checkpoint" in url_lower or "checkpoint" in text_head:
                return False, "Tài khoản cần xác minh bảo mật trên trình duyệt"
            if ("login" in url_lower and "login.php" in url_lower) or (
                "name=\"email\"" in text_head and "name=\"pass\"" in text_head
            ):
                return False, "Cookies đã hết hạn — lấy cookies mới từ Chrome"
            if "lỗi" in resp.text[:500].lower() and len(resp.text) < 5000:
                return False, "Facebook trả về trang lỗi — thử export cookies lại"

            return True, uid
        except requests.exceptions.ConnectionError:
            return False, "Không kết nối được Facebook — kiểm tra mạng/VPN"
        except Exception as exc:
            return False, f"Lỗi kiểm tra: {exc}"

    def load_cookies(self, path: Path) -> bool:
        if not path.exists():
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        return self._apply_cookies(data)

    def save_cookies(self, path: Path | None = None):
        _ensure_data_dir()
        path = path or COOKIES_FILE
        cookies = {c.name: c.value for c in self.session.cookies}
        # Gộp cookie cùng tên (ưu tiên bản mới)
        merged = {}
        for c in self.session.cookies:
            merged[c.name] = c.value
        cookies = merged or cookies
        path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
        # Giữ bản legacy để tương thích
        try:
            LEGACY_COOKIES_FILE.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
        except Exception:
            pass

    def save_tokens(self, extra: dict | None = None):
        """Lưu fb_dtsg / lsd gần nhất để mở tool nhanh hơn."""
        data = dict(self._tokens_cache or {})
        if extra:
            data.update(extra)
        data["saved_at"] = time.time()
        data["user_id"] = self._get_user_id()
        _write_json(TOKENS_FILE, {k: v for k, v in data.items() if v})

    def load_saved_tokens(self) -> dict:
        data = _read_json(TOKENS_FILE, {}) or {}
        # Token cũ hơn 2h coi như hết hạn
        if time.time() - float(data.get("saved_at") or 0) > 7200:
            return {}
        self._tokens_cache = {k: v for k, v in data.items() if k not in ("saved_at",)}
        self._tokens_cache_time = float(data.get("saved_at") or time.time())
        return self._tokens_cache

    def set_cookies_from_string(self, cookie_str: str) -> bool:
        cookies = {}
        for part in cookie_str.split(";"):
            part = part.strip()
            if "=" in part:
                name, _, value = part.partition("=")
                cookies[name.strip()] = value.strip()
        return self._apply_cookies(cookies)

    def login(self, email: str, password: str) -> tuple[bool, str]:
        try:
            # Thử nhiều endpoint mobile của Facebook
            login_endpoints = [
                "https://mbasic.facebook.com/login/",
                "https://m.facebook.com/login/",
                "https://mbasic.facebook.com/",
                "https://www.facebook.com/login/",
            ]

            html = ""
            form_action = ""
            last_exc = None
            for endpoint in login_endpoints:
                try:
                    resp = self.session.get(endpoint, timeout=20)
                    content = resp.text
                    if "login" in content.lower() or "email" in content.lower() or "pass" in content.lower():
                        html = content
                        m = re.search(
                            r'<form[^>]+action=["\']([^"\']*login[^"\']*)["\']',
                            html, re.I
                        )
                        if m:
                            form_action = m.group(1)
                        break
                except requests.exceptions.ProxyError as e:
                    last_exc = f"Lỗi proxy: {e}"
                    break
                except requests.exceptions.ConnectionError as e:
                    last_exc = f"Không kết nối được: {e}"
                    continue
                except requests.exceptions.Timeout:
                    last_exc = "Timeout kết nối"
                    continue
                except Exception as e:
                    last_exc = str(e)
                    continue

            if not html:
                msg = last_exc or "Không rõ"
                return False, (
                    f"Không thể kết nối tới Facebook.\n\n"
                    f"Chi tiết: {msg}\n\n"
                    f"Giải pháp:\n"
                    f"• Kiểm tra mạng Internet\n"
                    f"• Dùng VPN nếu Facebook bị chặn\n"
                    f"• Hoặc dùng tab 'Nhập Cookies' (không cần đăng nhập)"
                )

            form_data = self._extract_form_fields(html)

            # Thêm email/pass vào form
            form_data["email"] = email
            form_data["pass"] = password

            # Xác định URL submit
            if form_action:
                if form_action.startswith("http"):
                    submit_url = form_action
                else:
                    submit_url = f"{MOBILE_URL}{form_action}"
            else:
                submit_url = f"{MOBILE_URL}/login/device-based/regular/login/?refsrc=deprecated"

            login_resp = self.session.post(
                submit_url,
                data=form_data,
                allow_redirects=True,
                timeout=12,
            )

            # Kiểm tra checkpoint/2FA
            if "checkpoint" in login_resp.url or "checkpoint" in login_resp.text:
                return False, (
                    "Facebook yêu cầu xác minh bảo mật (checkpoint)!\n\n"
                    "Hãy dùng tab 'Nhập Cookies' thay thế:\n"
                    "1. Đăng nhập Facebook trên Chrome\n"
                    "2. Cài extension 'Cookie-Editor'\n"
                    "3. Export → Header String → Dán vào tab Cookies"
                )

            # Kiểm tra đăng nhập thành công
            cookies_dict = {c.name: c.value for c in self.session.cookies}
            if "c_user" in cookies_dict or self._check_logged_in(login_resp.text):
                self.logged_in = True
                return True, "Đăng nhập thành công!"

            # Kiểm tra thông báo lỗi từ Facebook
            body_l = login_resp.text.lower()
            wrong_pw = any(
                k in body_l
                for k in (
                    "password you entered is incorrect",
                    "incorrect password",
                    "wrong password",
                    "mật khẩu bạn đã nhập không chính xác",
                    "mật khẩu không đúng",
                    "sai mật khẩu",
                    "login_error",
                    "identifiermismatch",
                    "invalid username or password",
                    "email hoặc số điện thoại bạn nhập không khớp",
                    "the email or mobile number you entered isn't connected",
                    "không khớp với tài khoản nào",
                )
            )
            if wrong_pw or re.search(
                r"(incorrect|wrong).{0,20}password|mật khẩu.{0,30}(sai|không đúng|không chính xác)",
                login_resp.text,
                re.I,
            ):
                return False, (
                    "Sai tài khoản hoặc mật khẩu.\n\n"
                    "Kiểm tra lại email/SĐT và mật khẩu Facebook.\n"
                    "Hoặc dùng tab 'Nhập Cookies' (khuyến nghị)."
                )

            error_patterns = [
                r'id="error_box"[^>]*>([^<]+)',
                r'class="[^"]*error[^"]*"[^>]*>\s*<[^>]+>\s*([^<]{5,100})',
                r'The password[^<]+',
                r'Mật khẩu[^<]+không đúng[^<]*',
            ]
            for pat in error_patterns:
                m = re.search(pat, login_resp.text, re.I)
                if m:
                    snippet = re.sub(r"<[^>]+>", "", m.group(0))[:120]
                    low = snippet.lower()
                    if any(k in low for k in ("password", "mật khẩu", "incorrect", "sai")):
                        return False, (
                            "Sai tài khoản hoặc mật khẩu.\n\n"
                            "Kiểm tra lại email/SĐT và mật khẩu Facebook."
                        )
                    return False, f"Lỗi: {snippet}"

            return False, (
                "Sai tài khoản hoặc mật khẩu — hoặc Facebook chặn đăng nhập tự động.\n\n"
                "Thử lại đúng email/mật khẩu, hoặc dùng tab 'Nhập Cookies'."
            )
        except Exception as exc:
            return False, f"Lỗi kết nối: {exc}"

    def _extract_form_fields(self, html: str) -> dict:
        """Trích xuất tất cả input fields từ HTML (mọi thứ tự thuộc tính)."""
        fields = {}
        # Tìm tất cả thẻ <input ...>
        for input_tag in re.finditer(r'<input\b([^>]*?)/?>', html, re.I | re.S):
            attrs_str = input_tag.group(1)
            # Lấy tất cả cặp key=value trong thẻ
            attrs = {}
            for m in re.finditer(r'\b(\w+)\s*=\s*["\']([^"\']*)["\']', attrs_str):
                attrs[m.group(1).lower()] = m.group(2)
            name = attrs.get("name", "")
            value = attrs.get("value", "")
            input_type = attrs.get("type", "text").lower()
            # Bỏ qua submit, button, image, reset
            if name and input_type not in ("submit", "button", "image", "reset"):
                fields[name] = value
        return fields

    def _check_logged_in(self, html: str) -> bool:
        return any(x in html for x in ["logout", "c_user", "mbasic_logout", "log_out"])

    def get_profile_name(self) -> str:
        uid = self._get_user_id()
        if not uid:
            return "Chưa đăng nhập"

        ok, _ = self.verify_session()
        if not ok:
            return f"UID {uid} (cookies hết hạn?)"

        self._use_desktop_session()
        for url in (
            f"https://www.facebook.com/profile.php?id={uid}",
            "https://www.facebook.com/me",
        ):
            try:
                resp = self.session.get(url, timeout=15, allow_redirects=True)
                m = re.search(r"<title>([^<|]+)", resp.text)
                if m:
                    name = m.group(1).strip()
                    bad = {"lỗi", "error", "facebook", "log in", "đăng nhập", "login"}
                    if name.lower() not in bad and len(name) > 1:
                        return name
            except Exception:
                continue
        return f"Tài khoản {uid}"

    def scan_groups(self, progress_cb=None) -> list[dict]:
        """Quét nhóm — ưu tiên giao diện desktop (cookies Chrome)."""
        groups: list[dict] = []
        seen: set[str] = set()

        ok, msg = self.verify_session()
        if not ok:
            if progress_cb:
                progress_cb(f"❌ {msg}")
            return groups

        self._use_desktop_session()

        # ── Bước 1: Trang desktop (cookies Chrome) ────────────────────────
        desktop_urls = [
            "https://www.facebook.com/groups/joins/",
            "https://www.facebook.com/groups/feed/",
            "https://www.facebook.com/bookmarks/groups/",
            "https://www.facebook.com/groups/",
        ]
        raw_pages: list[str] = []

        for url in desktop_urls:
            try:
                if progress_cb:
                    progress_cb(f"🔍 Đang quét: {url}")
                resp = self.session.get(url, timeout=12, allow_redirects=True)
                html = resp.text
                raw_pages.append(html)

                # Phân trang cursor trong JSON
                cursors = re.findall(r'"end_cursor"\s*:\s*"([^"]+)"', html)
                for cursor in cursors[:3]:
                    try:
                        r2 = self.session.get(
                            url,
                            params={"cursor": cursor},
                            timeout=20,
                        )
                        raw_pages.append(r2.text)
                    except Exception:
                        pass
            except Exception as exc:
                if progress_cb:
                    progress_cb(f"⚠️ {url}: {exc}")

        if progress_cb:
            progress_cb("🔍 Trích xuất nhóm từ dữ liệu trang…")

        for html in raw_pages:
            self._extract_groups_from_json(html, groups, seen)
            self._extract_groups_from_html(html, groups, seen)

        # ── Bước 2: GraphQL nội bộ ────────────────────────────────────────
        if not groups:
            if progress_cb:
                progress_cb("🔍 Thử GraphQL API…")
            gql = self._scan_groups_graphql(progress_cb)
            for g in gql:
                if g["id"] not in seen:
                    seen.add(g["id"])
                    groups.append(g)

        # ── Bước 3: Fallback mobile ───────────────────────────────────────
        if not groups:
            if progress_cb:
                progress_cb("🔍 Thử giao diện mobile…")
            self._use_mobile_session()
            mobile_urls = [
                f"{MOBILE_URL}/groups/?seemore=1",
                f"{MOBILE_URL}/groups/",
                "https://m.facebook.com/groups/",
            ]
            for url in mobile_urls:
                try:
                    resp = self.session.get(url, timeout=12)
                    self._extract_groups_from_json(resp.text, groups, seen)
                    self._extract_groups_from_html(resp.text, groups, seen)
                except Exception:
                    pass
            self._use_desktop_session()

        return groups

    def _decode_json_str(self, s: str) -> str:
        """Giải mã chuỗi JSON (\\uXXXX, \\/, ...)."""
        try:
            return bytes(s, "utf-8").decode("unicode_escape")
        except Exception:
            return s.replace("\\/", "/")

    def _extract_groups_from_json(self, html: str, groups: list, seen: set):
        """Trích xuất nhóm từ JSON nhúng trong HTML Facebook."""
        json_patterns = [
            # id trước name
            r'"id"\s*:\s*"(\d{8,})"\s*,\s*"name"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"__typename"\s*:\s*"Group"',
            # name trước id
            r'"name"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"id"\s*:\s*"(\d{8,})"\s*,\s*"__typename"\s*:\s*"Group"',
            # group object
            r'"group"\s*:\s*\{\s*"id"\s*:\s*"(\d+)"\s*,\s*"name"\s*:\s*"((?:[^"\\]|\\.)*)"',
            # url kèm tên
            r'"url"\s*:\s*"(?:https?:\\?/\\?/)?(?:www\.)?facebook\.com/groups/(\d+)/?"\s*,\s*"name"\s*:\s*"((?:[^"\\]|\\.)*)"',
        ]

        for i, pattern in enumerate(json_patterns):
            for m in re.finditer(pattern, html):
                if i == 1:
                    name, gid = m.group(1), m.group(2)
                else:
                    gid, name = m.group(1), m.group(2)
                name = self._decode_json_str(name).strip()
                if gid not in seen and self._valid_name(name):
                    seen.add(gid)
                    groups.append({"id": gid, "name": name})

        # Tìm mọi group ID trong HTML (kể cả escaped \/groups\/)
        for m in re.finditer(r'(?:/|\\/)(?:groups|groups\\/)(\d{8,})', html):
            gid = m.group(1)
            if gid in seen:
                continue
            start = max(0, m.start() - 200)
            end = min(len(html), m.end() + 400)
            snippet = html[start:end]
            name_m = re.search(
                r'"name"\s*:\s*"((?:[^"\\]|\\.){3,80})"', snippet
            )
            if name_m:
                name = self._decode_json_str(name_m.group(1)).strip()
                if self._valid_name(name):
                    seen.add(gid)
                    groups.append({"id": gid, "name": name})

    def _extract_groups_from_html(self, html: str, groups: list, seen: set):
        """Trích xuất ID + tên nhóm từ HTML với nhiều pattern khác nhau."""

        # Pattern 1: link /groups/ID/  kèm tên trong thẻ tiếp theo
        for m in re.finditer(
            r'href="(?:https?://[^/]+)?/groups/(\d+)/?[^"]*"[^>]*>([^<]{2,80})<',
            html, re.I
        ):
            gid, name = m.group(1), m.group(2).strip()
            name = re.sub(r'\s+', ' ', name).strip()
            if gid not in seen and self._valid_name(name):
                seen.add(gid)
                groups.append({"id": gid, "name": name})

        # Pattern 2: link /groups/ID rồi tên nằm bên trong vài thẻ sau
        for m in re.finditer(
            r'href="(?:https?://[^/]+)?/groups/(\d+)/?[^"]*"', html, re.I
        ):
            gid = m.group(1)
            if gid in seen:
                continue
            # Tìm text gần nhất sau href này
            snippet = html[m.start():m.start() + 400]
            texts = re.findall(r'>([^<]{3,80})<', snippet)
            for t in texts:
                t = re.sub(r'\s+', ' ', t).strip()
                if self._valid_name(t):
                    seen.add(gid)
                    groups.append({"id": gid, "name": t})
                    break

        # Pattern 3: data-groupid / data-group-id attribute
        for m in re.finditer(
            r'data-(?:group-?id|id)=["\'](\d{8,})["\'][^>]*>([^<]{2,80})<', html, re.I
        ):
            gid, name = m.group(1), m.group(2).strip()
            if gid not in seen and self._valid_name(name):
                seen.add(gid)
                groups.append({"id": gid, "name": name})

    def _valid_name(self, name: str) -> bool:
        """Kiểm tra tên nhóm có hợp lệ không."""
        if not name or len(name) < 3 or len(name) > 100:
            return False
        # Loại bỏ các chuỗi không phải tên nhóm
        skip = {"xem thêm", "see more", "like", "comment", "share", "đăng ký",
                 "groups", "bình luận", "thích", "chia sẻ", "tham gia", "join",
                 "home", "trang chủ", "tin tức", "news feed"}
        if name.lower() in skip:
            return False
        if name.startswith("http") or name.startswith("/"):
            return False
        # Phải có ít nhất 1 chữ cái
        if not re.search(r'[a-zA-ZÀ-ỹ]', name):
            return False
        return True

    def _extract_fb_tokens(self, html: str) -> dict:
        tokens: dict[str, str] = {}
        token_patterns = {
            "fb_dtsg": [
                r'"DTSGInitData",\[\],\{"token":"([^"]+)"',
                r'name="fb_dtsg"\s+value="([^"]+)"',
                r'"fb_dtsg"\s*:\s*"([^"]+)"',
            ],
            "lsd": [
                r'"LSD",\[\],\{"token":"([^"]+)"',
                r'name="lsd"\s+value="([^"]+)"',
            ],
            "jazoest": [r'name="jazoest"\s+value="(\d+)"', r'jazoest=(\d+)'],
        }
        for key, patterns in token_patterns.items():
            for pat in patterns:
                m = re.search(pat, html)
                if m:
                    tokens[key] = m.group(1)
                    break
        return tokens

    def _scan_groups_graphql(self, progress_cb=None) -> list[dict]:
        """Lấy nhóm qua GraphQL nội bộ Facebook."""
        groups: list[dict] = []
        seen: set[str] = set()
        uid = self._get_user_id()
        if not uid:
            return groups

        self._use_desktop_session()
        try:
            if progress_cb:
                progress_cb("🔍 Lấy token GraphQL…")
            resp = self.session.get(
                "https://www.facebook.com/groups/joins/",
                timeout=12,
            )
            html = resp.text
            self._extract_groups_from_json(html, groups, seen)
            if groups:
                return groups

            tokens = self._extract_fb_tokens(html)
            if not tokens.get("fb_dtsg"):
                return groups

            if progress_cb:
                progress_cb("🔍 Gọi GraphQL lấy danh sách nhóm…")

            # doc_id tìm trong trang (Facebook nhúng sẵn)
            doc_ids = re.findall(r'"doc_id"\s*:\s*"(\d{10,})"', html)
            if not doc_ids:
                doc_ids = ["23474203845809271"]  # fallback phổ biến

            for doc_id in doc_ids[:5]:
                try:
                    payload = {
                        "fb_dtsg": tokens["fb_dtsg"],
                        "fb_api_caller_class": "RelayModern",
                        "fb_api_req_friendly_name": "GroupsCometJoinsRootQuery",
                        "variables": json.dumps({"count": 50, "scale": 1}),
                        "doc_id": doc_id,
                    }
                    if tokens.get("lsd"):
                        payload["lsd"] = tokens["lsd"]
                    if tokens.get("jazoest"):
                        payload["jazoest"] = tokens["jazoest"]

                    gql_resp = self.session.post(
                        "https://www.facebook.com/api/graphql/",
                        data=payload,
                        headers={
                            **self.DESKTOP_HEADERS,
                            "Content-Type": "application/x-www-form-urlencoded",
                            "X-FB-Friendly-Name": "GroupsCometJoinsRootQuery",
                        },
                        timeout=12,
                    )
                    self._extract_groups_from_json(gql_resp.text, groups, seen)
                    if groups:
                        break
                except Exception:
                    continue

            # Fallback: profile groups page
            if not groups:
                url = f"https://www.facebook.com/{uid}/groups"
                if progress_cb:
                    progress_cb(f"🔍 Quét profile: {url}")
                r2 = self.session.get(url, timeout=12)
                self._extract_groups_from_json(r2.text, groups, seen)
                self._extract_groups_from_html(r2.text, groups, seen)

        except Exception:
            pass
        return groups

    def _get_tokens(self, force_refresh: bool = False) -> dict:
        """Lấy fb_dtsg và các token cần thiết (cache 5 phút)."""
        if (
            not force_refresh
            and self._tokens_cache
            and time.time() - self._tokens_cache_time < 300
        ):
            return self._tokens_cache

        self._use_desktop_session()
        uid = self._get_user_id()
        for url in (
            "https://www.facebook.com/",
            "https://www.facebook.com/groups/feed/",
        ):
            try:
                resp = self.session.get(url, timeout=20)
                tokens = self._extract_fb_tokens(resp.text)
                if tokens.get("fb_dtsg") and uid:
                    tokens["__user"] = uid
                    tokens["av"] = uid
                    self._tokens_cache = tokens
                    self._tokens_cache_time = time.time()
                    return tokens
            except Exception:
                continue
        return {}

    def post_to_group(
        self, group_id: str, message: str, image_path: str = None, progress_cb=None
    ) -> tuple[str, str]:
        """
        Đăng bài vào nhóm.

        Returns:
            (status, message) với status = published | pending | failed
        """
        def _prog(msg: str):
            if progress_cb:
                try:
                    progress_cb(msg)
                except Exception:
                    pass

        self._tokens_cache.clear()
        self._tokens_cache_time = 0.0

        # Làm mới cookies + fb_dtsg từ đúng nhóm (tránh data cũ)
        ok_refresh, refresh_msg = self.refresh_session_for_group(group_id)
        if not ok_refresh:
            _prog(f"Cảnh báo làm mới session: {refresh_msg}")

        marker = self._extract_verify_marker(message)
        if not marker:
            marker = uuid.uuid4().hex[:6]
            message = f"{message.rstrip()}\n\nFPV{marker}"

        if image_path and Path(image_path).is_file():
            _prog(f"Đăng kèm ảnh: {self._safe_image_filename(image_path)}")

        # Nhóm đầu: GraphQL. Nhóm 2+: mbasic trước (GraphQL hay trả id giả từ cache)
        methods = [
            ("GraphQL", self._post_via_graphql),
            ("mbasic", self._post_via_mobile),
            ("composer", self._post_via_composer_direct),
            ("m.facebook", self._post_via_m_composer),
            ("Ajax", self._post_via_ajax_feed),
        ]
        if self._used_post_ids:
            methods = [
                ("mbasic", self._post_via_mobile),
                ("GraphQL", self._post_via_graphql),
                ("composer", self._post_via_composer_direct),
                ("m.facebook", self._post_via_m_composer),
                ("Ajax", self._post_via_ajax_feed),
            ]

        last_err = "Không thể đăng bài"
        for name, method in methods:
            _prog(f"Thử {name}…")
            try:
                status, msg = method(group_id, message, image_path)
            except Exception as exc:
                status, msg = "failed", str(exc)

            if status not in ("published", "pending"):
                last_err = msg or f"{name} thất bại"
                _prog(f"{name}: {last_err}")
                continue

            post_id = None
            m = re.search(
                r"(?:post[:\s]*|Đăng[^(]*\()([0-9]{8,}|Uzpf[A-Za-z0-9_-]{8,})",
                msg,
            )
            if not m:
                m = re.search(r"\(([0-9]{8,}|Uzpf[A-Za-z0-9_-]{8,})\)", msg)
            if m:
                post_id = m.group(1)
            if post_id and (
                str(post_id) == str(group_id) or str(post_id) in self._used_post_ids
            ):
                _prog(f"{name}: post_id trùng/đã dùng ({str(post_id)[:18]}) → bỏ qua")
                last_err = f"{name} trả post_id cũ"
                continue

            _prog(
                f"{name} báo {status}"
                + (f" (post {post_id[:18]}…)" if post_id else "")
                + " → kiểm tra permalink…"
            )

            verified = None
            try:
                verified = self._verify_post_status(
                    group_id,
                    message,
                    post_id=post_id,
                    claimed=status,
                    marker=marker,
                )
            except Exception as exc:
                _prog(f"Xác minh lỗi: {exc}")
                verified = None

            if verified in ("published", "pending"):
                if post_id:
                    self._used_post_ids.add(str(post_id))
                self._used_post_ids.add(f"marker:{marker}")
                label = (
                    "Đã đăng lên nhóm"
                    if verified == "published"
                    else "Đang chờ admin duyệt"
                )
                extra = f" (FPV{marker})"
                if post_id:
                    extra = f" (post: {post_id[:24]})"
                _prog(f"{name}: {label}{extra}")
                # Không ghi tokens.json giữa batch — tránh dtsg cũ làm hỏng nhóm sau
                return verified, f"{label}{extra}"

            last_err = (
                f"{name} báo OK nhưng permalink/hàng chờ không xác nhận được bài"
                + (f" — {msg}" if msg else "")
            )
            _prog(f"⚠ {last_err}")

        return "failed", last_err

    @staticmethod
    def _extract_verify_marker(message: str) -> str | None:
        m = re.search(r"(?i)(?:\[FPV-([a-z0-9]{6})\]|FPV([a-z0-9]{6}))\b", message or "")
        if not m:
            return None
        return (m.group(1) or m.group(2) or "").lower() or None

    @staticmethod
    def _strip_non_content_html(html: str) -> str:
        if not html:
            return ""
        out = re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
        out = re.sub(r"<style\b[^>]*>.*?</style>", " ", out, flags=re.I | re.S)
        out = re.sub(r"<textarea\b[^>]*>.*?</textarea>", " ", out, flags=re.I | re.S)
        out = re.sub(r"<input\b[^>]*>", " ", out, flags=re.I)
        out = re.sub(r"<select\b[^>]*>.*?</select>", " ", out, flags=re.I | re.S)
        out = re.sub(r'style\s*=\s*"[^"]*"', " ", out, flags=re.I)
        out = re.sub(r"style\s*=\s*'[^']*'", " ", out, flags=re.I)
        return out

    def _message_anchors(self, message: str, marker: str | None = None) -> list[str]:
        """
        Chỉ dùng mã FPV + dòng unique — KHÔNG dùng đoạn đầu bài chung
        (đoạn chung dễ khớp nhầm banner/composer → báo CHỜ DUYỆT giả).
        """
        anchors: list[str] = []
        mk = (marker or self._extract_verify_marker(message) or "").lower()
        if mk:
            anchors.append(f"fpv{mk}")
        low = (message or "").lower()
        m = re.search(r"(\d{6}-\d+/\d{4}\s+fpv[a-z0-9]{6})", low)
        if m:
            anchors.append(m.group(1))
        # Dòng spin unique nếu có mã sp-
        m2 = re.search(r"(sp-[a-z0-9]{5})", low)
        if m2:
            anchors.append(m2.group(1))
        return list(dict.fromkeys(a for a in anchors if a))

    def _page_unavailable(self, html: str, final_url: str) -> bool:
        low = (html or "")[:3500].lower()
        final = (final_url or "").lower()
        if "login" in final and "login.php" in final:
            return True
        return any(
            x in low
            for x in (
                "content isn't available",
                "this content isn't available",
                "nội dung không khả dụng",
                "không khả dụng",
                "page isn't available",
                "the link you followed may be broken",
            )
        )

    def _verify_permalink(
        self, group_id: str, post_id: str, anchors: list[str]
    ) -> str | None:
        """
        Chỉ OK khi:
        - URL cuối cùng vẫn đúng group_id
        - post_id có trong URL (không chỉ nằm lung tung trong HTML)
        - Thấy mã FPV/sp- của ĐÚNG bài này trong nội dung
        """
        if not post_id or not str(post_id).isdigit():
            return None
        if not anchors:
            return None
        gid = str(group_id)
        pid = str(post_id)
        candidates = [
            f"https://www.facebook.com/groups/{gid}/posts/{pid}",
            f"https://www.facebook.com/groups/{gid}/permalink/{pid}/",
            f"https://mbasic.facebook.com/story.php?story_fbid={pid}&id={gid}",
            f"https://m.facebook.com/story.php?story_fbid={pid}&id={gid}",
            f"https://mbasic.facebook.com/groups/{gid}/permalink/{pid}/",
        ]
        self._use_desktop_session()
        for url in candidates:
            try:
                if "mbasic." in url or "m.facebook." in url:
                    saved = dict(self.session.headers)
                    self._use_mobile_session()
                    try:
                        resp = self.session.get(url, timeout=14, allow_redirects=True)
                    finally:
                        self.session.headers.clear()
                        self.session.headers.update(saved)
                        if self._desktop_mode:
                            self._use_desktop_session()
                else:
                    resp = self.session.get(url, timeout=14, allow_redirects=True)
                if resp.status_code >= 400:
                    continue
                final = resp.url
                html = resp.text
                if self._page_unavailable(html, final):
                    continue
                final_l = final.lower()
                other = re.search(r"/groups/(\d+)", final_l)
                if other and other.group(1) != gid:
                    continue
                on_group = (
                    f"/groups/{gid}" in final_l
                    or f"id={gid}" in final_l
                )
                if not on_group:
                    continue
                # post_id phải nằm trong URL permalink (tránh khớp số random trong HTML)
                pid_in_url = (
                    f"/{pid}" in final_l
                    or f"story_fbid={pid}" in final_l
                    or f"story_fbid%3d{pid}" in final_l
                )
                if not pid_in_url:
                    continue

                cleaned = self._strip_non_content_html(html).lower()
                # BẮT BUỘC thấy anchor FPV của bài này
                if not any(a in cleaned for a in anchors):
                    continue

                if (
                    "pending" in final_l
                    or "/pending" in final_l
                    or "pending_approval" in cleaned
                    or "awaiting approval" in cleaned
                ):
                    return "pending"
                return "published"
            except Exception:
                continue
        return None

    def _verify_pending_or_feed(
        self, group_id: str, anchors: list[str], claimed: str | None
    ) -> str | None:
        """Chỉ nhận khi thấy FPV của bài này trên pending/feed (đã bỏ textarea)."""
        if not anchors:
            return None
        # Chỉ tin anchor kiểu fpv/sp — bỏ anchor nội dung chung nếu lỡ có
        strict = [a for a in anchors if a.startswith("fpv") or a.startswith("sp-")]
        if not strict:
            return None
        gid = str(group_id)
        checks = [
            ("pending", f"https://mbasic.facebook.com/groups/{gid}/pending"),
            ("pending", f"https://m.facebook.com/groups/{gid}/pending"),
            ("feed", f"https://mbasic.facebook.com/groups/{gid}"),
        ]
        for kind, url in checks:
            try:
                saved = dict(self.session.headers)
                self._use_mobile_session()
                try:
                    resp = self.session.get(url, timeout=12, allow_redirects=True)
                finally:
                    self.session.headers.clear()
                    self.session.headers.update(saved)
                    if self._desktop_mode:
                        self._use_desktop_session()
                if resp.status_code >= 400:
                    continue
                final = resp.url.lower()
                if "login" in final or f"/groups/{gid}" not in final:
                    continue
                cleaned = self._strip_non_content_html(resp.text).lower()
                if any(a in cleaned for a in strict):
                    if kind == "pending" or "pending" in final:
                        return "pending"
                    return "published"
            except Exception:
                continue
        return None

    def _verify_post_status(
        self,
        group_id: str,
        message: str,
        post_id: str | None = None,
        claimed: str | None = None,
        marker: str | None = None,
        before_pending: str | None = None,
        before_feed: str | None = None,
    ) -> str | None:
        """
        Ưu tiên: permalink post_id đúng nhóm.
        Phụ: thấy nội dung/marker trên pending/feed.
        """
        marker = (marker or self._extract_verify_marker(message) or "").lower()
        anchors = self._message_anchors(message, marker)

        for attempt in range(5):
            if attempt:
                time.sleep(2.0)
            else:
                time.sleep(1.2)

            if post_id:
                found = self._verify_permalink(group_id, post_id, anchors)
                if found:
                    return found

            found = self._verify_pending_or_feed(group_id, anchors, claimed)
            if found:
                return found
        return None

    @staticmethod
    def _safe_image_filename(image_path: str) -> str:
        """Tên file ASCII sạch — dấu cách/unicode dễ làm FB từ chối upload."""
        path = Path(image_path)
        safe = re.sub(r"[^\w.\-]+", "_", path.name) or f"photo_{uuid.uuid4().hex[:8]}.jpg"
        if not re.search(r"\.(jpe?g|png|gif|webp)$", safe, re.I):
            safe += ".jpg"
        return safe

    def _upload_photo(
        self, image_path: str, tokens: dict, group_id: str | None = None
    ) -> str | None:
        """Upload ảnh, trả về photo_id nếu thành công."""
        path = Path(image_path)
        if not path.is_file():
            return None
        uid = tokens.get("__user") or self._get_user_id()
        fb_dtsg = tokens.get("fb_dtsg")
        if not uid or not fb_dtsg:
            return None

        safe_name = self._safe_image_filename(image_path)
        waterfall = uuid.uuid4().hex
        session_id = str(uuid.uuid4())

        self._use_desktop_session()
        upload_urls = [
            "https://www.facebook.com/ajax/react_composer/attachments/photo/upload/",
            "https://www.facebook.com/ajax/react_composer/attachments/photo/upload",
            "https://upload.facebook.com/ajax/react_composer/attachments/photo/upload/",
            "https://upload.facebook.com/ajax/react_composer/attachments/photo/upload",
            f"https://upload.facebook.com/ajax/react_composer/attachments/photo/upload?__a=1&fb_dtsg={fb_dtsg}",
            "https://www.facebook.com/ajax/composer/attachment/photo/upload",
            "https://www.facebook.com/ajax/ufi/upload/",
        ]
        target = str(group_id) if group_id else uid
        base_data = {
            "fb_dtsg": fb_dtsg,
            "__user": uid,
            "__a": "1",
            "source": "8",
            "profile_id": uid,
            "target_id": target,
            "waterfallxapp": "comet",
            "upload_id": f"jsc_c_{uuid.uuid4().hex[:8]}",
            "qn": waterfall,
            "composer_session_id": session_id,
        }
        if tokens.get("lsd"):
            base_data["lsd"] = tokens["lsd"]
        if tokens.get("jazoest"):
            base_data["jazoest"] = tokens["jazoest"]

        mime = "image/jpeg"
        suf = path.suffix.lower()
        if suf == ".png":
            mime = "image/png"
        elif suf == ".gif":
            mime = "image/gif"
        elif suf == ".webp":
            mime = "image/webp"

        def _extract_photo_id(text: str) -> str | None:
            if text.startswith("for (;;);"):
                text = text[9:]
            for pat in (
                r'"photoID"\s*:\s*"?(\d+)"?',
                r'"photo_id"\s*:\s*"?(\d+)"?',
                r'"fbid"\s*:\s*"?(\d+)"?',
                r'"id"\s*:\s*"(\d{10,})"',
            ):
                m = re.search(pat, text)
                if m:
                    return m.group(1)
            try:
                j = json.loads(text)

                def find_photo(obj, depth=0):
                    if depth > 12:
                        return None
                    if isinstance(obj, dict):
                        for k in ("photoID", "photo_id", "fbid"):
                            if k in obj and str(obj[k]).isdigit():
                                return str(obj[k])
                        for v in obj.values():
                            r = find_photo(v, depth + 1)
                            if r:
                                return r
                    elif isinstance(obj, list):
                        for i in obj:
                            r = find_photo(i, depth + 1)
                            if r:
                                return r
                    return None

                return find_photo(j)
            except Exception:
                return None

        file_keys = ("farr", "file", "photo", "source")
        for url in upload_urls:
            for fkey in file_keys:
                try:
                    data = dict(base_data)
                    with open(path, "rb") as fh:
                        raw = fh.read()
                    resp = self.session.post(
                        url,
                        data=data,
                        files={fkey: (safe_name, raw, mime)},
                        headers={
                            **self.DESKTOP_HEADERS,
                            "Origin": "https://www.facebook.com",
                            "Referer": (
                                f"https://www.facebook.com/groups/{group_id}/"
                                if group_id
                                else "https://www.facebook.com/"
                            ),
                            "X-Requested-With": "XMLHttpRequest",
                        },
                        timeout=45,
                    )
                    pid = _extract_photo_id(resp.text)
                    if pid:
                        return pid
                except Exception:
                    continue
        return None

    def _build_gql_variables(
        self,
        group_id: str,
        message: str,
        uid: str,
        photo_id: str | None = None,
        *,
        entry_point: str = "inline_composer",
        attach_style: str = "attachments",
    ) -> dict:
        """Payload GraphQL theo format đã chạy được trên nhiều tool cookies."""
        sid = str(uuid.uuid4())
        input_node: dict = {
            "composer_entry_point": entry_point,
            "composer_source_surface": "group",
            "composer_type": "group",
            "idempotence_token": f"{uuid.uuid4()}_FEED",
            "source": "WWW",
            "attachments": [],
            "message": {"ranges": [], "text": message},
            "inline_activities": [],
            "explicit_place_id": "0",
            "text_format_preset_id": "0",
            "tracking": [None],
            "audience": {"to_id": str(group_id)},
            "actor_id": str(uid),
            "client_mutation_id": str(uuid.uuid4()),
            "logging": {"composer_session_id": sid},
        }
        if photo_id:
            photo_obj = {"photo": {"id": str(photo_id)}}
            # FB đổi schema thường xuyên — thử cả 2 kiểu
            if attach_style == "attached_media":
                input_node["attached_media"] = [photo_obj]
                input_node["attachments"] = []
            elif attach_style == "attachments_media":
                input_node["attachments"] = [{"media": {"id": str(photo_id)}}]
            else:
                input_node["attachments"] = [photo_obj]
        return {
            "input": input_node,
            "displayCommentsFeedbackContext": None,
            "displayCommentsContextEnableComment": None,
            "displayCommentsContextIsAdPreview": None,
            "displayCommentsContextIsAggregatedShare": None,
            "displayCommentsContextIsStorySet": None,
            "feedLocation": "GROUP",
            "feedbackSource": 0,
            "focusCommentID": None,
            "gridMediaWidth": None,
            "groupID": str(group_id),
            "scale": 1,
            "privacySelectorRenderLocation": "COMET_STREAM",
            "renderLocation": "group",
            "useDefaultActor": False,
            "isFeed": False,
            "isFundraiser": False,
            "isFunFactPost": False,
            "isGroup": True,
            "isTimeline": False,
            "isEvent": False,
            "isPageNewsFeed": False,
            "UFI2CommentsProvider_commentsKey": "CometGroupDiscussionRootSuccessQuery",
        }

    def _find_story_create_nodes(self, obj, depth: int = 0) -> list:
        if depth > 12 or obj is None:
            return []
        found = []
        if isinstance(obj, dict):
            if "story_create" in obj:
                found.append(obj["story_create"])
            for v in obj.values():
                found.extend(self._find_story_create_nodes(v, depth + 1))
        elif isinstance(obj, list):
            for item in obj:
                found.extend(self._find_story_create_nodes(item, depth + 1))
        return found

    def _json_has_other_group(self, obj, group_id: str, depth: int = 0) -> bool:
        """
        True nếu nhánh story_create gắn group KHÁC (echo bài nhóm trước).
        """
        if depth > 14 or obj is None:
            return False
        gid = str(group_id)
        if isinstance(obj, dict):
            for key in ("to_id", "group_id", "groupID"):
                val = obj.get(key)
                if val is None:
                    continue
                sval = str(val)
                if sval.isdigit() and len(sval) >= 8 and sval != gid:
                    return True
            aud = obj.get("audience")
            if isinstance(aud, dict):
                tid = str(aud.get("to_id", ""))
                if tid.isdigit() and len(tid) >= 8 and tid != gid:
                    return True
            for val in obj.values():
                if self._json_has_other_group(val, gid, depth + 1):
                    return True
        elif isinstance(obj, list):
            for item in obj:
                if self._json_has_other_group(item, gid, depth + 1):
                    return True
        elif isinstance(obj, str):
            m = re.search(r"/groups/(\d+)", obj.replace("\\/", "/"))
            if m and m.group(1) != gid:
                return True
        return False

    def _analyze_post_response(
        self, text: str, group_id: str | None = None
    ) -> tuple[str, str]:
        """
        Phân tích phản hồi đăng bài.
        Returns: (status, message) — status = published|pending|failed|unknown
        """
        raw = text
        if text.startswith("for (;;);"):
            text = text[9:]

        low = text.lower()
        gid = str(group_id) if group_id else ""

        # story_create null / bị chặn — không nhận là thành công
        if re.search(r'"story_create"\s*:\s*null', text):
            return "failed", "GraphQL: story_create=null (FB chặn hoặc từ chối bài)"
        if re.search(r'"story_create"\s*:\s*\{\s*\}', text):
            return "failed", "GraphQL: story_create rỗng"

        # Lỗi CRITICAL (bỏ qua WARNING relay)
        for chunk in text.split("\n"):
            chunk = chunk.strip()
            if not chunk or chunk[0] not in "{[":
                continue
            try:
                data = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict) and data.get("errors"):
                for err in data["errors"]:
                    if not isinstance(err, dict):
                        continue
                    sev = str(err.get("severity", "")).upper()
                    msg = str(err.get("message", ""))
                    if sev and sev not in ("CRITICAL", "ERROR", ""):
                        continue
                    if "pending" in msg.lower():
                        return "pending", "Đang chờ admin duyệt"
                    if msg and "warning" not in msg.lower():
                        return "failed", f"Lỗi FB: {msg[:140]}"

        pending_hints = (
            "pending_approval", "pending post", "awaiting approval",
            "chờ duyệt", "chờ phê duyệt", "requires_review",
            "publish_status\":\"pending", "publish_status_pending",
            "post_is_pending", "under_review",
        )
        is_pending = any(k.lower() in low for k in pending_hints)

        post_id = None
        publish_status = ""
        story_url = ""

        for chunk in text.split("\n"):
            chunk = chunk.strip()
            if not chunk or chunk[0] not in "{[":
                continue
            try:
                data = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            # Chỉ nhận id từ story_create — và phải thuộc đúng group_id
            found, status = self._walk_json_for_post(data, create_only=True)
            if found:
                if found in self._used_post_ids or (gid and found == gid):
                    continue
                if gid:
                    wrong = False
                    for sc in self._find_story_create_nodes(data):
                        if self._json_has_other_group(sc, gid):
                            wrong = True
                            break
                    if wrong:
                        continue
                post_id = found
                publish_status = status
                break
            url_m = re.search(
                r'https:\\?/\\?/www\.facebook\.com\\?/groups\\?/([^"\\/]+)\\?/(?:posts|permalink)\\?/([^"\\/?]+)',
                chunk,
            )
            if url_m:
                url_gid, url_pid = url_m.group(1), url_m.group(2)
                if gid and url_gid != gid:
                    continue
                if url_pid in self._used_post_ids:
                    continue
                story_url = url_m.group(0).replace("\\/", "/")
                post_id = post_id or url_pid
                break

        if not post_id:
            # Chỉ lấy id gần ngữ cảnh tạo bài — tránh id feed cũ
            for pat in (
                r'"story_create"\s*:\s*\{.{0,1200}?"legacy_story_hideable_id"\s*:\s*"(\d+)"',
                r'"story_create"\s*:\s*\{.{0,1200}?"post_id"\s*:\s*"(\d+)"',
                r'"creation_story"\s*:\s*\{[^}]*"id"\s*:\s*"([^"]+)"',
                r'"story_create"\s*:\s*\{[^}]*"id"\s*:\s*"([^"]+)"',
            ):
                m = re.search(pat, text, re.S)
                if m and m.group(1) not in self._used_post_ids:
                    if gid and m.group(1) == gid:
                        continue
                    post_id = m.group(1)
                    break

        if post_id or story_url:
            label = post_id[:28] if post_id else story_url[-40:]
            if is_pending or "pending" in publish_status.lower():
                return "pending", f"Đang chờ admin duyệt ({label})"
            return "published", f"Đã đăng lên nhóm ({label})"

        # Không có post_id / URL → KHÔNG báo thành công
        snippet = re.sub(r"\s+", " ", raw[:160])
        return "unknown", snippet

    def _extract_composer_doc_ids(self, html: str) -> list[str]:
        """Lấy doc_id composer từ HTML trang nhóm (ưu tiên) + fallback cũ."""
        ids: list[str] = []
        patterns = [
            r'ComposerStoryCreateMutation[^}]{0,400}"doc_id"\s*:\s*"(\d+)"',
            r'"doc_id"\s*:\s*"(\d+)"[^}]{0,400}ComposerStoryCreateMutation',
            r'CometComposerCreateMutation[^}]{0,400}"doc_id"\s*:\s*"(\d+)"',
            r'GroupComposer[^}]{0,400}"doc_id"\s*:\s*"(\d+)"',
            r'useCometComposerCreateMutation[^}]*"doc_id"\s*:\s*"(\d+)"',
            r'"name":"ComposerStoryCreateMutation"[^,]*,"id":"(\d+)"',
            r'"id":"(\d+)","name":"ComposerStoryCreateMutation"',
            # Pattern rộng hơn trên HTML comet
            r'"ComposerStoryCreateMutation".{0,80}"(doc_id|id)"\s*:\s*"(\d+)"',
            r'"(doc_id|id)"\s*:\s*"(\d+)".{0,80}"ComposerStoryCreateMutation"',
        ]
        for pat in patterns:
            for m in re.finditer(pat, html, re.S):
                gid = m.group(m.lastindex) if m.lastindex else m.group(1)
                if gid and gid.isdigit() and gid not in ids:
                    ids.append(gid)
        # Fallback cũ — đặt CUỐI, có thể đã chết
        known = [
            "26937332182536553",
            "4669579913112843",
            "5634383916606190",
            "4229729377134595",
            "23618316235273932",
        ]
        for fid in known:
            if fid not in ids:
                ids.append(fid)
        return ids

    def _post_via_graphql(
        self, group_id: str, message: str, image_path: str = None
    ) -> tuple[str, str]:
        """Đăng bài qua GraphQL — chỉ trả OK khi permalink post_id mở được đúng nhóm."""
        self._use_desktop_session()
        group_url = f"https://www.facebook.com/groups/{group_id}"
        try:
            self.session.get("https://www.facebook.com/", timeout=12)
            time.sleep(0.6)
            resp = self.session.get(group_url, timeout=15)
            html = resp.text
        except Exception as exc:
            return "failed", f"Không mở được trang nhóm: {exc}"

        tokens = self._extract_fb_tokens(html)
        uid = self._get_user_id()
        fb_dtsg = tokens.get("fb_dtsg")
        if not fb_dtsg:
            tokens = self._get_tokens(force_refresh=True)
            fb_dtsg = tokens.get("fb_dtsg")
        if not fb_dtsg or not uid:
            return "failed", "Không lấy được fb_dtsg — lấy lại cookies từ Chrome"

        if re.search(r'only.?admins.?can.?post|chỉ admin.*đăng|you can.?t post', html, re.I):
            return "failed", "Nhóm chỉ cho admin đăng bài"

        photo_id = None
        upload_err = ""
        want_image = bool(image_path and Path(image_path).is_file())
        if want_image:
            up_tokens = {"__user": uid, "fb_dtsg": fb_dtsg, **tokens}
            photo_id = self._upload_photo(image_path, up_tokens, group_id=group_id)
            if not photo_id:
                upload_err = "upload ảnh thất bại"
                photo_id = self._upload_photo(image_path, up_tokens, group_id=None)
            if not photo_id:
                # Không đăng text-only khi user chọn ảnh — để kênh khác thử multipart
                return "failed", (
                    "GraphQL: upload ảnh thất bại — thử kênh khác kèm file"
                )
            time.sleep(0.8)

        doc_ids = self._extract_composer_doc_ids(html)
        # Luôn ưu tiên doc_id scrap; bỏ id đã biết chết (document not found)
        dead_known = {
            "7828976785402038",
            "238010847699429",
            "7663315483767282",
        }
        doc_ids = [d for d in doc_ids if d not in dead_known]
        if not doc_ids:
            return "failed", "Không tìm thấy doc_id composer trên trang nhóm"

        entry_points = ["inline_composer", "group", "feed"]
        anchors = self._message_anchors(message)
        last_hint = upload_err
        claimed_unverified = 0
        dead_docs: set[str] = set()

        # Có ảnh → CHỈ đăng kèm ảnh (không fallback text-only giả thành công)
        photo_order: list[str | None] = [photo_id] if photo_id else [None]
        attach_styles = (
            ["attachments", "attached_media", "attachments_media"]
            if photo_id
            else ["attachments"]
        )

        def _try_once(
            doc_id: str, ph_id: str | None, entry: str, style: str = "attachments"
        ) -> tuple[str, str] | None:
            nonlocal last_hint, claimed_unverified
            if doc_id in dead_docs:
                return None
            variables = self._build_gql_variables(
                group_id, message, uid, ph_id,
                entry_point=entry, attach_style=style,
            )
            payload: dict = {
                "av": uid,
                "__user": uid,
                "__a": "1",
                "__req": str(uuid.uuid4().hex[:4]),
                "__comet_req": "15",
                "fb_dtsg": fb_dtsg,
                "fb_api_caller_class": "RelayModern",
                "fb_api_req_friendly_name": "ComposerStoryCreateMutation",
                "server_timestamps": "true",
                "variables": json.dumps(variables, ensure_ascii=False),
                "doc_id": doc_id,
            }
            if tokens.get("lsd"):
                payload["lsd"] = tokens["lsd"]
            if tokens.get("jazoest"):
                payload["jazoest"] = tokens["jazoest"]
            headers = {
                **self.DESKTOP_HEADERS,
                "Content-Type": "application/x-www-form-urlencoded",
                "X-FB-Friendly-Name": "ComposerStoryCreateMutation",
                "X-FB-LSD": tokens.get("lsd", ""),
                "Origin": "https://www.facebook.com",
                "Referer": group_url + "/",
            }
            try:
                gql_resp = self.session.post(
                    "https://www.facebook.com/api/graphql/",
                    data=payload,
                    headers=headers,
                    timeout=22,
                )
            except Exception as exc:
                last_hint = str(exc)
                return None

            raw = gql_resp.text
            # doc_id chết → bỏ hẳn, thử id khác
            if re.search(r"document with ID \d+ was not found", raw, re.I) or (
                "was not found" in raw.lower() and doc_id in raw
            ):
                dead_docs.add(doc_id)
                last_hint = f"doc_id {doc_id} đã chết"
                return None

            status, msg = self._analyze_post_response(raw, group_id=group_id)
            if status == "failed":
                if "was not found" in msg.lower() or "document" in msg.lower():
                    dead_docs.add(doc_id)
                    last_hint = msg[:120]
                    return None
                if any(
                    k in msg.lower()
                    for k in ("permission", "quyền", "not allowed", "admin", "chỉ cho")
                ):
                    return ("failed", msg)
                last_hint = msg
                return None
            if status not in ("published", "pending"):
                if msg:
                    last_hint = msg[:120]
                return None

            m = re.search(r"\(([0-9]{8,}|Uzpf[A-Za-z0-9_-]{8,})\)", msg)
            post_id = m.group(1) if m else None
            if post_id and post_id in self._used_post_ids:
                claimed_unverified += 1
                last_hint = f"post_id đã dùng {post_id[:16]}"
                return None
            if post_id:
                time.sleep(1.2)
                verified = self._verify_permalink(group_id, post_id, anchors)
                if verified:
                    tag = f"{msg}"
                    if ph_id:
                        tag += " (+ảnh)"
                    return (verified, tag)
                claimed_unverified += 1
                last_hint = f"permalink không có FPV / không mở được {post_id[:18]}"
                return None

            time.sleep(1.0)
            v = self._verify_pending_or_feed(group_id, anchors, status)
            if v:
                extra = " (+ảnh)" if ph_id else ""
                return (v, f"{msg}{extra}")
            claimed_unverified += 1
            last_hint = "không có post_id và không thấy FPV trên nhóm"
            return None

        for ph in photo_order:
            for entry in entry_points:
                for style in attach_styles:
                    for doc_id in doc_ids[:8]:
                        result = _try_once(doc_id, ph, entry, style)
                        if result:
                            st, msg = result
                            if st == "failed":
                                return result
                            return st, msg
                        time.sleep(0.25)

        hint = f" — {last_hint}" if last_hint else ""
        if claimed_unverified:
            hint += f" | {claimed_unverified} lần FB trả id giả / thiếu FPV"
        if dead_docs:
            hint += f" | bỏ {len(dead_docs)} doc_id chết"
        if photo_id:
            hint += f" | photoID={photo_id}"
        return "failed", f"GraphQL không tạo được bài thật{hint}"

    def _post_via_ajax_feed(
        self, group_id: str, message: str, image_path: str = None
    ) -> tuple[str, str]:
        """Fallback: ajax updatestatus / groups composer."""
        self._use_desktop_session()
        tokens = self._get_tokens(force_refresh=True)
        uid = tokens.get("__user") or self._get_user_id()
        fb_dtsg = tokens.get("fb_dtsg")
        if not fb_dtsg or not uid:
            return "failed", "Thiếu fb_dtsg"

        endpoints = [
            "https://www.facebook.com/ajax/updatestatus.php",
            "https://www.facebook.com/ajax/groups/composer/",
            f"https://www.facebook.com/groups/{group_id}/",
        ]
        bases = [
            {
                "fb_dtsg": fb_dtsg,
                "__user": uid,
                "__a": "1",
                "xhpc_message": message,
                "xhpc_message_text": message,
                "xhpc_targetid": str(group_id),
                "xhpc_context": "group",
                "xhpc_timeline": "1",
                "is_group": "1",
                "group_id": str(group_id),
                "message": message,
                "target": str(group_id),
            },
        ]

        for url in endpoints:
            for data in bases:
                try:
                    if image_path and Path(image_path).is_file() and "composer" in url:
                        raw = Path(image_path).read_bytes()
                        safe_name = self._safe_image_filename(image_path)
                        resp = self.session.post(
                            url, data=data,
                            files={"file": (safe_name, raw, "image/jpeg")},
                            headers={
                                **self.DESKTOP_HEADERS,
                                "Origin": "https://www.facebook.com",
                                "Referer": f"https://www.facebook.com/groups/{group_id}/",
                                "X-Requested-With": "XMLHttpRequest",
                            },
                            timeout=20,
                        )
                    else:
                        resp = self.session.post(
                            url, data=data,
                            headers={
                                **self.DESKTOP_HEADERS,
                                "Origin": "https://www.facebook.com",
                                "Referer": f"https://www.facebook.com/groups/{group_id}/",
                                "X-Requested-With": "XMLHttpRequest",
                                "Content-Type": "application/x-www-form-urlencoded",
                            },
                            timeout=15,
                        )
                    status, msg = self._analyze_post_response(resp.text, group_id=group_id)
                    if status in ("published", "pending"):
                        return status, msg
                    # Ajax chỉ chấp nhận khi có post id thật (analyze đã lo)
                except Exception:
                    continue
        return "failed", "Ajax composer thất bại"

    def _walk_json_for_post(
        self, obj, depth=0, path: str = "", *, create_only: bool = False
    ) -> tuple[str | None, str]:
        """
        Duyệt JSON tìm story/post id thật từ kết quả tạo bài.
        create_only=True: chỉ lấy id trong nhánh story_create / creation_story.
        """
        if depth > 14:
            return None, ""
        if isinstance(obj, dict):
            path_l = path.lower()
            in_create = any(
                k in path_l
                for k in (
                    "story_create",
                    "creation_story",
                    "composer_create",
                    "story_create_response",
                )
            )
            allow_id = in_create or not create_only

            if allow_id:
                for key in ("legacy_story_hideable_id", "post_id"):
                    val = obj.get(key)
                    if val and isinstance(val, (str, int)) and len(str(val)) >= 8:
                        status = str(obj.get("publish_status", obj.get("status", "")))
                        return str(val), status

            if in_create:
                for key in ("story_id", "id"):
                    val = obj.get(key)
                    if not val:
                        continue
                    sval = str(val)
                    if len(sval) < 8:
                        continue
                    if sval.isdigit() or sval.startswith("Uzpf") or ":" in sval:
                        status = str(obj.get("publish_status", obj.get("status", "")))
                        return sval, status
                typename = str(obj.get("__typename", ""))
                if typename in ("Story", "CometStory", "GroupFeedStory"):
                    val = obj.get("id")
                    if val and isinstance(val, str) and len(val) > 8:
                        status = str(obj.get("publish_status", obj.get("status", "")))
                        return val, status

            prefer = (
                "story_create",
                "creation_story",
                "composer_create",
                "story_create_response",
                "data",
                "story",
                "node",
                "post",
            )
            for nest_key in prefer:
                if nest_key in obj and isinstance(obj[nest_key], (dict, list)):
                    found, status = self._walk_json_for_post(
                        obj[nest_key],
                        depth + 1,
                        f"{path}.{nest_key}",
                        create_only=create_only,
                    )
                    if found:
                        return found, status
            for k, v in obj.items():
                if k in prefer:
                    continue
                found, status = self._walk_json_for_post(
                    v, depth + 1, f"{path}.{k}", create_only=create_only
                )
                if found:
                    return found, status
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                found, status = self._walk_json_for_post(
                    item, depth + 1, f"{path}[{i}]", create_only=create_only
                )
                if found:
                    return found, status
        return None, ""

    def _extract_created_post_id(self, data) -> tuple[str | None, str]:
        """Ưu tiên id từ story_create; fallback post_id/legacy nếu có."""
        found, status = self._walk_json_for_post(data, create_only=True)
        if found:
            return found, status
        return self._walk_json_for_post(data, create_only=False)



    def _post_via_composer_direct(
        self, group_id: str, message: str, image_path: str = None
    ) -> tuple[str, str]:
        """Đăng trực tiếp qua mbasic composer (không cần scrape form)."""
        tokens = self._get_tokens(force_refresh=False)
        uid = tokens.get("__user") or self._get_user_id()
        fb_dtsg = tokens.get("fb_dtsg", "")
        if not fb_dtsg:
            tokens = self._get_tokens(force_refresh=True)
            fb_dtsg = tokens.get("fb_dtsg", "")
        if not fb_dtsg or not uid:
            return "failed", "Thiếu fb_dtsg"

        saved = dict(self.session.headers)
        self._use_mobile_session()
        try:
            # Làm ấm session + lấy token mbasic
            warm = self.session.get(f"{MOBILE_URL}/", timeout=12)
            fields = self._extract_form_fields(warm.text)
            if fields.get("fb_dtsg"):
                fb_dtsg = fields["fb_dtsg"]
            jazoest = fields.get("jazoest") or tokens.get("jazoest", "")

            post_urls = [
                f"{MOBILE_URL}/composer/mbasic/?c_src=group&target={group_id}&av={uid}",
                f"{MOBILE_URL}/composer/mbasic/?target={group_id}&c_src=group",
                f"https://m.facebook.com/composer/mbasic/?c_src=group&target={group_id}",
            ]

            data = {
                "fb_dtsg": fb_dtsg,
                "__user": uid,
                "xc_message": message,
                "target": str(group_id),
                "c_src": "group",
                "cwevent": "composer_entry",
                "referrer": "group",
                "ctype": "inline",
                "cver": "amber",
                "view_post": "Đăng",
                "rst_ag": "1",
            }
            if jazoest:
                data["jazoest"] = jazoest

            for post_url in post_urls:
                try:
                    if image_path and Path(image_path).is_file():
                        raw = Path(image_path).read_bytes()
                        safe_name = self._safe_image_filename(image_path)
                        resp = self.session.post(
                            post_url, data=data,
                            files={"file1": (safe_name, raw, "image/jpeg")},
                            allow_redirects=True, timeout=25,
                        )
                    else:
                        resp = self.session.post(
                            post_url, data=data, allow_redirects=True, timeout=15,
                        )
                    status, msg = self._analyze_post_response(resp.text, group_id=group_id)
                    if status in ("published", "pending"):
                        return status, msg
                    # Chỉ nhận nếu URL redirect có post id thật
                    url_l = resp.url
                    pid_m = re.search(
                        r"(?:story_fbid|posts/|permalink\.php\?story_fbid=)[=/]?(\d{8,})",
                        url_l,
                    )
                    if pid_m:
                        if "pending" in url_l.lower():
                            return "pending", f"Đang chờ admin duyệt ({pid_m.group(1)})"
                        return "published", f"Đã đăng lên nhóm ({pid_m.group(1)})"
                except Exception:
                    continue

            return "failed", "Composer: không xác nhận được bài đăng (không có post ID)"
        except Exception as exc:
            return "failed", f"Composer: {exc}"
        finally:
            self.session.headers.clear()
            self.session.headers.update(saved)
            if self._desktop_mode:
                self._use_desktop_session()

    def _post_via_m_composer(
        self, group_id: str, message: str, image_path: str = None
    ) -> tuple[str, str]:
        """Đăng qua m.facebook.com composer — ổn định với thành viên thường."""
        tokens = self._get_tokens()
        uid = tokens.get("__user") or self._get_user_id()
        fb_dtsg = tokens.get("fb_dtsg", "")

        saved = dict(self.session.headers)
        self.session.headers.update({
            **self.DESKTOP_HEADERS,
            "User-Agent": self.MOBILE_HEADERS["User-Agent"],
        })

        compose_url = f"https://m.facebook.com/groups/{group_id}/permalink/"
        try:
            resp = self.session.get(compose_url, timeout=12, allow_redirects=True)
            html = resp.text
            fields = self._extract_form_fields(html)

            ta_m = re.search(r'<textarea[^>]+name=["\']([^"\']+)["\']', html, re.I)
            msg_key = ta_m.group(1) if ta_m else "message"

            action = self._find_form_action(html, group_id)
            if not action:
                action = f"/groups/{group_id}/permalink/"

            fields[msg_key] = message
            if fb_dtsg:
                fields["fb_dtsg"] = fb_dtsg
            if uid:
                fields["__user"] = uid
            if tokens.get("jazoest"):
                fields["jazoest"] = tokens["jazoest"]
            fields["__a"] = "1"
            fields["target"] = str(group_id)
            fields["c_src"] = "group"

            if not action:
                action = f"/composer/mbasic/?c_src=group&target={group_id}"

            post_url = action if action.startswith("http") else f"https://m.facebook.com{action}"

            if image_path and Path(image_path).is_file():
                raw = Path(image_path).read_bytes()
                safe_name = self._safe_image_filename(image_path)
                post_resp = self.session.post(
                    post_url, data=fields,
                    files={"file": (safe_name, raw, "image/jpeg")},
                    allow_redirects=True, timeout=20,
                )
            else:
                post_resp = self.session.post(
                    post_url, data=fields, allow_redirects=True, timeout=12,
                )

            status, msg = self._analyze_post_response(post_resp.text, group_id=group_id)
            if status in ("published", "pending"):
                return status, msg
            if status == "failed" and msg:
                return status, msg
            # Chỉ chấp nhận nếu có post id trong HTML
            pid = re.search(
                r'(?:story_fbid|post_id|legacy_story_hideable_id)[=:]["\']?(\d{8,})',
                post_resp.text,
            )
            if pid:
                if any(k in post_resp.text.lower() for k in (
                    "pending", "chờ duyệt", "awaiting approval",
                )):
                    return "pending", f"Đang chờ admin duyệt (post: {pid.group(1)})"
                return "published", f"Đã đăng lên nhóm (post: {pid.group(1)})"
            return "failed", "m.facebook.com: không xác nhận được bài đăng (không có post ID)"
        except Exception as exc:
            return "failed", f"m.facebook: {exc}"
        finally:
            self.session.headers.clear()
            self.session.headers.update(saved)
            if self._desktop_mode:
                self._use_desktop_session()

    def _post_via_permalink(self, group_id: str, message: str) -> tuple[str, str]:
        """Đăng qua trang composer permalink (desktop)."""
        self._use_desktop_session()
        tokens = self._get_tokens()
        uid = tokens.get("__user") or self._get_user_id()
        fb_dtsg = tokens.get("fb_dtsg")
        if not fb_dtsg:
            return "failed", "Thiếu fb_dtsg"

        compose_urls = [
            f"https://www.facebook.com/groups/{group_id}/permalink/",
            f"https://m.facebook.com/groups/{group_id}/permalink/",
        ]

        for compose_url in compose_urls:
            try:
                resp = self.session.get(compose_url, timeout=12, allow_redirects=True)
                fields = self._extract_form_fields(resp.text)
                if not fields:
                    continue

                # Tìm trường message
                msg_field = None
                for key in ("message", "xc_message", "composer_message"):
                    if key in fields or any(k.endswith(key) for k in fields):
                        msg_field = key
                        break
                if not msg_field:
                    m = re.search(r'<textarea[^>]+name=["\']([^"\']+)["\']', resp.text)
                    msg_field = m.group(1) if m else "message"

                fields[msg_field] = message
                fields["fb_dtsg"] = fb_dtsg
                if uid:
                    fields["__user"] = uid

                action = self._find_form_action(resp.text, group_id)
                if not action:
                    action = compose_url
                post_url = action if action.startswith("http") else f"https://www.facebook.com{action}"

                post_resp = self.session.post(
                    post_url, data=fields, allow_redirects=True, timeout=12
                )
                status, msg = self._analyze_post_response(post_resp.text, group_id=group_id)
                if status in ("published", "pending"):
                    return status, msg
                pid = re.search(
                    r'(?:story_fbid|post_id|legacy_story_hideable_id)[=:]["\']?(\d{8,})',
                    post_resp.text,
                )
                if pid:
                    return "published", f"Đã đăng lên nhóm (post: {pid.group(1)})"
            except Exception:
                continue
        return "failed", "Không tìm thấy form permalink"

    def _post_via_mobile(
        self, group_id: str, message: str, image_path: str = None
    ) -> tuple[str, str]:
        """Đăng qua mbasic — lấy token mới từ trang nhóm, xác nhận bằng FPV."""
        # Force token mới — không dùng cache dtsg cũ
        self._tokens_cache.clear()
        self._tokens_cache_time = 0.0
        uid = self._get_user_id()

        saved_headers = dict(self.session.headers)
        self._use_mobile_session()

        try:
            # Làm ấm mbasic home trước (hay lấy được fb_dtsg khi trang nhóm thiếu)
            try:
                home = self.session.get(f"{MOBILE_URL}/", timeout=12, allow_redirects=True)
                home_fields = self._extract_form_fields(home.text)
                home_dtsg = home_fields.get("fb_dtsg", "")
            except Exception:
                home_dtsg = ""

            urls_to_try = [
                f"{MOBILE_URL}/composer/mbasic/?c_src=group&target={group_id}&av={uid}",
                f"{MOBILE_URL}/composer/?c_src=group&target={group_id}",
                f"{MOBILE_URL}/photos/upload/?target_id={group_id}&upload_source=composer",
                f"{MOBILE_URL}/groups/{group_id}?view=permalink",
                f"{MOBILE_URL}/groups/{group_id}/",
                f"https://m.facebook.com/groups/{group_id}/",
            ]

            html = ""
            fb_dtsg = home_dtsg
            for url in urls_to_try:
                try:
                    resp = self.session.get(url, timeout=12, allow_redirects=True)
                    if resp.status_code != 200:
                        continue
                    html = resp.text
                    fields0 = self._extract_form_fields(html)
                    if fields0.get("fb_dtsg"):
                        fb_dtsg = fields0["fb_dtsg"]
                    link_m = re.search(
                        r'href="(/composer/[^"]*target=' + re.escape(str(group_id)) + r'[^"]*)"',
                        html, re.I,
                    )
                    if not link_m:
                        link_m = re.search(
                            rf'href="(/groups/{group_id}/[^"]*(?:permalink|compose)[^"]*)"',
                            html, re.I,
                        )
                    if not link_m:
                        link_m = re.search(r'href="(/composer/[^"]+)"', html, re.I)
                    if link_m:
                        href = link_m.group(1).replace("&amp;", "&")
                        compose_page = self.session.get(
                            f"{MOBILE_URL}{href}" if href.startswith("/") else href,
                            timeout=12, allow_redirects=True,
                        )
                        html = compose_page.text
                        fields0 = self._extract_form_fields(html)
                        if fields0.get("fb_dtsg"):
                            fb_dtsg = fields0["fb_dtsg"]
                    if "textarea" in html.lower() or "xc_message" in html or "fb_dtsg" in html:
                        break
                except Exception:
                    continue

            if not html:
                return "failed", "Không truy cập được trang nhóm (mbasic)"

            if re.search(r'only.?admins|chỉ admin.*đăng|you can.?t post', html, re.I):
                return "failed", "Nhóm chỉ cho admin đăng bài"

            fields = self._extract_form_fields(html)
            if fields.get("fb_dtsg"):
                fb_dtsg = fields["fb_dtsg"]
            if not fb_dtsg:
                # Fallback desktop token (cookies Chrome)
                desk = self._get_tokens(force_refresh=True)
                fb_dtsg = desk.get("fb_dtsg", "")
            if not fb_dtsg:
                return "failed", "mbasic: thiếu fb_dtsg mới"

            ta_m = re.search(r'<textarea[^>]+name=["\']([^"\']+)["\']', html, re.I)
            msg_key = ta_m.group(1) if ta_m else "xc_message"

            action = self._find_form_action(html, group_id)
            if not action:
                action = f"/composer/mbasic/?c_src=group&target={group_id}&av={uid}"

            fields[msg_key] = message
            fields["xc_message"] = message
            fields["target"] = str(group_id)
            fields["c_src"] = "group"
            fields["fb_dtsg"] = fb_dtsg
            if uid:
                fields["__user"] = uid
            fields.setdefault("view_post", "Đăng")

            post_urls = [
                action if action.startswith("http") else f"{MOBILE_URL}{action}",
                f"{MOBILE_URL}/composer/mbasic/?c_src=group&target={group_id}&av={uid}",
                f"{MOBILE_URL}/a/group/post/add/?gid={group_id}",
            ]

            use_image = bool(image_path and Path(image_path).is_file())
            safe_name = self._safe_image_filename(image_path) if use_image else ""
            mime = "image/jpeg"
            if use_image:
                suf = Path(image_path).suffix.lower()
                if suf == ".png":
                    mime = "image/png"
                elif suf == ".gif":
                    mime = "image/gif"
                elif suf == ".webp":
                    mime = "image/webp"

            last_resp = None
            photo_sent = False
            for post_url in post_urls:
                try:
                    if use_image:
                        raw = Path(image_path).read_bytes()
                        for fkey in ("file1", "file", "photo", "source"):
                            post_resp = self.session.post(
                                post_url,
                                data=fields,
                                files={fkey: (safe_name, raw, mime)},
                                allow_redirects=True,
                                timeout=30,
                            )
                            last_resp = post_resp
                            if "login" in post_resp.url.lower():
                                return "failed", "Cookies hết hạn — lấy lại cookies"
                            status, msg = self._analyze_post_response(
                                post_resp.text, group_id=group_id
                            )
                            pid_m = re.search(
                                r"(?:story_fbid|posts/|permalink\.php\?story_fbid=)[=/]?(\d{8,})",
                                post_resp.url,
                            )
                            post_id = pid_m.group(1) if pid_m else None
                            if status in ("published", "pending") and post_id:
                                return status, f"{msg} (+ảnh)"
                            if post_id:
                                if "pending" in post_resp.url.lower():
                                    return "pending", f"Đang chờ admin duyệt ({post_id})"
                                return "published", f"Đã đăng lên nhóm ({post_id})"
                            if "photo_upload_success" in post_resp.url.lower() or (
                                "view=group" in post_resp.url.lower()
                                and "photo" in post_resp.url.lower()
                            ):
                                photo_sent = True
                                break
                        if photo_sent:
                            break
                    else:
                        post_resp = self.session.post(
                            post_url, data=fields, allow_redirects=True, timeout=15,
                        )
                        last_resp = post_resp
                        if "login" in post_resp.url.lower():
                            return "failed", "Cookies hết hạn — lấy lại cookies"
                        status, msg = self._analyze_post_response(
                            post_resp.text, group_id=group_id
                        )
                        pid_m = re.search(
                            r"(?:story_fbid|posts/|permalink\.php\?story_fbid=)[=/]?(\d{8,})",
                            post_resp.url,
                        )
                        post_id = pid_m.group(1) if pid_m else None
                        if status in ("published", "pending") and post_id:
                            return status, msg
                        if post_id:
                            if "pending" in post_resp.url.lower():
                                return "pending", f"Đang chờ admin duyệt ({post_id})"
                            return "published", f"Đã đăng lên nhóm ({post_id})"
                except Exception:
                    continue

            # Không có post id trên URL → xác minh FPV trên pending/feed
            time.sleep(1.5)
            marker = self._extract_verify_marker(message)
            anchors = self._message_anchors(message, marker)
            verified = self._verify_pending_or_feed(group_id, anchors, "pending")
            if verified:
                extra = " (+ảnh)" if use_image else ""
                return verified, f"mbasic OK (xác minh FPV trên nhóm){extra}"
            verified = self._verify_post_status(
                group_id, message, post_id=None, claimed="pending", marker=marker
            )
            if verified:
                extra = " (+ảnh)" if use_image else ""
                return verified, f"mbasic OK (xác minh FPV){extra}"
            if last_resp is None:
                return "failed", "mbasic: không gửi được form"
            return "failed", "mbasic: đã gửi form nhưng không thấy FPV trên nhóm"
        except Exception as exc:
            return "failed", f"mbasic: {exc}"
        finally:
            self.session.headers.clear()
            self.session.headers.update(saved_headers)
            if self._desktop_mode:
                self._use_desktop_session()

    def _find_form_action(self, html: str, group_id: str) -> str:
        patterns = [
            r'<form[^>]+action=["\']([^"\']*(?:compose|permalink|post|group)[^"\']*)["\']',
            r'<form[^>]+action=["\'](/groups/[^"\']*)["\']',
            r'<form[^>]+action=["\'](/a/group/post/[^"\']*)["\']',
            rf'action=["\'](/groups/{group_id}/[^"\']*)["\']',
        ]
        for p in patterns:
            m = re.search(p, html, re.I)
            if m:
                return m.group(1)
        m = re.search(
            r'<form[^>]+method=["\']post["\'][^>]+action=["\']([^"\']+)["\']',
            html, re.I,
        )
        if m:
            return m.group(1)
        m = re.search(
            r'action=["\']([^"\']+)["\'][^>]*method=["\']post["\']',
            html, re.I,
        )
        return m.group(1) if m else ""

    def _extract_hidden_fields(self, html: str) -> dict:
        """Trích xuất các hidden input field."""
        return self._extract_form_fields(html)

    def _post_ok(self, html: str) -> bool:
        indicators = [
            "story_menu", "Bài viết của bạn", "Your post", "post_action",
            "story_create", "legacy_story_hideable_id", "permalink.php",
            "view_post_script", "m_story_permalink_view",
        ]
        if any(x in html for x in indicators):
            return True
        if "error" in html[:400].lower() and "story" not in html[:400].lower():
            return False
        return False


# ──────────────────────────────────────────────────────────────────────────────
# Custom Widgets — cam / trắng, góc bo tròn
# ──────────────────────────────────────────────────────────────────────────────

def _round_rect(canvas, x1, y1, x2, y2, r=16, **kw):
    points = [
        x1 + r, y1, x1 + r, y1, x2 - r, y1, x2 - r, y1, x2, y1,
        x2, y1 + r, x2, y1 + r, x2, y2 - r, x2, y2 - r, x2, y2,
        x2 - r, y2, x2 - r, y2, x1 + r, y2, x1 + r, y2, x1, y2,
        x1, y2 - r, x1, y2 - r, x1, y1 + r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


class RoundedFrame(tk.Frame):
    """Khung trắng bo góc, viền cam nhạt."""

    def __init__(self, master, radius=18, fill=None, border=None, **kw):
        self._radius = radius
        self._fill = fill or COLOR_PANEL
        self._border = border or COLOR_BORDER
        outer_bg = master.cget("bg") if master else COLOR_BG
        super().__init__(master, bg=outer_bg, **kw)
        self._canvas = tk.Canvas(self, bg=outer_bg, highlightthickness=0, bd=0)
        self._canvas.pack(fill="both", expand=True)
        self.inner = tk.Frame(self._canvas, bg=self._fill)
        self._win = self._canvas.create_window(12, 12, anchor="nw", window=self.inner)
        self.bind("<Configure>", self._redraw)

    def _redraw(self, _e=None):
        w, h = max(self.winfo_width(), 20), max(self.winfo_height(), 20)
        self._canvas.delete("shape")
        _round_rect(
            self._canvas, 1, 1, w - 1, h - 1,
            r=self._radius, fill=self._fill, outline=self._border, width=1.5, tags="shape",
        )
        self._canvas.tag_lower("shape")
        self._canvas.itemconfigure(self._win, width=max(w - 24, 10), height=max(h - 24, 10))


class HoverButton(tk.Button):
    """Nút cam bo mềm (pad lớn, font rõ)."""

    def __init__(self, master, **kw):
        self._bg = kw.get("bg", COLOR_BUTTON)
        self._hover_bg = kw.pop("hover_bg", COLOR_BUTTON_HOVER)
        kw.setdefault("bg", self._bg)
        kw.setdefault("fg", kw.get("fg", "#FFFFFF"))
        kw.setdefault("activebackground", self._hover_bg)
        kw.setdefault("activeforeground", "#FFFFFF")
        kw.setdefault("relief", "flat")
        kw.setdefault("cursor", "hand2")
        kw.setdefault("bd", 0)
        kw.setdefault("highlightthickness", 0)
        kw.setdefault("font", ("Segoe UI", 11, "bold"))
        kw.setdefault("padx", 16)
        kw.setdefault("pady", 8)
        super().__init__(master, **kw)
        self.bind("<Enter>", lambda e: self._safe_bg(self._hover_bg))
        self.bind("<Leave>", lambda e: self._safe_bg(self._bg))

    def _safe_bg(self, color):
        try:
            if str(self["state"]) != "disabled":
                self.config(bg=color)
        except Exception:
            pass


class RoundedButton(tk.Canvas):
    """Nút bo tròn thật (canvas) — dùng cho Bắt đầu / Dừng."""

    def __init__(
        self,
        master,
        text="",
        command=None,
        bg=None,
        fg="#FFFFFF",
        hover_bg=None,
        disabled_bg="#FDBA74",
        disabled_fg="#FFF7ED",
        radius=18,
        font=None,
        padx=28,
        pady=14,
        outline=None,
        **_kw,
    ):
        parent_bg = master.cget("bg") if master else COLOR_BG
        super().__init__(master, bg=parent_bg, highlightthickness=0, bd=0, cursor="hand2")
        self._text = text
        self._command = command
        self._bg = bg or COLOR_BUTTON
        self._fg = fg
        self._hover_bg = hover_bg or COLOR_BUTTON_HOVER
        self._disabled_bg = disabled_bg
        self._disabled_fg = disabled_fg
        self._radius = radius
        self._font = font or ("Segoe UI", 13, "bold")
        self._padx = padx
        self._pady = pady
        self._outline = outline or self._bg
        self._state = "normal"
        self._hover = False
        self._shape = None
        self._label = None
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<Configure>", lambda _e: self._draw())
        self.after_idle(self._measure_and_draw)

    def _measure_and_draw(self):
        try:
            tmp = self.create_text(0, 0, text=self._text, font=self._font, anchor="nw")
            bbox = self.bbox(tmp)
            self.delete(tmp)
            tw = (bbox[2] - bbox[0]) if bbox else 80
            th = (bbox[3] - bbox[1]) if bbox else 20
            w = tw + self._padx * 2
            h = th + self._pady * 2
            self.configure(width=w, height=h)
        except Exception:
            self.configure(width=180, height=48)
        self._draw()

    def _fill(self):
        if self._state == "disabled":
            return self._disabled_bg
        return self._hover_bg if self._hover else self._bg

    def _text_color(self):
        if self._state == "disabled":
            return self._disabled_fg
        return self._fg

    def _draw(self):
        self.delete("all")
        w = max(self.winfo_width(), 40)
        h = max(self.winfo_height(), 28)
        fill = self._fill()
        outline = fill if self._state == "disabled" else (self._outline or fill)
        self._shape = _round_rect(
            self, 1, 1, w - 2, h - 2,
            r=min(self._radius, h // 2),
            fill=fill, outline=outline, width=1.5, tags="btn",
        )
        self._label = self.create_text(
            w // 2, h // 2, text=self._text, fill=self._text_color(),
            font=self._font, tags="btn",
        )

    def _on_enter(self, _e=None):
        if self._state == "disabled":
            return
        self._hover = True
        self._draw()

    def _on_leave(self, _e=None):
        self._hover = False
        self._draw()

    def _on_click(self, _e=None):
        if self._state == "disabled" or not self._command:
            return
        self._command()

    def config(self, **kw):
        redraw = False
        if "state" in kw:
            self._state = str(kw.pop("state"))
            self.configure(cursor="" if self._state == "disabled" else "hand2")
            redraw = True
        if "text" in kw:
            self._text = kw.pop("text")
            redraw = True
        if "command" in kw:
            self._command = kw.pop("command")
        if "bg" in kw:
            self._bg = kw.pop("bg")
            redraw = True
        if "fg" in kw:
            self._fg = kw.pop("fg")
            redraw = True
        if kw:
            super().configure(**kw)
        if redraw:
            self.after_idle(self._measure_and_draw)

    configure = config

    def cget(self, key):
        if key == "state":
            return self._state
        if key == "text":
            return self._text
        return super().cget(key)


class SoftEntry(tk.Frame):
    """Ô nhập bo góc giả lập bằng viền cam nhạt."""

    def __init__(self, master, textvariable=None, width=30, show=None, **kw):
        super().__init__(
            master, bg=COLOR_BORDER, padx=2, pady=2,
            highlightthickness=0,
        )
        self.entry = tk.Entry(
            self, textvariable=textvariable, width=width, show=show or "",
            bg=COLOR_INPUT_BG, fg=COLOR_INPUT_FG, insertbackground=COLOR_TEXT,
            relief="flat", font=("Segoe UI", 11), bd=0,
        )
        self.entry.pack(fill="both", expand=True, padx=10, pady=8)


class Card(RoundedFrame):
    def __init__(self, master, title: str = "", **kw):
        super().__init__(master, radius=18, **kw)
        if title:
            tk.Label(
                self.inner, text=title, bg=COLOR_PANEL, fg=COLOR_TEXT,
                font=("Segoe UI", 13, "bold"),
            ).pack(anchor="w", pady=(4, 8))
        self.body = tk.Frame(self.inner, bg=COLOR_PANEL)
        self.body.pack(fill="both", expand=True)


class LogBox(scrolledtext.ScrolledText):
    def __init__(self, master, **kw):
        defaults = dict(
            bg=COLOR_INPUT_BG, fg=COLOR_TEXT, font=("Consolas", 9),
            wrap=tk.WORD, state="disabled", relief="flat",
            insertbackground=COLOR_TEXT,
            highlightthickness=1, highlightbackground=COLOR_BORDER,
            highlightcolor=COLOR_ACCENT,
        )
        defaults.update(kw)
        super().__init__(master, **defaults)
        self.tag_config("ok", foreground=COLOR_SUCCESS)
        self.tag_config("err", foreground=COLOR_ERROR)
        self.tag_config("warn", foreground=COLOR_WARNING)
        self.tag_config("pending", foreground=COLOR_PENDING)
        self.tag_config("info", foreground=COLOR_TEXT_DIM)
        self.tag_config("bold", foreground=COLOR_TEXT, font=("Consolas", 9, "bold"))

    def log(self, msg: str, tag: str = ""):
        self.config(state="normal")
        ts = time.strftime("%H:%M:%S")
        self.insert("end", f"[{ts}] {msg}\n", tag)
        self.see("end")
        self.config(state="disabled")

    def clear(self):
        self.config(state="normal")
        self.delete("1.0", "end")
        self.config(state="disabled")


# ──────────────────────────────────────────────────────────────────────────────
# Main Application
# ──────────────────────────────────────────────────────────────────────────────

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        _ensure_data_dir()
        self.title(f"{APP_TITLE} v{APP_VERSION} — {APP_COPYRIGHT}")
        self.geometry("1120x760")
        self.minsize(960, 660)
        self.configure(bg=COLOR_BG)
        self.resizable(True, True)

        try:
            if getattr(sys, "frozen", False):
                base = sys._MEIPASS
            else:
                base = os.path.dirname(__file__)
            icon_path = os.path.join(base, "icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        self.backend = FacebookBackend()
        self.groups: list[dict] = []
        self.selected_groups: list[dict] = []
        self._posting = False
        self._stop_flag = False
        self._draft_save_job = None
        self._license_ok = False
        self._license_dialog = None
        self._license_watch_job = None

        # UI trước — mở nhanh; cookies/nhóm/nháp load nền
        self._build_ui()
        self.after(80, self._bootstrap_license_then_data)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _bootstrap_license_then_data(self):
        """Xác minh bản quyền trước, rồi mới load cookies/nhóm."""
        def _bg():
            if lic is None:
                self.after(0, lambda: self._on_license_result(
                    False, "Thiếu module license_client.py"
                ))
                return
            ok, msg, data = lic.verify()
            self.after(0, lambda: self._on_license_result(ok, msg, data))

        threading.Thread(target=_bg, daemon=True).start()

    def _on_license_result(self, ok: bool, msg: str, data: dict | None = None):
        self._license_ok = bool(ok)
        data = data or {}
        if hasattr(self, "_license_status_var"):
            self._license_status_var.set(
                ("✅ " if ok else "❌ ") + (msg or "")
            )
        if ok:
            self._status_var.set(f"🔑 {msg}")
            self._log(f"Bản quyền: {msg}", "ok")
            self._bootstrapped_data = True
            self._bootstrap_saved_data()
            self._schedule_license_watch()
        else:
            self._status_var.set("🔑 Cần mua token để sử dụng tiếp")
            self._log(f"Bản quyền: {msg}", "warn")
            # Hết hạn giữa chừng → dừng đăng bài
            if getattr(self, "_posting", False):
                self._stop_flag = True
            reason = "expired" if (data.get("code") == "expired") else "missing"
            self.after(200, lambda: self._show_license_dialog(reason=reason))

    def _schedule_license_watch(self):
        """Kiểm tra hạn token định kỳ (mỗi 15 giây)."""
        if self._license_watch_job:
            try:
                self.after_cancel(self._license_watch_job)
            except Exception:
                pass
            self._license_watch_job = None

        def _tick():
            self._license_watch_job = self.after(15000, _tick)
            if not lic or not getattr(self, "_license_ok", False):
                return
            # Kiểm tra hết hạn local ngay (không chờ server)
            if lic.is_locally_expired():
                self._on_license_result(
                    False,
                    getattr(lic, "MSG_NEED_BUY", "Token đã hết hạn. Bạn cần mua token để sử dụng tiếp."),
                    {"code": "expired"},
                )
                return

            def _bg():
                ok, msg, data = lic.verify(timeout=8.0)
                if not ok:
                    self.after(0, lambda: self._on_license_result(ok, msg, data))
                else:
                    self.after(0, lambda: self._refresh_license_status_ok(msg))

            threading.Thread(target=_bg, daemon=True).start()

        self._license_watch_job = self.after(15000, _tick)

    def _refresh_license_status_ok(self, msg: str):
        if not getattr(self, "_license_ok", False):
            return
        self._status_var.set(f"🔑 {msg}")
        if hasattr(self, "_license_status_var"):
            self._license_status_var.set(f"✅ {msg}")

    def _show_license_dialog(self, reason: str = "missing"):
        """Hộp thoại bắt buộc nhập token — hiện lại khi hết hạn."""
        # Đã có dialog đang mở
        existing = getattr(self, "_license_dialog", None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.lift()
                    existing.focus_force()
                    return
            except Exception:
                pass

        if getattr(self, "_license_ok", False) and reason != "expired":
            return

        # Hết hạn → buộc hiện lại dù trước đó ok
        self._license_ok = False

        win = tk.Toplevel(self)
        self._license_dialog = win
        win.title("Kích hoạt bản quyền")
        win.configure(bg=COLOR_PANEL)
        win.geometry("500x400")
        win.transient(self)
        win.grab_set()
        win.resizable(False, False)

        title = "🔑  Nhập mã token để sử dụng app"
        hint = (
            "Mua token trên trang web / Zalo 0981227703.\n"
            "Mỗi token chỉ kích hoạt được 1 máy.\n"
            f"{APP_COPYRIGHT}"
        )
        if reason == "expired":
            title = "⏰  Token đã hết hạn"
            hint = (
                "Bạn cần mua token để sử dụng tiếp.\n"
                "Zalo / SĐT: 0981227703\n"
                f"{APP_COPYRIGHT}"
            )

        tk.Label(
            win, text=title,
            bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Segoe UI", 14, "bold"),
        ).pack(pady=(22, 6), padx=20, anchor="w")
        tk.Label(
            win, text=hint,
            bg=COLOR_PANEL, fg=COLOR_ERROR if reason == "expired" else COLOR_TEXT_DIM,
            font=("Segoe UI", 10, "bold" if reason == "expired" else "normal"),
            justify="left",
        ).pack(padx=20, anchor="w")

        token_var = tk.StringVar()
        SoftEntry(win, textvariable=token_var, width=42).pack(
            padx=20, pady=(16, 8), fill="x"
        )

        server_var = tk.StringVar(
            value=(lic.get_server_url() if lic else DEFAULT_LICENSE_SERVER)
        )
        tk.Label(
            win, text="Server license (URL):", bg=COLOR_PANEL,
            fg=COLOR_TEXT_DIM, font=("Segoe UI", 9),
        ).pack(padx=20, anchor="w")
        SoftEntry(win, textvariable=server_var, width=42).pack(
            padx=20, pady=(4, 8), fill="x"
        )

        status = tk.Label(
            win,
            text=("Bạn cần mua token để sử dụng tiếp." if reason == "expired" else ""),
            bg=COLOR_PANEL, fg=COLOR_ERROR,
            font=("Segoe UI", 9), wraplength=440, justify="left",
        )
        status.pack(padx=20, anchor="w")

        def _do_activate():
            if not lic:
                status.config(text="Thiếu license_client")
                return
            tok = token_var.get().strip()
            if not tok:
                status.config(text="Vui lòng nhập token")
                return
            url = server_var.get().strip()
            if url:
                lic.set_server_url(url)
            status.config(text="Đang kích hoạt…", fg=COLOR_WARNING)
            win.update_idletasks()

            def _worker():
                ok, msg, _ = lic.activate(tok)
                def _done():
                    if ok:
                        self._license_ok = True
                        status.config(text=f"✅ {msg}", fg=COLOR_SUCCESS)
                        if hasattr(self, "_license_status_var"):
                            self._license_status_var.set(f"✅ {msg}")
                        self._log(f"Kích hoạt OK: {msg}", "ok")
                        self._license_dialog = None
                        win.after(400, win.destroy)
                        self._bootstrap_saved_data()
                        self._schedule_license_watch()
                    else:
                        status.config(text=f"❌ {msg}", fg=COLOR_ERROR)
                self.after(0, _done)

            threading.Thread(target=_worker, daemon=True).start()

        btn_row = tk.Frame(win, bg=COLOR_PANEL)
        btn_row.pack(pady=16)
        HoverButton(
            btn_row, text="  Kích hoạt  ", command=_do_activate,
            bg=COLOR_BUTTON, fg="white", font=("Segoe UI", 11, "bold"),
            padx=22, pady=10,
        ).pack(side="left", padx=6)

        def _open_buy():
            import webbrowser
            url = (server_var.get() or DEFAULT_LICENSE_SERVER).rstrip("/")
            webbrowser.open(url)

        HoverButton(
            btn_row, text="  Mua token  ", command=_open_buy,
            bg=COLOR_SURFACE, fg=COLOR_ACCENT2, hover_bg="#FFD7B5",
            font=("Segoe UI", 11, "bold"), padx=16, pady=10,
        ).pack(side="left", padx=6)

        def _on_close_lic():
            if not self._license_ok:
                if messagebox.askyesno(
                    "Thoát?",
                    "Chưa có token hợp lệ. Bạn muốn thoát app?",
                    parent=win,
                ):
                    self._license_dialog = None
                    win.destroy()
                    self.destroy()
            else:
                self._license_dialog = None
                win.destroy()

        win.protocol("WM_DELETE_WINDOW", _on_close_lic)

    def _bootstrap_saved_data(self):
        """Load cookies / nhóm / nháp sau khi UI đã hiện."""
        if not getattr(self, "_license_ok", False):
            return
        def _bg():
            cookies_ok = False
            if COOKIES_FILE.exists():
                cookies_ok = self.backend.load_cookies(COOKIES_FILE)
            elif LEGACY_COOKIES_FILE.exists():
                cookies_ok = self.backend.load_cookies(LEGACY_COOKIES_FILE)
                if cookies_ok:
                    try:
                        self.backend.save_cookies(COOKIES_FILE)
                    except Exception:
                        pass
            if cookies_ok:
                self.backend.load_saved_tokens()
                self.after(0, self._on_login_success_ui)
                def _check():
                    valid, msg = self.backend.verify_session()
                    if valid:
                        self.after(0, self._on_login_success_ui)
                        try:
                            self.backend.save_tokens()
                        except Exception:
                            pass
                    else:
                        self.after(0, lambda: self._status_var.set(f"● {msg}"))
                threading.Thread(target=_check, daemon=True).start()

            groups = _read_json(GROUPS_FILE, [])
            if isinstance(groups, list) and groups:
                self.after(0, lambda: self._restore_groups(groups))

            draft = _read_json(DRAFT_FILE, {}) or {}
            if draft:
                self.after(0, lambda: self._restore_draft(draft))

        threading.Thread(target=_bg, daemon=True).start()

    def _restore_groups(self, groups: list):
        self.groups = groups
        self._on_groups_loaded(groups)
        self._log(f"Đã tải {len(groups)} nhóm đã lưu", "ok")

    def _restore_draft(self, draft: dict):
        msg = draft.get("message") or ""
        if msg and hasattr(self, "_msg_text"):
            self._msg_text.delete("1.0", "end")
            self._msg_text.insert("1.0", msg)
        images = draft.get("images") or []
        if not images:
            one = draft.get("image") or ""
            if one:
                images = [one]
        images = [p for p in images if Path(p).is_file()]
        if hasattr(self, "_image_paths"):
            self._image_paths = images[:8]
            self._sync_image_ui()
        delay = draft.get("delay")
        if delay is not None and hasattr(self, "_delay_var"):
            try:
                self._delay_var.set(float(delay))
            except Exception:
                pass
        mode = draft.get("image_spin_mode")
        if mode and hasattr(self, "_img_spin_mode"):
            self._img_spin_mode.set(mode)

    def _persist_groups(self):
        try:
            _write_json(GROUPS_FILE, self.groups)
        except Exception:
            pass

    def _persist_draft(self, copy_image: bool = False):
        try:
            message = ""
            if hasattr(self, "_msg_text"):
                message = self._msg_text.get("1.0", "end").rstrip("\n")
            images = list(getattr(self, "_image_paths", []) or [])
            if copy_image and images:
                cached = []
                for p in images:
                    if Path(p).is_file():
                        cached.append(self._cache_image(p))
                self._image_paths = cached
                images = cached
                self._sync_image_ui()
            delay = 20.0
            if hasattr(self, "_delay_var"):
                try:
                    delay = float(self._delay_var.get())
                except Exception:
                    pass
            mode = "rotate"
            if hasattr(self, "_img_spin_mode"):
                mode = self._img_spin_mode.get() or "rotate"
            _write_json(DRAFT_FILE, {
                "message": message,
                "image": images[0] if images else "",
                "images": images,
                "image_spin_mode": mode,
                "delay": delay,
                "saved_at": time.time(),
            })
        except Exception:
            pass

    def _cache_image(self, image_path: str) -> str:
        """Copy ảnh vào ~/.fb_poster/images để mở lại tool vẫn còn."""
        src = Path(image_path)
        if not src.is_file():
            return image_path
        _ensure_data_dir()
        try:
            if src.resolve().parent == IMAGES_DIR.resolve():
                return str(src)
        except Exception:
            pass
        dest = IMAGES_DIR / f"draft_{int(time.time())}_{uuid.uuid4().hex[:6]}_{src.name}"
        try:
            shutil.copy2(src, dest)
            return str(dest)
        except Exception:
            return image_path

    def _sync_image_ui(self):
        """Cập nhật ô hiển thị danh sách ảnh spin."""
        paths = getattr(self, "_image_paths", []) or []
        if hasattr(self, "_image_var"):
            if not paths:
                self._image_var.set("")
            elif len(paths) == 1:
                self._image_var.set(paths[0])
            else:
                names = [Path(p).name for p in paths]
                self._image_var.set(f"{len(paths)} ảnh: " + " | ".join(names))
        if hasattr(self, "_img_count_var"):
            n = len(paths)
            if n == 0:
                self._img_count_var.set("Chưa chọn ảnh")
            elif n == 1:
                self._img_count_var.set("1 ảnh (không spin)")
            else:
                self._img_count_var.set(f"{n} ảnh — spin mỗi nhóm 1 tấm khác nhau")

    def _schedule_draft_save(self, *_args):
        if self._draft_save_job:
            try:
                self.after_cancel(self._draft_save_job)
            except Exception:
                pass
        self._draft_save_job = self.after(800, self._persist_draft)

    def _on_close(self):
        self._persist_draft(copy_image=True)
        self._persist_groups()
        try:
            if self.backend.logged_in:
                self.backend.save_cookies()
                self.backend.save_tokens()
        except Exception:
            pass
        self.destroy()

    def _auto_login(self):
        # Giữ tương thích — bootstrap đã lo
        pass

    # ── UI BUILD ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header cam
        header_wrap = tk.Frame(self, bg=COLOR_HEADER, height=64)
        header_wrap.pack(fill="x", side="top")
        header_wrap.pack_propagate(False)

        header = tk.Frame(header_wrap, bg=COLOR_HEADER)
        header.pack(fill="both", expand=True)

        logo_frame = tk.Frame(header, bg=COLOR_HEADER)
        logo_frame.pack(side="left", padx=20, pady=8)
        tk.Label(logo_frame, text="📣", bg=COLOR_HEADER, fg=COLOR_HEADER_TEXT,
                 font=("Segoe UI", 20)).pack(side="left")
        tk.Label(logo_frame, text=f"  {APP_TITLE}", bg=COLOR_HEADER, fg=COLOR_HEADER_TEXT,
                 font=("Segoe UI", 16, "bold")).pack(side="left")
        tk.Label(logo_frame, text=f"  v{APP_VERSION}", bg=COLOR_HEADER, fg="#FFEDD5",
                 font=("Segoe UI", 9)).pack(side="left", pady=(6, 0))
        tk.Label(
            logo_frame,
            text=f"  ·  {APP_COPYRIGHT}",
            bg=COLOR_HEADER,
            fg="#FED7AA",
            font=("Segoe UI", 8),
        ).pack(side="left", pady=(8, 0))

        status_frame = tk.Frame(header, bg="#C2410C", padx=16, pady=8)
        status_frame.pack(side="right", padx=20, pady=14)
        self._status_var = tk.StringVar(value="○ Chưa đăng nhập")
        tk.Label(status_frame, textvariable=self._status_var, bg="#C2410C",
                 fg=COLOR_HEADER_TEXT, font=("Segoe UI", 10, "bold")).pack()

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Custom.TNotebook", background=COLOR_BG, borderwidth=0)
        style.configure(
            "Custom.TNotebook.Tab",
            background=COLOR_SURFACE, foreground=COLOR_TEXT_DIM,
            padding=[18, 10], font=("Segoe UI", 10), borderwidth=0,
        )
        style.map(
            "Custom.TNotebook.Tab",
            background=[("selected", COLOR_PANEL)],
            foreground=[("selected", COLOR_ACCENT2)],
        )
        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor="#FFEDD5", background=COLOR_ACCENT,
            borderwidth=0, lightcolor=COLOR_ACCENT, darkcolor=COLOR_ACCENT,
        )

        content = tk.Frame(self, bg=COLOR_BG)
        content.pack(fill="both", expand=True, padx=12, pady=(8, 4))

        nb = ttk.Notebook(content, style="Custom.TNotebook")
        nb.pack(fill="both", expand=True)

        self._tab_login = tk.Frame(nb, bg=COLOR_BG)
        self._tab_groups = tk.Frame(nb, bg=COLOR_BG)
        self._tab_post = tk.Frame(nb, bg=COLOR_BG)
        self._tab_log = tk.Frame(nb, bg=COLOR_BG)
        self._tab_settings = tk.Frame(nb, bg=COLOR_BG)

        nb.add(self._tab_login, text="  🔑  Đăng nhập  ")
        nb.add(self._tab_groups, text="  👥  Nhóm của tôi  ")
        nb.add(self._tab_post, text="  📝  Đăng bài  ")
        nb.add(self._tab_log, text="  📋  Nhật ký  ")
        nb.add(self._tab_settings, text="  ⚙️  Cài đặt  ")

        self._nb = nb
        self._build_login_tab()
        self._build_groups_tab()
        self._build_post_tab()
        self._build_log_tab()
        self._build_settings_tab()

        foot = tk.Frame(self, bg=COLOR_BG)
        foot.pack(fill="x", side="bottom", padx=12, pady=(0, 8))
        tk.Label(
            foot,
            text=f"{APP_COPYRIGHT}  ·  Hỗ trợ Zalo/SĐT: {APP_SUPPORT_ZALO}",
            bg=COLOR_BG,
            fg=COLOR_TEXT_DIM,
            font=("Segoe UI", 8),
        ).pack(anchor="e")

        if self.backend.logged_in:
            self._on_login_success_ui()

    # ── LOGIN TAB ─────────────────────────────────────────────────────────────

    def _build_login_tab(self):
        tab = self._tab_login
        outer = tk.Frame(tab, bg=COLOR_BG)
        outer.pack(expand=True)

        card = tk.Frame(outer, bg=COLOR_PANEL, padx=40, pady=36,
                        highlightbackground=COLOR_BORDER, highlightthickness=1)
        card.pack(pady=40, padx=40)

        tk.Label(card, text="🔐  Đăng nhập Facebook", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Segoe UI", 15, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 4))
        tk.Label(card, text="Khuyến nghị: dùng Cookies từ Chrome (tab bên cạnh)",
                 bg=COLOR_PANEL, fg=COLOR_TEXT_DIM,
                 font=("Segoe UI", 9)).grid(row=1, column=0, columnspan=2, pady=(0, 16))

        # ── Notebook bên trong: Email/Password vs Cookie ──
        inner_nb = ttk.Notebook(card, style="Custom.TNotebook")
        inner_nb.grid(row=2, column=0, columnspan=2)

        pane_pw = tk.Frame(inner_nb, bg=COLOR_PANEL, padx=20, pady=16)
        pane_ck = tk.Frame(inner_nb, bg=COLOR_PANEL, padx=20, pady=16)
        inner_nb.add(pane_pw, text="  Email / Mật khẩu  ")
        inner_nb.add(pane_ck, text="  Nhập Cookies  ")

        # Password pane
        self._email_var = tk.StringVar()
        self._pass_var = tk.StringVar()

        def lbl(p, text, r):
            tk.Label(p, text=text, bg=COLOR_PANEL, fg=COLOR_TEXT_DIM,
                     font=("Segoe UI", 10)).grid(row=r, column=0, sticky="w", pady=4)

        lbl(pane_pw, "Email:", 0)
        SoftEntry(pane_pw, textvariable=self._email_var, width=36).grid(
            row=0, column=1, padx=(8, 0), pady=6, sticky="ew"
        )

        lbl(pane_pw, "Mật khẩu:", 1)
        SoftEntry(pane_pw, textvariable=self._pass_var, width=36, show="●").grid(
            row=1, column=1, padx=(8, 0), pady=6, sticky="ew"
        )

        self._login_btn = HoverButton(
            pane_pw, text="  Đăng nhập  ", command=self._do_login,
            bg=COLOR_BUTTON, fg="white", font=("Segoe UI", 11, "bold"),
            relief="flat", cursor="hand2", padx=20, pady=8,
        )
        self._login_btn.grid(row=2, column=0, columnspan=2, pady=(16, 0))

        # Cookies pane
        tk.Label(pane_ck, text="Dán cookies từ trình duyệt vào đây:", bg=COLOR_PANEL,
                 fg=COLOR_TEXT_DIM, font=("Segoe UI", 10)).pack(anchor="w")
        tk.Label(
            pane_ck,
            text="(Cài extension Cookie-Editor → Export → Header String)",
            bg=COLOR_PANEL, fg=COLOR_TEXT_DIM, font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(0, 6))

        self._cookie_text = scrolledtext.ScrolledText(
            pane_ck, width=52, height=5,
            bg=COLOR_INPUT_BG, fg=COLOR_INPUT_FG, insertbackground=COLOR_TEXT,
            relief="flat", font=("Consolas", 9),
        )
        self._cookie_text.pack(fill="x")

        HoverButton(
            pane_ck, text="  Xác nhận Cookies  ", command=self._do_set_cookies,
            bg=COLOR_ACCENT2, fg="white", font=("Segoe UI", 11, "bold"),
            relief="flat", cursor="hand2", padx=20, pady=8,
        ).pack(pady=(12, 0))

        # Status
        self._login_status = tk.Label(card, text="", bg=COLOR_PANEL,
                                      fg=COLOR_TEXT_DIM, font=("Segoe UI", 10), wraplength=440)
        self._login_status.grid(row=3, column=0, columnspan=2, pady=(16, 0))

    def _do_login(self):
        email = self._email_var.get().strip()
        pw = self._pass_var.get().strip()
        if not email or not pw:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập email và mật khẩu.")
            return
        self._login_btn.config(state="disabled", text="Đang đăng nhập…")
        self._login_status.config(text="Đang kết nối tới Facebook…", fg=COLOR_WARNING)

        def _worker():
            ok, msg = self.backend.login(email, pw)
            self.after(0, lambda: self._on_login_done(ok, msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_login_done(self, ok: bool, msg: str):
        self._login_btn.config(state="normal", text="  Đăng nhập  ")
        if ok:
            self.backend.save_cookies(COOKIES_FILE)
            self._login_status.config(text=f"✅ {msg}", fg=COLOR_SUCCESS)
            self._on_login_success_ui()
        else:
            self._login_status.config(text=f"❌ {msg}", fg=COLOR_ERROR)
            low = msg.lower()
            if "sai tài khoản" in low or "mật khẩu" in low:
                messagebox.showerror(
                    "Sai tài khoản hoặc mật khẩu",
                    "Tài khoản hoặc mật khẩu Facebook không đúng.\n\n"
                    "• Kiểm tra lại email / số điện thoại và mật khẩu\n"
                    "• Tắt Caps Lock nếu đang bật\n"
                    "• Hoặc dùng tab 'Nhập Cookies' (ổn định hơn)",
                )
            elif "checkpoint" in low or "chặn" in low or "cookies" in low:
                messagebox.showinfo(
                    "Gợi ý: Dùng Cookies",
                    "Đăng nhập bằng email/mật khẩu thất bại.\n\n"
                    "👉 Hãy dùng tab 'Nhập Cookies':\n\n"
                    "1. Mở Chrome, đăng nhập Facebook bình thường\n"
                    "2. Cài extension 'Cookie-Editor' (miễn phí)\n"
                    "3. Mở extension → Export → Header String → Copy\n"
                    "4. Quay lại tab 'Nhập Cookies' → Dán vào ô → Xác nhận",
                )
            else:
                messagebox.showerror("Đăng nhập thất bại", msg)

    def _do_set_cookies(self):
        cookie_str = self._cookie_text.get("1.0", "end").strip()
        if not cookie_str:
            messagebox.showwarning("Thiếu cookies", "Vui lòng dán cookies vào ô trên.")
            return
        ok = self.backend.set_cookies_from_string(cookie_str)
        if not ok:
            self._login_status.config(
                text="⚠️ Không tìm thấy c_user trong cookies. Thử lại.", fg=COLOR_WARNING
            )
            return

        self.backend.save_cookies(COOKIES_FILE)
        self._login_status.config(text="🔄 Đang kiểm tra cookies…", fg=COLOR_WARNING)
        self.update_idletasks()

        def _verify():
            valid, msg = self.backend.verify_session()
            self.after(0, lambda: self._on_cookies_verified(valid, msg))

        threading.Thread(target=_verify, daemon=True).start()

    def _on_cookies_verified(self, valid: bool, msg: str):
        if valid:
            self._login_status.config(text="✅ Cookies hợp lệ! Đã lưu.", fg=COLOR_SUCCESS)
            self._on_login_success_ui()
        else:
            self._login_status.config(text=f"❌ {msg}", fg=COLOR_ERROR)
            self._status_var.set("🔴 Cookies không hợp lệ")
            messagebox.showerror(
                "Cookies không hoạt động",
                f"{msg}\n\n"
                "Cách lấy cookies đúng:\n"
                "1. Mở Chrome → đăng nhập facebook.com\n"
                "2. Cài extension Cookie-Editor\n"
                "3. Export → Header String (KHÔNG phải JSON)\n"
                "4. Copy TOÀN BỘ chuỗi (phải có c_user và xs)\n"
                "5. Dán lại vào đây",
            )

    def _on_login_success_ui(self):
        valid, msg = self.backend.verify_session()
        if not valid:
            self._status_var.set(f"🔴 {msg}")
            self._log(f"Session không hợp lệ: {msg}", "err")
            return
        name = self.backend.get_profile_name()
        self._status_var.set(f"🟢 Đã đăng nhập: {name}")
        self._log(f"Đã đăng nhập: {name} (UID: {msg})", "ok")

    # ── GROUPS TAB ────────────────────────────────────────────────────────────

    def _build_groups_tab(self):
        tab = self._tab_groups

        top = tk.Frame(tab, bg=COLOR_BG)
        top.pack(fill="x", padx=16, pady=(12, 6))

        tk.Label(top, text="Danh sách nhóm Facebook của bạn",
                 bg=COLOR_BG, fg=COLOR_TEXT, font=("Segoe UI", 12, "bold")).pack(side="left")

        btn_frame = tk.Frame(top, bg=COLOR_BG)
        btn_frame.pack(side="right")

        HoverButton(
            btn_frame, text="🔍  Quét nhóm", command=self._scan_groups,
            bg=COLOR_BUTTON, fg="white", font=("Segoe UI", 10, "bold"),
            relief="flat", cursor="hand2", padx=14, pady=6,
        ).pack(side="left", padx=4)

        HoverButton(
            btn_frame, text="✅  Chọn tất cả", command=self._select_all_groups,
            bg=COLOR_CARD, fg=COLOR_TEXT, font=("Segoe UI", 10),
            relief="flat", cursor="hand2", padx=10, pady=6,
        ).pack(side="left", padx=4)

        HoverButton(
            btn_frame, text="❌  Bỏ chọn tất cả", command=self._deselect_all_groups,
            bg=COLOR_CARD, fg=COLOR_TEXT, font=("Segoe UI", 10),
            relief="flat", cursor="hand2", padx=10, pady=6,
        ).pack(side="left", padx=4)

        HoverButton(
            btn_frame, text="💾  Lưu danh sách", command=self._save_groups,
            bg=COLOR_ACCENT2, fg="white", font=("Segoe UI", 10),
            relief="flat", cursor="hand2", padx=10, pady=6,
        ).pack(side="left", padx=4)

        HoverButton(
            btn_frame, text="📂  Tải từ file", command=self._load_groups_file,
            bg=COLOR_ACCENT2, fg="white", font=("Segoe UI", 10),
            relief="flat", cursor="hand2", padx=10, pady=6,
        ).pack(side="left", padx=4)

        # Scan progress
        self._scan_progress_var = tk.StringVar(value="")
        tk.Label(tab, textvariable=self._scan_progress_var, bg=COLOR_BG,
                 fg=COLOR_TEXT_DIM, font=("Segoe UI", 9)).pack(anchor="w", padx=16)

        # ── Nhập ID nhóm thủ công ───────────────────────────────────────
        manual_frame = tk.Frame(tab, bg=COLOR_PANEL)
        manual_frame.pack(fill="x", padx=16, pady=(0, 4))

        tk.Label(manual_frame, text="➕ Thêm nhóm thủ công:", bg=COLOR_PANEL,
                 fg=COLOR_TEXT_DIM, font=("Segoe UI", 9)).pack(side="left", padx=(8, 4))

        self._manual_id_var = tk.StringVar()
        tk.Entry(
            manual_frame, textvariable=self._manual_id_var, width=20,
            bg=COLOR_INPUT_BG, fg=COLOR_INPUT_FG, insertbackground=COLOR_TEXT,
            relief="flat", font=("Segoe UI", 9),
        ).pack(side="left", ipady=3, padx=(0, 4))

        tk.Label(manual_frame, text="Tên:", bg=COLOR_PANEL,
                 fg=COLOR_TEXT_DIM, font=("Segoe UI", 9)).pack(side="left")

        self._manual_name_var = tk.StringVar()
        tk.Entry(
            manual_frame, textvariable=self._manual_name_var, width=24,
            bg=COLOR_INPUT_BG, fg=COLOR_INPUT_FG, insertbackground=COLOR_TEXT,
            relief="flat", font=("Segoe UI", 9),
        ).pack(side="left", ipady=3, padx=(4, 4))

        HoverButton(
            manual_frame, text="Thêm", command=self._add_manual_group,
            bg=COLOR_ACCENT2, fg="white", relief="flat", cursor="hand2",
            font=("Segoe UI", 9, "bold"), padx=10, pady=3,
        ).pack(side="left")

        tk.Label(
            manual_frame,
            text="(ID nhóm: lấy từ URL facebook.com/groups/ID)",
            bg=COLOR_PANEL, fg=COLOR_TEXT_DIM, font=("Segoe UI", 8),
        ).pack(side="left", padx=(8, 0))

        # Group list with checkboxes
        list_frame = tk.Frame(tab, bg=COLOR_PANEL)
        list_frame.pack(fill="both", expand=True, padx=16, pady=(4, 12))

        canvas = tk.Canvas(list_frame, bg=COLOR_PANEL, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self._groups_inner = tk.Frame(canvas, bg=COLOR_PANEL)

        self._groups_inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.create_window((0, 0), window=self._groups_inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Bind mousewheel
        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        self._group_vars: list[tuple[tk.BooleanVar, dict]] = []
        self._groups_canvas = canvas

        # Count label
        self._group_count_var = tk.StringVar(value="0 nhóm — 0 đã chọn")
        tk.Label(tab, textvariable=self._group_count_var, bg=COLOR_BG,
                 fg=COLOR_TEXT_DIM, font=("Segoe UI", 9)).pack(anchor="w", padx=16, pady=(0, 8))

    def _scan_groups(self):
        if not self.backend.logged_in:
            messagebox.showwarning("Chưa đăng nhập", "Vui lòng nhập cookies trước (tab Đăng nhập).")
            return

        valid, msg = self.backend.verify_session()
        if not valid:
            messagebox.showerror("Cookies hết hạn", f"{msg}\n\nVui lòng lấy cookies mới từ Chrome.")
            self._status_var.set(f"🔴 {msg}")
            return

        self._scan_progress_var.set("🔄 Đang quét nhóm…")

        def _worker():
            groups = self.backend.scan_groups(
                progress_cb=lambda msg: self.after(0, lambda m=msg: self._scan_progress_var.set(m))
            )
            self.after(0, lambda: self._on_groups_loaded(groups))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_groups_loaded(self, groups: list[dict]):
        self.groups = groups
        self._persist_groups()
        if groups:
            self._scan_progress_var.set(f"✅ Quét xong — tìm thấy {len(groups)} nhóm (đã lưu)")
            self._log(f"Quét xong: {len(groups)} nhóm — đã lưu tự động", "ok")
        else:
            self._scan_progress_var.set(
                "⚠️ Không tìm thấy nhóm nào — Facebook thay đổi giao diện, hãy thêm thủ công bên dưới"
            )
            self._log("Quét nhóm không ra kết quả.", "warn")
            self._log("➡ Hướng dẫn lấy ID nhóm:", "warn")
            self._log("  1. Vào nhóm trên Facebook (Chrome)", "info")
            self._log("  2. Xem URL: facebook.com/groups/ID_NHOM", "info")
            self._log("  3. Nhập ID vào ô 'Thêm nhóm thủ công' bên dưới", "info")
            messagebox.showinfo(
                "Không tìm thấy nhóm tự động",
                "Không quét được nhóm tự động.\n\n"
                "Facebook thay đổi giao diện thường xuyên.\n\n"
                "👉 Cách thêm nhóm thủ công:\n"
                "1. Mở Chrome, vào facebook.com/groups\n"
                "2. Bấm vào từng nhóm, xem URL:\n"
                "   facebook.com/groups/123456789\n"
                "3. Sao chép số ID (123456789)\n"
                "4. Dán vào ô 'Thêm nhóm thủ công' trong app",
            )
        self._render_group_list()

    def _render_group_list(self):
        for w in self._groups_inner.winfo_children():
            w.destroy()
        self._group_vars.clear()

        for g in self.groups:
            var = tk.BooleanVar(value=True)
            self._group_vars.append((var, g))

            row = tk.Frame(self._groups_inner, bg=COLOR_PANEL)
            row.pack(fill="x", padx=8, pady=1)

            cb = tk.Checkbutton(
                row, variable=var, bg=COLOR_PANEL,
                activebackground=COLOR_PANEL, selectcolor=COLOR_CARD,
                command=self._update_group_count,
            )
            cb.pack(side="left")

            tk.Label(row, text=g["name"], bg=COLOR_PANEL, fg=COLOR_TEXT,
                     font=("Segoe UI", 10), anchor="w").pack(side="left")
            tk.Label(row, text=f"  [{g['id']}]", bg=COLOR_PANEL, fg=COLOR_TEXT_DIM,
                     font=("Segoe UI", 9)).pack(side="left")

        self._update_group_count()

    def _select_all_groups(self):
        for var, _ in self._group_vars:
            var.set(True)
        self._update_group_count()

    def _deselect_all_groups(self):
        for var, _ in self._group_vars:
            var.set(False)
        self._update_group_count()

    def _update_group_count(self):
        total = len(self._group_vars)
        selected = sum(1 for v, _ in self._group_vars if v.get())
        self._group_count_var.set(f"{total} nhóm — {selected} đã chọn")

    def _save_groups(self):
        if not self.groups:
            messagebox.showinfo("Trống", "Chưa có nhóm nào. Hãy quét trước.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Lưu danh sách nhóm",
        )
        if path:
            Path(path).write_text(json.dumps(self.groups, ensure_ascii=False, indent=2), encoding="utf-8")
            messagebox.showinfo("Đã lưu", f"Đã lưu {len(self.groups)} nhóm vào:\n{path}")

    def _load_groups_file(self):
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Tải danh sách nhóm",
        )
        if path:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            self.groups = data
            self._on_groups_loaded(data)

    def _add_manual_group(self):
        gid = self._manual_id_var.get().strip()
        name = self._manual_name_var.get().strip()

        # Trích xuất ID từ URL nếu người dùng dán URL
        url_m = re.search(r'facebook\.com/groups/(\d+)', gid)
        if url_m:
            gid = url_m.group(1)

        if not gid or not gid.isdigit():
            messagebox.showwarning(
                "ID không hợp lệ",
                "Vui lòng nhập ID nhóm (chỉ gồm chữ số).\n"
                "Ví dụ: 123456789\n\n"
                "Hoặc dán cả URL: https://www.facebook.com/groups/123456789",
            )
            return

        if not name:
            name = f"Nhóm {gid}"

        # Kiểm tra trùng
        existing_ids = {g["id"] for g in self.groups}
        if gid in existing_ids:
            messagebox.showinfo("Trùng", f"Nhóm ID {gid} đã có trong danh sách.")
            return

        self.groups.append({"id": gid, "name": name})
        self._render_group_list()
        self._persist_groups()
        self._manual_id_var.set("")
        self._manual_name_var.set("")
        self._log(f"Đã thêm nhóm thủ công: {name} ({gid})", "ok")

    # ── POST TAB ──────────────────────────────────────────────────────────────

    def _build_post_tab(self):
        tab = self._tab_post

        # Left compose card
        left_wrap = tk.Frame(tab, bg=COLOR_BG)
        left_wrap.pack(side="left", fill="both", expand=True, padx=(14, 8), pady=12)

        left_card = tk.Frame(
            left_wrap, bg=COLOR_PANEL,
            highlightbackground=COLOR_BORDER, highlightthickness=1,
            highlightcolor=COLOR_ACCENT, padx=20, pady=18,
        )
        left_card.pack(fill="both", expand=True)
        left = left_card

        tk.Label(left, text="Soạn bài đăng", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(
            left,
            text=(
                "✅ Đã đăng   ⏳ Chờ duyệt   ❌ Lỗi\n"
                "Spin chữ: {Câu A|Câu B|Câu C}  •  Spin ảnh: mỗi nhóm 1 tấm khác nhau"
            ),
            bg=COLOR_PANEL, fg=COLOR_ACCENT2, font=("Segoe UI", 10),
            justify="left",
        ).pack(anchor="w", pady=(4, 12))

        tk.Label(left, text="Nội dung", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")

        msg_frame = tk.Frame(left, bg=COLOR_BORDER, padx=2, pady=2)
        msg_frame.pack(fill="both", expand=True, pady=(6, 12))
        self._msg_text = scrolledtext.ScrolledText(
            msg_frame, height=10, bg="#FFFFFF", fg=COLOR_INPUT_FG,
            insertbackground=COLOR_TEXT, relief="flat",
            font=("Segoe UI", 12), wrap=tk.WORD, padx=12, pady=10,
        )
        self._msg_text.pack(fill="both", expand=True)
        self._msg_text.bind("<KeyRelease>", self._schedule_draft_save)

        # Images — spin nhiều tấm chống spam
        img_label_row = tk.Frame(left, bg=COLOR_PANEL)
        img_label_row.pack(fill="x", pady=(4, 0))
        tk.Label(img_label_row, text="Ảnh đính kèm (spin nhiều tấm)", bg=COLOR_PANEL,
                 fg=COLOR_TEXT, font=("Segoe UI", 10, "bold")).pack(side="left")
        self._img_count_var = tk.StringVar(value="Chưa chọn ảnh")
        tk.Label(
            img_label_row, textvariable=self._img_count_var,
            bg=COLOR_PANEL, fg=COLOR_ACCENT2, font=("Segoe UI", 9),
        ).pack(side="right")

        img_row = tk.Frame(left, bg=COLOR_PANEL)
        img_row.pack(fill="x", pady=6)

        self._image_paths: list[str] = []
        self._image_var = tk.StringVar()
        img_box = SoftEntry(img_row, textvariable=self._image_var, width=32)
        img_box.pack(side="left", padx=(0, 6), fill="x", expand=True)

        HoverButton(
            img_row, text="  Chọn nhiều ảnh  ", command=self._browse_image,
            bg=COLOR_SURFACE, fg=COLOR_ACCENT2, hover_bg="#FFD7B5",
            font=("Segoe UI", 10, "bold"), padx=12, pady=8,
        ).pack(side="left")
        HoverButton(
            img_row, text=" +Thêm ", command=self._browse_image_add,
            bg=COLOR_SURFACE, fg=COLOR_ACCENT2, hover_bg="#FFD7B5",
            font=("Segoe UI", 10, "bold"), padx=10, pady=8,
        ).pack(side="left", padx=3)
        HoverButton(
            img_row, text=" Xóa ", command=self._clear_images,
            bg="#FEE2E2", fg=COLOR_ERROR, hover_bg="#FECACA",
            font=("Segoe UI", 10, "bold"), padx=10, pady=8,
        ).pack(side="left", padx=2)

        spin_row = tk.Frame(left, bg=COLOR_PANEL)
        spin_row.pack(fill="x", pady=(2, 4))
        self._img_spin_mode = tk.StringVar(value="rotate")
        tk.Label(spin_row, text="Cách spin ảnh:", bg=COLOR_PANEL, fg=COLOR_TEXT_DIM,
                 font=("Segoe UI", 9)).pack(side="left")
        for val, label in (("rotate", "Xoay vòng"), ("random", "Ngẫu nhiên")):
            tk.Radiobutton(
                spin_row, text=label, variable=self._img_spin_mode, value=val,
                bg=COLOR_PANEL, fg=COLOR_TEXT, selectcolor=COLOR_SURFACE,
                activebackground=COLOR_PANEL, font=("Segoe UI", 9),
                command=self._schedule_draft_save,
            ).pack(side="left", padx=(8, 0))
        tk.Label(
            spin_row, text="(nhóm 1→ảnh1, nhóm 2→ảnh2… tránh spam)",
            bg=COLOR_PANEL, fg=COLOR_TEXT_DIM, font=("Segoe UI", 8),
        ).pack(side="left", padx=(10, 0))

        # Delay + elapsed
        delay_row = tk.Frame(left, bg=COLOR_PANEL)
        delay_row.pack(fill="x", pady=(12, 4))
        tk.Label(delay_row, text="Delay (giây)", bg=COLOR_PANEL,
                 fg=COLOR_TEXT, font=("Segoe UI", 10, "bold")).pack(side="left")
        self._delay_var = tk.DoubleVar(value=25)
        delay_spin = tk.Spinbox(
            delay_row, from_=8, to=300, textvariable=self._delay_var,
            width=5, bg="#FFFFFF", fg=COLOR_INPUT_FG, relief="flat",
            font=("Segoe UI", 12, "bold"), buttonbackground=COLOR_SURFACE,
            insertbackground=COLOR_TEXT, highlightthickness=1,
            highlightbackground=COLOR_BORDER, highlightcolor=COLOR_ACCENT,
            command=self._schedule_draft_save,
        )
        delay_spin.pack(side="left", padx=(10, 4), ipady=5)
        tk.Label(
            delay_row, text="(≥25s tránh FB chặn spam)",
            bg=COLOR_PANEL, fg=COLOR_TEXT_DIM, font=("Segoe UI", 9),
        ).pack(side="left", padx=(4, 0))

        self._elapsed_var = tk.StringVar(value="⏱ Thời gian: 00:00")
        tk.Label(
            delay_row, textvariable=self._elapsed_var,
            bg=COLOR_PANEL, fg=COLOR_ACCENT2, font=("Segoe UI", 12, "bold"),
        ).pack(side="right")

        # Start / Stop — to, bo tròn
        btn_row = tk.Frame(left, bg=COLOR_PANEL)
        btn_row.pack(fill="x", pady=(16, 6))

        self._post_btn = RoundedButton(
            btn_row, text="🚀  Bắt đầu đăng bài", command=self._start_posting,
            bg=COLOR_BUTTON, fg="#FFFFFF", hover_bg=COLOR_BUTTON_HOVER,
            radius=20, font=("Segoe UI", 14, "bold"), padx=32, pady=16,
        )
        self._post_btn.pack(side="left", padx=(0, 12))

        self._stop_btn = RoundedButton(
            btn_row, text="⏹  Dừng", command=self._stop_posting,
            bg="#FFFFFF", fg=COLOR_ERROR, hover_bg="#FEE2E2",
            disabled_bg="#F5F5F4", disabled_fg="#A8A29E",
            outline=COLOR_ERROR, radius=20,
            font=("Segoe UI", 14, "bold"), padx=28, pady=16,
        )
        self._stop_btn.pack(side="left")
        self._stop_btn.config(state="disabled")

        # Right progress panel
        right = tk.Frame(
            tab, bg=COLOR_PANEL, width=320,
            highlightbackground=COLOR_BORDER, highlightthickness=1,
            highlightcolor=COLOR_ACCENT,
        )
        right.pack(side="right", fill="y", padx=(0, 14), pady=12)
        right.pack_propagate(False)

        tk.Label(right, text="Tiến trình", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Segoe UI", 14, "bold")).pack(pady=(14, 4), padx=14, anchor="w")

        self._status_line = tk.StringVar(value="Chưa chạy")
        tk.Label(
            right, textvariable=self._status_line, bg=COLOR_PANEL,
            fg=COLOR_TEXT_DIM, font=("Segoe UI", 10), wraplength=280, justify="left",
        ).pack(padx=14, anchor="w")

        # Countdown delay lớn, rõ
        cd_frame = tk.Frame(right, bg=COLOR_SURFACE, padx=12, pady=10)
        cd_frame.pack(fill="x", padx=14, pady=(10, 4))
        tk.Label(
            cd_frame, text="Đếm ngược delay", bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM, font=("Segoe UI", 9),
        ).pack(anchor="w")
        self._countdown_var = tk.StringVar(value="—")
        self._countdown_lbl = tk.Label(
            cd_frame, textvariable=self._countdown_var, bg=COLOR_SURFACE,
            fg=COLOR_ACCENT2, font=("Segoe UI", 28, "bold"),
        )
        self._countdown_lbl.pack(anchor="w")
        self._countdown_hint = tk.StringVar(value="Chờ giữa các nhóm")
        tk.Label(
            cd_frame, textvariable=self._countdown_hint, bg=COLOR_SURFACE,
            fg=COLOR_TEXT_DIM, font=("Segoe UI", 9),
        ).pack(anchor="w")

        style = ttk.Style()
        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor="#FFEDD5", background=COLOR_ACCENT,
            borderwidth=0, lightcolor=COLOR_ACCENT, darkcolor=COLOR_ACCENT,
            thickness=16,
        )
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            right, variable=self._progress_var,
            style="Accent.Horizontal.TProgressbar",
            maximum=100, length=280,
        )
        self._progress_bar.pack(padx=14, pady=(10, 6))

        self._progress_label = tk.Label(
            right, text="0 / 0", bg=COLOR_PANEL,
            fg=COLOR_TEXT, font=("Segoe UI", 13, "bold"),
        )
        self._progress_label.pack()

        stats = tk.Frame(right, bg=COLOR_PANEL)
        stats.pack(fill="x", padx=14, pady=10)

        def stat_lbl(text, color):
            f = tk.Frame(stats, bg=COLOR_SURFACE, padx=10, pady=8)
            f.pack(fill="x", pady=3)
            lbl = tk.Label(f, text="0", bg=COLOR_SURFACE, fg=color,
                           font=("Segoe UI", 16, "bold"), width=3, anchor="e")
            lbl.pack(side="left")
            tk.Label(f, text=f"  {text}", bg=COLOR_SURFACE, fg=COLOR_TEXT,
                     font=("Segoe UI", 11)).pack(side="left")
            return lbl

        self._ok_lbl = stat_lbl("Đã đăng", COLOR_SUCCESS)
        self._pending_lbl = stat_lbl("Chờ duyệt", COLOR_PENDING)
        self._err_lbl = stat_lbl("Lỗi", COLOR_ERROR)
        self._skip_lbl = stat_lbl("Còn lại", COLOR_TEXT_DIM)

        tk.Label(right, text="Log nhanh", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Segoe UI", 11, "bold")).pack(padx=14, anchor="w", pady=(8, 2))
        self._mini_log = LogBox(right, height=10, font=("Consolas", 9))
        self._mini_log.pack(fill="both", expand=True, padx=10, pady=(0, 12))

        self._post_start_ts = None
        self._timer_job = None
        self._last_spin_idx = -1

    def _browse_image(self):
        """Chọn lại danh sách ảnh (thay thế) — giữ Ctrl/Shift để chọn nhiều."""
        paths = filedialog.askopenfilenames(
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif *.bmp *.webp"), ("All files", "*.*")],
            title="Chọn nhiều ảnh để spin (Ctrl hoặc Shift chọn nhiều tấm)",
        )
        if not paths:
            return
        cached = []
        seen_names: set[str] = set()
        for p in list(paths)[:8]:
            if not Path(p).is_file():
                continue
            c = self._cache_image(p)
            # Tránh trùng cùng 1 file nguồn (cùng tên + size)
            key = f"{Path(p).name}:{Path(p).stat().st_size}"
            if key in seen_names:
                continue
            seen_names.add(key)
            cached.append(c)
        self._image_paths = cached
        self._last_spin_idx = -1
        self._sync_image_ui()
        self._persist_draft()
        if len(cached) <= 1:
            self._log(
                f"Đã chọn {len(cached)} ảnh — thêm ≥2 tấm (nút +Thêm) để spin chống spam",
                "warn",
            )
        else:
            self._log(
                f"Đã chọn {len(cached)} ảnh để spin: "
                + ", ".join(Path(p).name for p in cached),
                "ok",
            )

    def _browse_image_add(self):
        """Thêm ảnh vào danh sách spin (tối đa 8)."""
        paths = filedialog.askopenfilenames(
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif *.bmp *.webp"), ("All files", "*.*")],
            title="Thêm ảnh vào bộ spin (có thể chọn nhiều)",
        )
        if not paths:
            return
        current = list(getattr(self, "_image_paths", []) or [])
        existing_keys = set()
        for p in current:
            try:
                existing_keys.add(f"{Path(p).name}:{Path(p).stat().st_size}")
            except Exception:
                existing_keys.add(Path(p).name)
        for p in paths:
            if not Path(p).is_file():
                continue
            try:
                key = f"{Path(p).name}:{Path(p).stat().st_size}"
            except Exception:
                key = Path(p).name
            if key in existing_keys:
                continue
            cached = self._cache_image(p)
            current.append(cached)
            existing_keys.add(key)
            if len(current) >= 8:
                break
        self._image_paths = current[:8]
        self._last_spin_idx = -1
        self._sync_image_ui()
        self._persist_draft()
        self._log(
            f"Danh sách ảnh spin: {len(self._image_paths)} tấm — "
            + ", ".join(Path(p).name for p in self._image_paths),
            "ok",
        )

    def _clear_images(self):
        self._image_paths = []
        self._last_spin_idx = -1
        self._sync_image_ui()
        self._persist_draft()

    def _pick_image_for_group(self, index: int) -> str | None:
        """
        Spin ảnh cho từng nhóm.
        - rotate: xoay vòng 1→2→3→4→1…
        - random: chọn ngẫu nhiên, tránh trùng tấm vừa dùng nếu ≥2 ảnh
        """
        paths = [p for p in (getattr(self, "_image_paths", []) or []) if Path(p).is_file()]
        if not paths:
            one = ""
            if hasattr(self, "_image_var"):
                one = self._image_var.get().strip()
            if one and Path(one).is_file() and " ảnh:" not in one:
                return one
            return None
        mode = "rotate"
        if hasattr(self, "_img_spin_mode"):
            mode = self._img_spin_mode.get() or "rotate"
        if mode == "random":
            if len(paths) == 1:
                self._last_spin_idx = 0
                return paths[0]
            choices = list(range(len(paths)))
            last = getattr(self, "_last_spin_idx", -1)
            if last in choices and len(choices) > 1:
                choices.remove(last)
            pick = random.choice(choices)
            self._last_spin_idx = pick
            return paths[pick]
        pick = (index - 1) % len(paths)
        self._last_spin_idx = pick
        return paths[pick]

    @staticmethod
    def spin_text(text: str) -> str:
        """
        Trộn văn bản dạng {A|B|C} — chọn ngẫu nhiên 1 nhánh.
        Hỗ trợ lồng nhau giới hạn.
        """
        if not text or "{" not in text:
            return text or ""

        def _pick(match: re.Match) -> str:
            options = [o.strip() for o in match.group(1).split("|")]
            options = [o for o in options if o != ""]
            return random.choice(options) if options else ""

        out = text
        for _ in range(25):
            nxt = re.sub(r"\{([^{}]+)\}", _pick, out)
            if nxt == out:
                break
            out = nxt
        return out

    @staticmethod
    def _inject_invisible_noise(text: str) -> str:
        """Chèn ký tự vô hình ngẫu nhiên để bài không hash trùng 100%."""
        if not text:
            return text
        noises = ["\u200b", "\u200c", "\u200d", "\u2060", "\ufeff"]
        chars = list(text)
        # Chèn 2–5 noise vào khoảng trắng / sau dấu câu
        spots = [
            i
            for i, ch in enumerate(chars)
            if ch in " \n.,;:!?" and i + 1 < len(chars)
        ]
        if not spots:
            return text + random.choice(noises)
        for i in sorted(random.sample(spots, k=min(len(spots), random.randint(2, 5))), reverse=True):
            chars.insert(i + 1, random.choice(noises))
        return "".join(chars)

    def _unique_message(
        self, message: str, group_id: str, index: int = 1, group_name: str = ""
    ) -> str:
        """
        Spin {A|B|C} + noise + dòng FPV riêng mỗi nhóm.
        """
        base = message or ""
        # Spin trước
        base = self.spin_text(base)
        # Gỡ marker/dòng unique cũ
        base = re.sub(r"(?mi)\n*(?:\[FPV-[a-z0-9]{6}\]|FPV[a-z0-9]{6})\s*$", "", base)
        base = re.sub(r"(?m)\n*#[a-f0-9]{6}\s*$", "", base)
        base = re.sub(
            r"(?m)\n*[▪️•●◆▪]\s*\d{6}-\d+(?:/\d{4})?\s+FPV[a-z0-9]{6}\s*$",
            "",
            base,
            flags=re.I,
        )
        base = re.sub(r"(?mi)\n*sp-[a-z0-9]{5}\s*$", "", base).rstrip()

        # Đảo nhẹ thứ tự đoạn (nếu có ≥2 đoạn) để giảm trùng cấu trúc
        parts = [p for p in re.split(r"\n\s*\n", base) if p.strip()]
        if len(parts) >= 2 and index > 1:
            # Xoay vòng đoạn theo index
            rot = (index - 1) % len(parts)
            parts = parts[rot:] + parts[:rot]
            base = "\n\n".join(parts)

        base = self._inject_invisible_noise(base)

        code = uuid.uuid4().hex[:6]
        spin_id = uuid.uuid4().hex[:5]
        ts = time.strftime("%H%M%S")
        bullets = ["▪️", "•", "●", "◆", "▪"]
        bullet = bullets[(index - 1) % len(bullets)]
        tail_gid = str(group_id)[-4:]
        # Dòng unique hiển thị — dùng để xác minh + chống spam
        return (
            f"{base}\n\n"
            f"{bullet} {ts}-{index}/{tail_gid} FPV{code}\n"
            f"sp-{spin_id}"
        )

    def _get_selected_groups(self) -> list[dict]:
        return [g for var, g in self._group_vars if var.get()]

    def _tick_timer(self):
        if not self._posting or not self._post_start_ts:
            return
        elapsed = int(time.time() - self._post_start_ts)
        mm, ss = divmod(elapsed, 60)
        hh, mm = divmod(mm, 60)
        if hh:
            self._elapsed_var.set(f"⏱ Thời gian: {hh:02d}:{mm:02d}:{ss:02d}")
        else:
            self._elapsed_var.set(f"⏱ Thời gian: {mm:02d}:{ss:02d}")
        self._timer_job = self.after(1000, self._tick_timer)

    def _set_countdown(self, left: int, total: int):
        """Cập nhật ô đếm ngược delay giữa các nhóm."""
        if not hasattr(self, "_countdown_var"):
            return
        mm, ss = divmod(max(0, int(left)), 60)
        self._countdown_var.set(f"{mm:02d}:{ss:02d}")
        self._countdown_hint.set(f"Còn {left}s / delay {total}s → nhóm tiếp theo")
        self._status_line.set(f"⏱ Đếm ngược delay: {left}s rồi đăng nhóm tiếp…")
        try:
            if left <= 5:
                self._countdown_lbl.config(fg=COLOR_ERROR)
            elif left <= 15:
                self._countdown_lbl.config(fg=COLOR_PENDING)
            else:
                self._countdown_lbl.config(fg=COLOR_ACCENT2)
        except Exception:
            pass

    def _mark_posting_group(self, n, t, name, gid, marker, img_tag):
        if hasattr(self, "_countdown_var"):
            self._countdown_var.set("…")
            self._countdown_hint.set(f"Đang đăng nhóm {n}/{t}")
            try:
                self._countdown_lbl.config(fg=COLOR_ACCENT2)
            except Exception:
                pass
        self._live(
            f"[{n}/{t}] Đang xử lý: {name} [{gid}] (FPV{marker}, {img_tag})…",
            "info",
        )

    def _live(self, msg: str, tag: str = "info"):
        """Ghi log tức thì vào cả mini log và nhật ký."""
        self._mini_log.log(msg, tag)
        self._log(msg, tag)
        self._status_line.set(msg[:80])
        self.update_idletasks()

    def _start_posting(self):
        if lic:
            ok, msg, data = lic.verify(timeout=8.0)
            if not ok:
                self._license_ok = False
                messagebox.showerror(
                    "Token hết hạn / chưa kích hoạt",
                    msg or "Bạn cần mua token để sử dụng tiếp.",
                )
                self._show_license_dialog(
                    reason="expired" if (data or {}).get("code") == "expired" else "missing"
                )
                return
            self._license_ok = True
        elif not getattr(self, "_license_ok", False):
            messagebox.showwarning(
                "Chưa bản quyền",
                "Bạn cần mua token để sử dụng tiếp.",
            )
            self._show_license_dialog()
            return
        if not self.backend.logged_in:
            messagebox.showwarning("Chưa đăng nhập", "Vui lòng đăng nhập trước.")
            return

        message = self._msg_text.get("1.0", "end").strip()
        if not message:
            messagebox.showwarning("Thiếu nội dung", "Vui lòng nhập nội dung bài đăng.")
            return

        groups = self._get_selected_groups()
        if not groups:
            messagebox.showwarning("Chưa chọn nhóm", "Vui lòng chọn ít nhất một nhóm.")
            return

        images = [p for p in (getattr(self, "_image_paths", []) or []) if Path(p).is_file()]
        if not images:
            one = self._image_var.get().strip()
            if one and Path(one).is_file() and " ảnh:" not in one:
                images = [self._cache_image(one)]
                self._image_paths = images
        else:
            images = [self._cache_image(p) for p in images]
            self._image_paths = images
        self._sync_image_ui()

        delay = float(self._delay_var.get())
        if delay < 15:
            delay = 15.0
            self._delay_var.set(delay)

        self._persist_draft(copy_image=True)
        self.backend.reset_batch_state()

        self._posting = True
        self._stop_flag = False
        self._post_start_ts = time.time()
        self._post_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._ok_lbl.config(text="0")
        self._pending_lbl.config(text="0")
        self._err_lbl.config(text="0")
        self._skip_lbl.config(text=str(len(groups)))
        self._progress_var.set(0)
        self._progress_label.config(text=f"0 / {len(groups)}")
        self._mini_log.clear()
        self._elapsed_var.set("⏱ Thời gian: 00:00")
        self._countdown_var.set("—")
        self._countdown_hint.set("Đang chuẩn bị…")
        self._last_spin_idx = -1
        self._tick_timer()

        spin_mode = self._img_spin_mode.get() if hasattr(self, "_img_spin_mode") else "rotate"
        self._live(f"▶ Bắt đầu đăng vào {len(groups)} nhóm (delay {delay:.0f}s)", "bold")
        self._live("Mỗi nhóm: nạp lại cookies + fb_dtsg mới | xóa cache token cũ", "info")
        self._live("Spin {A|B|C} + FPV | nhóm 2+ ưu tiên mbasic", "info")
        if images:
            names = ", ".join(f"{i+1}.{Path(p).name}" for i, p in enumerate(images))
            self._live(
                f"Spin ảnh: {len(images)} tấm — "
                f"{'ngẫu nhiên' if spin_mode == 'random' else 'xoay vòng'}: {names}",
                "info",
            )
            if len(images) == 1:
                self._live(
                    "⚠ Chỉ 1 ảnh — mọi nhóm cùng tấm. Thêm ảnh (+Thêm) để spin chống spam.",
                    "warn",
                )
        self._live("✅ Đã đăng | ⏳ Chờ duyệt | ❌ Lỗi", "info")

        def _worker():
            ok_count = 0
            pending_count = 0
            err_count = 0
            for idx, g in enumerate(groups):
                if self._stop_flag:
                    self.after(0, lambda: self._live("⏹ Đã dừng bởi người dùng", "warn"))
                    break

                gid = str(g["id"])
                gname = g.get("name", gid)
                n = idx + 1
                t = len(groups)
                # Xóa token cache trước mỗi nhóm (tránh dtsg/doc_id cũ)
                self.backend._tokens_cache.clear()
                self.backend._tokens_cache_time = 0.0
                msg_for_group = self._unique_message(
                    message, gid, index=n, group_name=gname
                )
                marker = self.backend._extract_verify_marker(msg_for_group) or "?"
                image = self._pick_image_for_group(n)
                img_idx = getattr(self, "_last_spin_idx", -1) + 1
                img_total = len([p for p in self._image_paths if Path(p).is_file()]) or 0
                img_name = Path(image).name if image else "không ảnh"
                img_tag = (
                    f"ảnh {img_idx}/{img_total}: {img_name}"
                    if image and img_total
                    else "không ảnh"
                )

                def _prog(msg, _n=n, _t=t, _name=gname, _gid=gid):
                    self.after(
                        0,
                        lambda m=msg: self._live(
                            f"[{_n}/{_t}] {_name} [{_gid}] — {m}", "info"
                        ),
                    )

                self.after(
                    0,
                    lambda _n=n, _t=t, _name=gname, _gid=gid, _m=marker, _img=img_tag: (
                        self._mark_posting_group(_n, _t, _name, _gid, _m, _img)
                    ),
                )

                # Làm ấm session trên đúng trang nhóm trước khi đăng
                try:
                    self.backend._use_desktop_session()
                    self.backend.session.get(
                        f"https://www.facebook.com/groups/{gid}",
                        timeout=12,
                    )
                    time.sleep(1.5)
                except Exception:
                    pass

                try:
                    status, msg_result = self.backend.post_to_group(
                        gid, msg_for_group, image, progress_cb=_prog
                    )
                except Exception as exc:
                    status, msg_result = "failed", str(exc)

                if status == "published":
                    ok_count += 1
                elif status == "pending":
                    pending_count += 1
                else:
                    err_count += 1
                    status = "failed"

                remaining = t - n
                pct = (n / t) * 100
                check_url = f"https://www.facebook.com/groups/{gid}"

                self.after(
                    0,
                    lambda st=status, name=gname, gid_=gid, res=msg_result, url=check_url,
                           o=ok_count, pnd=pending_count, e=err_count, r=remaining,
                           p=pct, i=n, tt=t, im=img_tag: self._on_post_result(
                        st, name, gid_, res, url, o, pnd, e, r, p, i, tt, im
                    ),
                )

                if idx < len(groups) - 1 and not self._stop_flag:
                    wait_s = int(delay) + min(idx * 3, 30)
                    if status == "failed":
                        wait_s += 15
                    self.after(
                        0,
                        lambda w=wait_s: (
                            self._live(f"⏱ Chờ delay {w}s trước nhóm tiếp theo…", "info"),
                            self._set_countdown(w, w),
                        ),
                    )
                    for sec in range(wait_s):
                        if self._stop_flag:
                            break
                        left = wait_s - sec
                        self.after(0, lambda l=left, w=wait_s: self._set_countdown(l, w))
                        time.sleep(1)

            self.after(0, self._on_posting_done)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_post_result(self, status, name, gid, res, url, o, pnd, e, r, p, i, t, img_tag=""):
        self._ok_lbl.config(text=str(o))
        self._pending_lbl.config(text=str(pnd))
        self._err_lbl.config(text=str(e))
        self._skip_lbl.config(text=str(r))
        self._progress_var.set(p)
        self._progress_label.config(text=f"{i} / {t}")

        if status == "published":
            icon, tag, label = "✅", "ok", "ĐÃ ĐĂNG"
        elif status == "pending":
            icon, tag, label = "⏳", "pending", "CHỜ DUYỆT"
        else:
            icon, tag, label = "❌", "err", "LỖI"

        extra = f" | {img_tag}" if img_tag else ""
        self._live(f"[{i}/{t}] {icon} {label} — {name} [{gid}]{extra}", tag)
        self._live(f"    → {res}", tag)
        self._live(f"    🔗 {url}", "info")

    def _stop_posting(self):
        self._stop_flag = True
        self._stop_btn.config(state="disabled")
        self._live("⏹ Đang dừng sau bài hiện tại…", "warn")
        if hasattr(self, "_countdown_hint"):
            self._countdown_hint.set("Đang dừng…")

    def _on_posting_done(self):
        self._posting = False
        self._post_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        if hasattr(self, "_countdown_var"):
            self._countdown_var.set("00:00")
            self._countdown_hint.set("Đã xong")
            try:
                self._countdown_lbl.config(fg=COLOR_SUCCESS)
            except Exception:
                pass
        if self._timer_job:
            try:
                self.after_cancel(self._timer_job)
            except Exception:
                pass
            self._timer_job = None
        elapsed = ""
        if self._post_start_ts:
            sec = int(time.time() - self._post_start_ts)
            mm, ss = divmod(sec, 60)
            elapsed = f"\n⏱ Tổng thời gian: {mm:02d}:{ss:02d}"
            self._elapsed_var.set(f"⏱ Xong — {mm:02d}:{ss:02d}")
        ok = int(self._ok_lbl.cget("text"))
        pnd = int(self._pending_lbl.cget("text"))
        err = int(self._err_lbl.cget("text"))
        self._live(
            f"Hoàn thành! Đã đăng: {ok} | Chờ duyệt: {pnd} | Lỗi: {err}",
            "bold",
        )
        self._status_line.set("Đã xong")
        messagebox.showinfo(
            "Hoàn thành",
            f"Kết quả đăng bài:\n\n"
            f"✅ Đã đăng: {ok}\n"
            f"⏳ Chờ duyệt: {pnd}\n"
            f"❌ Lỗi: {err}{elapsed}",
        )

    # ── LOG TAB ───────────────────────────────────────────────────────────────

    def _build_log_tab(self):
        tab = self._tab_log
        top = tk.Frame(tab, bg=COLOR_BG)
        top.pack(fill="x", padx=16, pady=(12, 4))

        tk.Label(top, text="Nhật ký hoạt động", bg=COLOR_BG, fg=COLOR_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(side="left")

        HoverButton(
            top, text="🗑  Xóa log", command=lambda: self._full_log.clear(),
            bg=COLOR_CARD, fg=COLOR_TEXT, relief="flat", cursor="hand2",
            font=("Segoe UI", 10), padx=10, pady=4,
        ).pack(side="right")

        self._full_log = LogBox(tab, font=("Consolas", 9))
        self._full_log.pack(fill="both", expand=True, padx=16, pady=(0, 12))

    def _log(self, msg: str, tag: str = ""):
        self._full_log.log(msg, tag)

    # ── SETTINGS TAB ──────────────────────────────────────────────────────────

    def _build_settings_tab(self):
        tab = self._tab_settings

        outer = tk.Frame(tab, bg=COLOR_BG)
        outer.pack(expand=True, fill="both", padx=40, pady=20)

        # ── Bản quyền / Token ─────────────────────────────────────────────
        lic_card = tk.LabelFrame(
            outer, text="  Bản quyền (Token)  ",
            bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Segoe UI", 11, "bold"),
            bd=1, relief="groove", padx=16, pady=12,
        )
        lic_card.pack(fill="x", pady=(0, 16))

        self._license_status_var = tk.StringVar(
            value=(lic.status_summary() if lic else "Thiếu license_client")
        )
        tk.Label(
            lic_card, textvariable=self._license_status_var,
            bg=COLOR_PANEL, fg=COLOR_ACCENT2, font=("Segoe UI", 10, "bold"),
            wraplength=520, justify="left",
        ).pack(anchor="w")

        tk.Label(
            lic_card,
            text=(
                "Mỗi token = 1 máy. Server lưu IP khi kích hoạt / dùng.\n"
                "Hết hạn theo gói (ngày/tháng) — mua thêm token để gia hạn."
            ),
            bg=COLOR_PANEL, fg=COLOR_TEXT_DIM, font=("Segoe UI", 9),
            justify="left",
        ).pack(anchor="w", pady=(6, 8))

        row = tk.Frame(lic_card, bg=COLOR_PANEL)
        row.pack(fill="x")
        self._lic_token_var = tk.StringVar()
        SoftEntry(row, textvariable=self._lic_token_var, width=28).pack(
            side="left", padx=(0, 8)
        )
        HoverButton(
            row, text="Kích hoạt", command=self._activate_license_ui,
            bg=COLOR_BUTTON, fg="white", font=("Segoe UI", 10, "bold"),
            padx=12, pady=6,
        ).pack(side="left")
        HoverButton(
            row, text="Kiểm tra lại", command=self._recheck_license_ui,
            bg=COLOR_SURFACE, fg=COLOR_ACCENT2, hover_bg="#FFD7B5",
            font=("Segoe UI", 10, "bold"), padx=10, pady=6,
        ).pack(side="left", padx=6)

        srv_row = tk.Frame(lic_card, bg=COLOR_PANEL)
        srv_row.pack(fill="x", pady=(10, 0))
        tk.Label(
            srv_row, text="Server:", bg=COLOR_PANEL, fg=COLOR_TEXT_DIM,
            font=("Segoe UI", 9),
        ).pack(side="left")
        self._lic_server_var = tk.StringVar(
            value=(lic.get_server_url() if lic else DEFAULT_LICENSE_SERVER)
        )
        SoftEntry(srv_row, textvariable=self._lic_server_var, width=36).pack(
            side="left", padx=8
        )
        HoverButton(
            srv_row, text="Lưu URL", command=self._save_license_server_ui,
            bg=COLOR_SURFACE, fg=COLOR_ACCENT2, hover_bg="#FFD7B5",
            font=("Segoe UI", 9, "bold"), padx=10, pady=5,
        ).pack(side="left")

        # ── Kiểm tra kết nối ──────────────────────────────────────────────
        net_card = tk.LabelFrame(
            outer, text="  Kết nối mạng  ",
            bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Segoe UI", 11, "bold"),
            bd=1, relief="groove", padx=16, pady=12,
        )
        net_card.pack(fill="x", pady=(0, 16))

        tk.Label(
            net_card,
            text="Kiểm tra xem app có kết nối được tới Facebook không:",
            bg=COLOR_PANEL, fg=COLOR_TEXT_DIM, font=("Segoe UI", 10),
        ).pack(anchor="w")

        self._net_status_var = tk.StringVar(value="")
        tk.Label(net_card, textvariable=self._net_status_var,
                 bg=COLOR_PANEL, fg=COLOR_TEXT_DIM,
                 font=("Segoe UI", 10), wraplength=500).pack(anchor="w", pady=4)

        HoverButton(
            net_card, text="🔍  Kiểm tra kết nối", command=self._check_connection,
            bg=COLOR_CARD, fg=COLOR_TEXT, relief="flat", cursor="hand2",
            font=("Segoe UI", 10, "bold"), padx=14, pady=6,
        ).pack(anchor="w", pady=(4, 0))

        # ── Proxy / VPN ───────────────────────────────────────────────────
        proxy_card = tk.LabelFrame(
            outer, text="  Proxy / VPN  ",
            bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Segoe UI", 11, "bold"),
            bd=1, relief="groove", padx=16, pady=12,
        )
        proxy_card.pack(fill="x", pady=(0, 16))

        tk.Label(
            proxy_card,
            text=(
                "Nếu Facebook bị chặn ở mạng của bạn, hãy nhập địa chỉ proxy:\n"
                "Ví dụ:  http://127.0.0.1:8080   hoặc   socks5://127.0.0.1:1080"
            ),
            bg=COLOR_PANEL, fg=COLOR_TEXT_DIM, font=("Segoe UI", 10),
            justify="left",
        ).pack(anchor="w", pady=(0, 8))

        proxy_row = tk.Frame(proxy_card, bg=COLOR_PANEL)
        proxy_row.pack(fill="x")

        tk.Label(proxy_row, text="Proxy URL:", bg=COLOR_PANEL, fg=COLOR_TEXT_DIM,
                 font=("Segoe UI", 10)).pack(side="left")

        self._proxy_var = tk.StringVar()
        proxy_entry = tk.Entry(
            proxy_row, textvariable=self._proxy_var, width=40,
            bg=COLOR_INPUT_BG, fg=COLOR_INPUT_FG, insertbackground=COLOR_TEXT,
            relief="flat", font=("Segoe UI", 10),
        )
        proxy_entry.pack(side="left", padx=(8, 8), ipady=5)

        HoverButton(
            proxy_row, text="Áp dụng", command=self._apply_proxy,
            bg=COLOR_BUTTON, fg="white", relief="flat", cursor="hand2",
            font=("Segoe UI", 10, "bold"), padx=12, pady=5,
        ).pack(side="left")

        HoverButton(
            proxy_row, text="Xoá proxy", command=self._clear_proxy,
            bg=COLOR_CARD, fg=COLOR_TEXT, relief="flat", cursor="hand2",
            font=("Segoe UI", 10), padx=10, pady=5,
        ).pack(side="left", padx=(6, 0))

        # ── Dữ liệu đã lưu ────────────────────────────────────────────────
        data_card = tk.LabelFrame(
            outer, text="  Dữ liệu đã lưu (tự động)  ",
            bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Segoe UI", 11, "bold"),
            bd=1, relief="groove", padx=16, pady=12,
        )
        data_card.pack(fill="x", pady=(0, 16))
        tk.Label(
            data_card,
            text=(
                f"Thư mục: {DATA_DIR}\n"
                "• cookies.json — token/cookies đăng nhập\n"
                "• license.json — bản quyền đã kích hoạt\n"
                "• tokens.json — fb_dtsg gần nhất (mở nhanh hơn)\n"
                "• groups.json — nhóm đã quét\n"
                "• draft.json + images/ — nội dung bài & ảnh"
            ),
            bg=COLOR_PANEL, fg=COLOR_TEXT_DIM, font=("Segoe UI", 10),
            justify="left",
        ).pack(anchor="w")
        HoverButton(
            data_card, text="💾  Lưu ngay cookies + nhóm + bài nháp",
            command=self._save_all_now,
            bg=COLOR_BUTTON, fg="white", relief="flat", cursor="hand2",
            font=("Segoe UI", 10, "bold"), padx=12, pady=6,
        ).pack(anchor="w", pady=(10, 0))
        HoverButton(
            data_card, text="🧹  Xóa cache đăng bài (tokens.json / fb_dtsg cũ)",
            command=self._clear_posting_cache_ui,
            bg="#FEE2E2", fg=COLOR_ERROR, relief="flat", cursor="hand2",
            font=("Segoe UI", 10, "bold"), padx=12, pady=6,
        ).pack(anchor="w", pady=(8, 0))
        tk.Label(
            data_card,
            text="Nên xóa cache nếu nhóm 2+ toàn lỗi / GraphQL trả id giả.",
            bg=COLOR_PANEL, fg=COLOR_TEXT_DIM, font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(4, 0))

        self._proxy_status_var = tk.StringVar(value="")
        tk.Label(proxy_card, textvariable=self._proxy_status_var,
                 bg=COLOR_PANEL, fg=COLOR_TEXT_DIM,
                 font=("Segoe UI", 9)).pack(anchor="w", pady=(6, 0))

        # ── Hướng dẫn VPN miễn phí ───────────────────────────────────────
        hint_card = tk.LabelFrame(
            outer, text="  Nếu không có proxy — Dùng VPN miễn phí  ",
            bg=COLOR_PANEL, fg=COLOR_TEXT, font=("Segoe UI", 11, "bold"),
            bd=1, relief="groove", padx=16, pady=12,
        )
        hint_card.pack(fill="x")

        hints = [
            "1. Cài Psiphon (psiphon3.com) hoặc Lantern (getlantern.org) — miễn phí",
            "2. Bật VPN lên, rồi mở lại app này",
            "3. Hoặc dùng tab 'Nhập Cookies' — KHÔNG CẦN đăng nhập trong app",
            "",
            "👉 Cách dùng Cookies (đơn giản nhất, không cần VPN):",
            "   • Đăng nhập Facebook trên Chrome bình thường",
            "   • Cài extension 'Cookie-Editor' trên Chrome",
            "   • Mở extension → Export → Header String → Copy",
            "   • Quay lại tab Đăng nhập → tab Nhập Cookies → Dán → Xác nhận",
        ]
        for h in hints:
            color = COLOR_WARNING if h.startswith("👉") else (COLOR_SUCCESS if h.startswith("   •") else COLOR_TEXT_DIM)
            tk.Label(hint_card, text=h, bg=COLOR_PANEL, fg=color,
                     font=("Segoe UI", 9), anchor="w", justify="left").pack(anchor="w")

    def _save_license_server_ui(self):
        if not lic:
            return
        url = self._lic_server_var.get().strip()
        if not url:
            messagebox.showwarning("Thiếu URL", "Nhập địa chỉ server license.")
            return
        lic.set_server_url(url)
        messagebox.showinfo("Đã lưu", f"Server license:\n{url}")

    def _activate_license_ui(self):
        if not lic:
            messagebox.showerror("Lỗi", "Thiếu license_client.py")
            return
        tok = self._lic_token_var.get().strip()
        if not tok:
            messagebox.showwarning("Thiếu token", "Dán mã FBP-… vào ô.")
            return
        url = self._lic_server_var.get().strip()
        if url:
            lic.set_server_url(url)

        def _worker():
            ok, msg, data = lic.activate(tok)
            def _done():
                if ok:
                    self._license_ok = True
                    self._license_status_var.set(f"✅ {msg}")
                    days = data.get("expires_at", "")
                    messagebox.showinfo(
                        "Kích hoạt OK",
                        f"{msg}\nHết hạn: {days}\nMáy đã bị khoá với token này.",
                    )
                    if not getattr(self, "_bootstrapped_data", False):
                        self._bootstrap_saved_data()
                else:
                    messagebox.showerror("Kích hoạt thất bại", msg)
                    self._license_status_var.set(f"❌ {msg}")
            self.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    def _recheck_license_ui(self):
        if not lic:
            return
        url = self._lic_server_var.get().strip()
        if url:
            lic.set_server_url(url)

        def _worker():
            ok, msg, data = lic.verify()
            def _done():
                self._license_ok = ok
                self._license_status_var.set(("✅ " if ok else "❌ ") + msg)
                if ok:
                    messagebox.showinfo("License", msg)
                    self._schedule_license_watch()
                else:
                    messagebox.showerror(
                        "License",
                        msg or "Bạn cần mua token để sử dụng tiếp.",
                    )
                    self._show_license_dialog(
                        reason="expired" if (data or {}).get("code") == "expired" else "missing"
                    )
            self.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    def _save_all_now(self):
        self._bootstrapped_data = True
        try:
            _ensure_data_dir()
            if self.backend.logged_in:
                self.backend.save_cookies()
                self.backend.save_tokens()
            self._persist_groups()
            self._persist_draft(copy_image=True)
            messagebox.showinfo(
                "Đã lưu",
                f"Đã lưu vào:\n{DATA_DIR}\n\n"
                f"Cookies, token, {len(self.groups)} nhóm, bài nháp & ảnh.",
            )
        except Exception as exc:
            messagebox.showerror("Lỗi lưu", str(exc))

    def _clear_posting_cache_ui(self):
        try:
            self.backend.clear_posting_cache()
            messagebox.showinfo(
                "Đã xóa cache",
                "Đã xóa tokens.json và cache fb_dtsg trong RAM.\n"
                "Cookies đăng nhập vẫn giữ.\n\n"
                "Hãy chạy đăng bài lại.",
            )
            self._log("Đã xóa cache đăng bài (tokens/fb_dtsg)", "warn")
        except Exception as exc:
            messagebox.showerror("Lỗi", str(exc))

    def _check_connection(self):
        self._net_status_var.set("🔄 Đang kiểm tra…")
        self.update_idletasks()

        def _worker():
            ok, detail = self.backend.test_connection()
            def _done():
                if ok:
                    self._net_status_var.set(f"✅ Kết nối OK → {detail}")
                    self._net_status_var._label_fg = COLOR_SUCCESS
                else:
                    msgs = {
                        "proxy_error": "❌ Lỗi proxy — kiểm tra địa chỉ proxy",
                        "ssl_error": "❌ Lỗi SSL/HTTPS",
                        "unreachable": "❌ Không kết nối được tới Facebook\n→ Thử bật VPN hoặc dùng proxy",
                    }
                    self._net_status_var.set(msgs.get(detail, f"❌ {detail}"))
            self.after(0, _done)

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_proxy(self):
        proxy = self._proxy_var.get().strip()
        if not proxy:
            messagebox.showwarning("Thiếu proxy", "Vui lòng nhập địa chỉ proxy.")
            return
        self.backend.set_proxy(proxy)
        self._proxy_status_var.set(f"✅ Đang dùng proxy: {proxy}")
        self._log(f"Đã đặt proxy: {proxy}", "warn")

    def _clear_proxy(self):
        self.backend.set_proxy("")
        self._proxy_var.set("")
        self._proxy_status_var.set("Đã xoá proxy — dùng kết nối trực tiếp")
        self._log("Đã xoá proxy", "info")

    # ──────────────────────────────────────────────────────────────────────────


def main():
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
