"""
Facebook Group Poster — Ứng dụng GUI Desktop
Đăng bài quảng cáo lên nhiều nhóm Facebook tự động.
"""

import json
import os
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

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

APP_TITLE = "Facebook Group Poster"
APP_VERSION = "1.4.0"
MOBILE_URL = "https://mbasic.facebook.com"

# Thư mục dữ liệu cục bộ — mở lại tool giữ cookies / nhóm / bài nháp
DATA_DIR = Path.home() / ".fb_poster"
COOKIES_FILE = DATA_DIR / "cookies.json"
LEGACY_COOKIES_FILE = Path.home() / ".fb_poster_cookies.json"
GROUPS_FILE = DATA_DIR / "groups.json"
DRAFT_FILE = DATA_DIR / "draft.json"
IMAGES_DIR = DATA_DIR / "images"
TOKENS_FILE = DATA_DIR / "tokens.json"


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
        """Gọi trước mỗi lần đăng hàng loạt."""
        self._used_post_ids.clear()
        self._tokens_cache.clear()
        self._tokens_cache_time = 0.0

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
            error_patterns = [
                r'id="error_box"[^>]*>([^<]+)',
                r'class="[^"]*error[^"]*"[^>]*>\s*<[^>]+>\s*([^<]{5,100})',
                r'The password[^<]+',
                r'Mật khẩu[^<]+không đúng[^<]*',
            ]
            for pat in error_patterns:
                m = re.search(pat, login_resp.text, re.I)
                if m:
                    return False, f"Lỗi: {m.group(0)[:120]}"

            return False, (
                "Đăng nhập thất bại.\n"
                "Facebook có thể đang chặn đăng nhập tự động.\n"
                "Vui lòng dùng tab 'Nhập Cookies' thay thế."
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

        # Token mới mỗi nhóm — tránh tái dùng session sau bài đầu
        self._tokens_cache.clear()
        self._tokens_cache_time = 0.0

        methods = [
            ("GraphQL", self._post_via_graphql),
            ("Ajax", self._post_via_ajax_feed),
            ("composer", self._post_via_composer_direct),
            ("mbasic", self._post_via_mobile),
            ("m.facebook", self._post_via_m_composer),
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

            # Bắt buộc xác minh lại trên nhóm — tránh báo thành công giả
            _prog(f"{name} báo {status} → đang kiểm tra trên nhóm…")
            post_id = None
            m = re.search(
                r"(?:post[:\s]*|Đăng[^(]*\()([0-9]{8,}|Uzpf[A-Za-z0-9_-]{8,})",
                msg,
            )
            if not m:
                m = re.search(r"\(([0-9]{8,}|Uzpf[A-Za-z0-9_-]{8,})\)", msg)
            if m:
                post_id = m.group(1)
            # post_id trùng group_id hoặc đã dùng cho nhóm khác → giả
            if post_id and (
                str(post_id) == str(group_id) or str(post_id) in self._used_post_ids
            ):
                _prog(f"{name}: post_id trùng/đã dùng ({str(post_id)[:20]}) → bỏ qua")
                last_err = f"{name} trả post_id cũ — có thể FB chặn spam hoặc echo bài trước"
                continue

            verified = None
            try:
                verified = self._verify_post_status(
                    group_id, message, post_id=post_id, claimed=status
                )
            except Exception as exc:
                _prog(f"Xác minh lỗi: {exc}")
                verified = None

            if verified in ("published", "pending"):
                if post_id:
                    self._used_post_ids.add(str(post_id))
                label = "Đã đăng lên nhóm" if verified == "published" else "Đang chờ admin duyệt"
                extra = " (đã xác minh)"
                if post_id:
                    extra = f" (post: {post_id[:28]}, đã xác minh)"
                _prog(f"{name}: {label}{extra}")
                try:
                    self.save_tokens()
                except Exception:
                    pass
                return verified, f"{label}{extra}"

            # Báo success nhưng không thấy bài → coi là thất bại, thử cách khác
            last_err = (
                f"{name} báo OK nhưng không thấy bài trên nhóm/hàng chờ"
                + (f" — {msg}" if msg else "")
            )
            _prog(f"⚠ {last_err}")

        return "failed", last_err

    def _message_snippets(self, message: str) -> list[str]:
        """Đoạn text dùng để khớp bài trên feed/pending."""
        raw = message or ""
        snippet = re.sub(r"\s+", " ", raw.strip())
        checks: list[str] = []
        # Ưu tiên đuôi bài (chứa dấu ẩn unique từng nhóm)
        if len(raw) >= 24:
            checks.append(raw[-96:].lower())
        if len(snippet) >= 10:
            checks.append(snippet[:48].lower())
        for line in raw.split("\n"):
            line = re.sub(r"\s+", " ", line).strip()
            if len(line) >= 10 and re.search(r"[a-zA-ZÀ-ỹ0-9]", line):
                checks.append(line[:40].lower())
                break
        return list(dict.fromkeys(c for c in checks if c))

    def _verify_post_status(
        self,
        group_id: str,
        message: str,
        post_id: str | None = None,
        claimed: str | None = None,
    ) -> str | None:
        """
        Xác minh bài đã lên feed hoặc hàng chờ.
        Returns: published | pending | None
        """
        checks = self._message_snippets(message)
        self._use_desktop_session()

        # Thử vài lần — FB đôi khi chậm index
        for attempt in range(3):
            if attempt:
                time.sleep(1.8)
            else:
                time.sleep(1.0)

            found = self._verify_once(group_id, checks, post_id=post_id, claimed=claimed)
            if found:
                return found
        return None

    def _verify_once(
        self,
        group_id: str,
        checks: list[str],
        post_id: str | None = None,
        claimed: str | None = None,
    ) -> str | None:
        urls: list[tuple[str, str]] = []
        if post_id:
            pid = str(post_id)
            if pid.isdigit():
                urls.extend([
                    ("by_id", f"https://www.facebook.com/groups/{group_id}/posts/{pid}"),
                    ("by_id", f"https://www.facebook.com/groups/{group_id}/permalink/{pid}/"),
                    ("by_id", f"https://mbasic.facebook.com/story.php?story_fbid={pid}&id={group_id}"),
                    ("by_id", f"https://m.facebook.com/story.php?story_fbid={pid}&id={group_id}"),
                ])
            else:
                urls.append(("by_id", f"https://www.facebook.com/{pid}"))

        urls.extend([
            ("pending", f"https://mbasic.facebook.com/groups/{group_id}/pending"),
            ("pending", f"https://m.facebook.com/groups/{group_id}/pending"),
            ("pending", f"https://www.facebook.com/groups/{group_id}/pending_posts"),
            ("pending", f"https://www.facebook.com/groups/{group_id}/pending"),
            ("feed", f"https://mbasic.facebook.com/groups/{group_id}"),
            ("feed", f"https://m.facebook.com/groups/{group_id}"),
            ("feed", f"https://www.facebook.com/groups/{group_id}"),
        ])

        for kind, url in urls:
            try:
                resp = self.session.get(url, timeout=12, allow_redirects=True)
                if resp.status_code >= 400:
                    continue
                html = resp.text
                low = html.lower()
                final = resp.url.lower()
                gid = str(group_id)

                if "login" in final or "/login" in final:
                    continue
                if any(x in low[:2500] for x in (
                    "content isn't available", "nội dung không",
                    "this content isn't available", "không khả dụng",
                )):
                    continue

                # Bắt buộc vẫn thuộc đúng nhóm (tránh redirect sang bài nhóm trước)
                on_this_group = (
                    f"/groups/{gid}" in final
                    or f"id={gid}" in final
                    or f"&id={gid}" in final
                    or f"group_id={gid}" in final
                )
                if kind in ("by_id", "pending", "feed") and not on_this_group:
                    # URL tuyệt đối /Uzpf... đôi khi không có group trong path —
                    # chỉ chấp nhận nếu HTML chứa groups/{gid}
                    if f"/groups/{gid}" not in low and f"groups\\/{gid}" not in low:
                        continue

                has_pid = bool(post_id and str(post_id) in html)
                matched = any(c in low for c in checks) if checks else False

                if kind == "by_id":
                    # Phải khớp nội dung HOẶC (pid + đúng nhóm) — không tin redirect mù
                    if not on_this_group and f"/groups/{gid}" not in low:
                        continue
                    if has_pid and matched:
                        if "pending" in final or "pending" in low[:3000] or claimed == "pending":
                            return "pending"
                        return "published"
                    if has_pid and on_this_group:
                        # Có post_id trên URL nhóm này; ưu tiên pending nếu claim
                        if claimed == "pending" or "pending" in final or "pending" in low[:3000]:
                            return "pending"
                        return "published"
                    if matched and on_this_group:
                        if claimed == "pending" or "pending" in low[:3000]:
                            return "pending"
                        return "published"
                    continue

                # feed / pending: bắt buộc khớp nội dung bài (không chỉ banner chờ duyệt)
                if not matched:
                    continue

                if kind == "pending":
                    return "pending"

                if "pending" in final:
                    return "pending"
                return "published"
            except Exception:
                continue
        return None

    def _upload_photo(self, image_path: str, tokens: dict) -> str | None:
        """Upload ảnh, trả về photo_id nếu thành công."""
        path = Path(image_path)
        if not path.is_file():
            return None
        uid = tokens.get("__user") or self._get_user_id()
        fb_dtsg = tokens.get("fb_dtsg")
        if not uid or not fb_dtsg:
            return None

        self._use_desktop_session()
        upload_urls = [
            f"https://upload.facebook.com/ajax/react_composer/attachments/photo/upload?__a=1&fb_dtsg={fb_dtsg}",
            "https://www.facebook.com/ajax/react_composer/attachments/photo/upload",
            "https://upload.facebook.com/ajax/react_composer/attachments/photo/upload",
        ]
        data = {
            "fb_dtsg": fb_dtsg,
            "__user": uid,
            "__a": "1",
            "source": "8",
            "profile_id": uid,
            "target_id": uid,
            "waterfallxapp": "comet",
            "upload_id": "jsc_c_a0",
        }
        mime = "image/jpeg"
        if path.suffix.lower() == ".png":
            mime = "image/png"
        elif path.suffix.lower() == ".gif":
            mime = "image/gif"

        for url in upload_urls:
            try:
                with open(path, "rb") as fh:
                    resp = self.session.post(
                        url,
                        data=data,
                        files={"farr": (path.name, fh, mime)},
                        headers={
                            **self.DESKTOP_HEADERS,
                            "Origin": "https://www.facebook.com",
                            "Referer": "https://www.facebook.com/",
                        },
                        timeout=30,
                    )
                text = resp.text
                if text.startswith("for (;;);"):
                    text = text[9:]
                # P.A.I.F style
                locale = text.find('"photoID":"')
                if locale >= 0:
                    photo_id = text[locale + 11: locale + 27].split('"')[0]
                    if photo_id.isdigit():
                        return photo_id
                m = re.search(
                    r'"photoID"\s*:\s*"(\d+)"|"photo_id"\s*:\s*"(\d+)"',
                    text,
                )
                if m:
                    return m.group(1) or m.group(2)
                # Thử parse JSON
                try:
                    j = json.loads(text)
                    found, _ = self._walk_json_for_post(j)
                    # walk tìm id - có thể lấy nhầm; tìm photoID riêng
                    def find_photo(obj, depth=0):
                        if depth > 10:
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
                    pid = find_photo(j)
                    if pid:
                        return pid
                except Exception:
                    pass
            except Exception:
                continue
        return None

    def _build_gql_variables(
        self, group_id: str, message: str, uid: str, photo_id: str | None = None
    ) -> dict:
        """Payload GraphQL theo format đã chạy được trên nhiều tool cookies."""
        sid = str(uuid.uuid4())
        attachments = []
        if photo_id:
            attachments = [{"photo": {"id": str(photo_id)}}]
        return {
            "input": {
                "composer_entry_point": "inline_composer",
                "composer_source_surface": "group",
                "composer_type": "group",
                "idempotence_token": f"{uuid.uuid4()}_FEED",
                "source": "WWW",
                "attachments": attachments,
                "message": {"ranges": [], "text": message},
                "inline_activities": [],
                "explicit_place_id": "0",
                "text_format_preset_id": "0",
                "tracking": [None],
                "audience": {"to_id": str(group_id)},
                "actor_id": str(uid),
                "client_mutation_id": str(uuid.uuid4()),
                "logging": {"composer_session_id": sid},
            },
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
            # Chỉ nhận id từ story_create — tránh echo bài cũ trên feed
            found, status = self._walk_json_for_post(data, create_only=True)
            if found:
                if found in self._used_post_ids or (gid and found == gid):
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
        """Lấy doc_id composer từ HTML + danh sách ID đã biết."""
        ids: list[str] = []
        patterns = [
            r'ComposerStoryCreateMutation[^}]{0,400}"doc_id"\s*:\s*"(\d+)"',
            r'"doc_id"\s*:\s*"(\d+)"[^}]{0,400}ComposerStoryCreateMutation',
            r'CometComposerCreateMutation[^}]{0,400}"doc_id"\s*:\s*"(\d+)"',
            r'GroupComposer[^}]{0,400}"doc_id"\s*:\s*"(\d+)"',
            r'useCometComposerCreateMutation[^}]*"doc_id"\s*:\s*"(\d+)"',
            r'"name":"ComposerStoryCreateMutation"[^,]*,"id":"(\d+)"',
            r'"id":"(\d+)","name":"ComposerStoryCreateMutation"',
        ]
        for pat in patterns:
            for m in re.finditer(pat, html):
                if m.group(1) not in ids:
                    ids.append(m.group(1))
        # Doc IDs từng chạy được (có thể hết hạn — vẫn thử)
        known = [
            "26937332182536553",
            "4669579913112843",
            "5634383916606190",
            "4229729377134595",
            "238010847699429",
            "7828976785402038",
            "23618316235273932",
        ]
        for fid in known:
            if fid not in ids:
                ids.append(fid)
        return ids

    def _post_via_graphql(
        self, group_id: str, message: str, image_path: str = None
    ) -> tuple[str, str]:
        """Đăng bài qua GraphQL — format payload giống tool cookies thực tế."""
        # Luôn refresh token từ trang nhóm
        self._use_desktop_session()
        group_url = f"https://www.facebook.com/groups/{group_id}"
        try:
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
        if image_path and Path(image_path).is_file():
            # Gắn token mới vào upload
            up_tokens = {"__user": uid, "fb_dtsg": fb_dtsg, **tokens}
            photo_id = self._upload_photo(image_path, up_tokens)

        doc_ids = self._extract_composer_doc_ids(html)
        last_hint = ""

        for doc_id in doc_ids[:8]:
            # Variables mới mỗi lần thử — tránh FB echo mutation cũ
            variables = self._build_gql_variables(group_id, message, uid, photo_id)
            payload: dict = {
                "av": uid,
                "__user": uid,
                "__a": "1",
                "__req": "1",
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
                    timeout=20,
                )
                status, msg = self._analyze_post_response(gql_resp.text, group_id=group_id)
                if status in ("published", "pending"):
                    if photo_id:
                        msg = f"{msg} (+ảnh)"
                    try:
                        self._tokens_cache = {**tokens, "__user": uid, "fb_dtsg": fb_dtsg}
                        self._tokens_cache_time = time.time()
                        self.save_tokens()
                    except Exception:
                        pass
                    return status, msg
                if status == "failed":
                    if any(k in msg.lower() for k in ("permission", "quyền", "not allowed", "admin", "chỉ cho")):
                        return "failed", msg
                    last_hint = msg
                elif status == "unknown" and msg:
                    last_hint = msg[:100]
            except Exception as exc:
                last_hint = str(exc)
                continue

        # Text-only retry nếu upload ảnh fail
        if photo_id:
            for doc_id in doc_ids[:4]:
                variables = self._build_gql_variables(group_id, message, uid, None)
                payload = {
                    "av": uid, "__user": uid, "__a": "1", "__comet_req": "15",
                    "fb_dtsg": fb_dtsg,
                    "fb_api_caller_class": "RelayModern",
                    "fb_api_req_friendly_name": "ComposerStoryCreateMutation",
                    "variables": json.dumps(variables, ensure_ascii=False),
                    "doc_id": doc_id,
                }
                if tokens.get("lsd"):
                    payload["lsd"] = tokens["lsd"]
                try:
                    gql_resp = self.session.post(
                        "https://www.facebook.com/api/graphql/",
                        data=payload,
                        headers={
                            **self.DESKTOP_HEADERS,
                            "Content-Type": "application/x-www-form-urlencoded",
                            "X-FB-Friendly-Name": "ComposerStoryCreateMutation",
                            "Origin": "https://www.facebook.com",
                            "Referer": group_url + "/",
                        },
                        timeout=20,
                    )
                    status, msg = self._analyze_post_response(gql_resp.text, group_id=group_id)
                    if status in ("published", "pending"):
                        return status, f"{msg} (chỉ text)"
                except Exception:
                    continue

        hint = f" — {last_hint}" if last_hint else ""
        return "failed", f"GraphQL không nhận post ID{hint}"

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
                        with open(image_path, "rb") as fh:
                            resp = self.session.post(
                                url, data=data,
                                files={"file": (Path(image_path).name, fh, "image/jpeg")},
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
                        with open(image_path, "rb") as fh:
                            resp = self.session.post(
                                post_url, data=data,
                                files={"file1": (Path(image_path).name, fh, "image/jpeg")},
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
                with open(image_path, "rb") as fh:
                    post_resp = self.session.post(
                        post_url, data=fields,
                        files={"file": (Path(image_path).name, fh, "image/jpeg")},
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
        """Đăng qua mbasic — tìm form compose linh hoạt hơn."""
        tokens = self._get_tokens()
        fb_dtsg = tokens.get("fb_dtsg", "")
        uid = tokens.get("__user") or self._get_user_id()

        saved_headers = dict(self.session.headers)
        self._use_mobile_session()

        try:
            urls_to_try = [
                f"{MOBILE_URL}/groups/{group_id}?view=permalink",
                f"{MOBILE_URL}/groups/{group_id}/",
                f"{MOBILE_URL}/composer/?c_src=group&target={group_id}",
                f"https://m.facebook.com/groups/{group_id}/",
            ]

            html = ""
            for url in urls_to_try:
                try:
                    resp = self.session.get(url, timeout=12, allow_redirects=True)
                    if resp.status_code != 200:
                        continue
                    html = resp.text
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

            ta_m = re.search(r'<textarea[^>]+name=["\']([^"\']+)["\']', html, re.I)
            msg_key = ta_m.group(1) if ta_m else "xc_message"

            action = self._find_form_action(html, group_id)
            if not action:
                action = f"/composer/mbasic/?c_src=group&target={group_id}&av={uid}"

            fields[msg_key] = message
            fields["xc_message"] = message
            fields["target"] = str(group_id)
            fields["c_src"] = "group"
            if fb_dtsg:
                fields["fb_dtsg"] = fb_dtsg
            if uid:
                fields["__user"] = uid
            fields.setdefault("view_post", "Đăng")

            post_url = action if action.startswith("http") else f"{MOBILE_URL}{action}"

            if image_path and Path(image_path).is_file():
                with open(image_path, "rb") as fh:
                    post_resp = self.session.post(
                        post_url, data=fields,
                        files={"file1": (Path(image_path).name, fh, "image/jpeg")},
                        allow_redirects=True, timeout=25,
                    )
            else:
                post_resp = self.session.post(
                    post_url, data=fields, allow_redirects=True, timeout=15,
                )

            status, msg = self._analyze_post_response(post_resp.text, group_id=group_id)
            if status in ("published", "pending"):
                return status, msg
            pid_m = re.search(
                r"(?:story_fbid|posts/|permalink\.php\?story_fbid=)[=/]?(\d{8,})",
                post_resp.url,
            )
            if pid_m:
                if "pending" in post_resp.url.lower():
                    return "pending", f"Đang chờ admin duyệt ({pid_m.group(1)})"
                return "published", f"Đã đăng lên nhóm ({pid_m.group(1)})"
            if "login" in post_resp.url.lower():
                return "failed", "Cookies hết hạn — lấy lại cookies"
            return "failed", "mbasic: không xác nhận được bài đăng (không có post ID)"
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


class SoftEntry(tk.Frame):
    """Ô nhập bo góc giả lập bằng viền cam nhạt."""

    def __init__(self, master, textvariable=None, width=30, show=None, **kw):
        super().__init__(
            master, bg=COLOR_BORDER, padx=1, pady=1,
            highlightthickness=0,
        )
        self.entry = tk.Entry(
            self, textvariable=textvariable, width=width, show=show or "",
            bg=COLOR_INPUT_BG, fg=COLOR_INPUT_FG, insertbackground=COLOR_TEXT,
            relief="flat", font=("Segoe UI", 11), bd=0,
        )
        self.entry.pack(fill="both", expand=True, padx=8, pady=6)


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
        self.title(f"{APP_TITLE} v{APP_VERSION}")
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

        # UI trước — mở nhanh; cookies/nhóm/nháp load nền
        self._build_ui()
        self.after(50, self._bootstrap_saved_data)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _bootstrap_saved_data(self):
        """Load cookies / nhóm / nháp sau khi UI đã hiện."""
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
        img = draft.get("image") or ""
        if img and Path(img).is_file() and hasattr(self, "_image_var"):
            self._image_var.set(img)
        delay = draft.get("delay")
        if delay is not None and hasattr(self, "_delay_var"):
            try:
                self._delay_var.set(float(delay))
            except Exception:
                pass

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
            image = ""
            if hasattr(self, "_image_var"):
                image = self._image_var.get().strip()
            if copy_image and image and Path(image).is_file():
                image = self._cache_image(image)
                self._image_var.set(image)
            delay = 20.0
            if hasattr(self, "_delay_var"):
                try:
                    delay = float(self._delay_var.get())
                except Exception:
                    pass
            _write_json(DRAFT_FILE, {
                "message": message,
                "image": image,
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
        # Giữ nếu đã nằm trong thư mục cache
        try:
            if src.resolve().parent == IMAGES_DIR.resolve():
                return str(src)
        except Exception:
            pass
        dest = IMAGES_DIR / f"draft_{int(time.time())}_{src.name}"
        try:
            shutil.copy2(src, dest)
            return str(dest)
        except Exception:
            return image_path

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

        status_frame = tk.Frame(header, bg="#EA580C", padx=14, pady=6)
        status_frame.pack(side="right", padx=20, pady=12)
        self._status_var = tk.StringVar(value="○ Chưa đăng nhập")
        tk.Label(status_frame, textvariable=self._status_var, bg="#EA580C",
                 fg=COLOR_HEADER_TEXT, font=("Segoe UI", 10)).pack()

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
        content.pack(fill="both", expand=True, padx=12, pady=(8, 12))

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
        email_entry = tk.Entry(pane_pw, textvariable=self._email_var, width=36,
                               bg=COLOR_INPUT_BG, fg=COLOR_INPUT_FG, insertbackground=COLOR_TEXT,
                               relief="flat", font=("Segoe UI", 11))
        email_entry.grid(row=0, column=1, padx=(8, 0), pady=4, ipady=6)

        lbl(pane_pw, "Mật khẩu:", 1)
        pass_entry = tk.Entry(pane_pw, textvariable=self._pass_var, show="●", width=36,
                              bg=COLOR_INPUT_BG, fg=COLOR_INPUT_FG, insertbackground=COLOR_TEXT,
                              relief="flat", font=("Segoe UI", 11))
        pass_entry.grid(row=1, column=1, padx=(8, 0), pady=4, ipady=6)

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
            # Nếu lỗi liên quan tới form/block, gợi ý dùng cookies
            if "checkpoint" in msg or "chặn" in msg or "thất bại" in msg or "form" in msg:
                messagebox.showinfo(
                    "Gợi ý: Dùng Cookies",
                    "Đăng nhập bằng email/mật khẩu thất bại.\n\n"
                    "👉 Hãy dùng tab 'Nhập Cookies':\n\n"
                    "1. Mở Chrome, đăng nhập Facebook bình thường\n"
                    "2. Cài extension 'Cookie-Editor' (miễn phí)\n"
                    "   https://chromewebstore.google.com/detail/cookie-editor/hlkenndednhfkekhgcdicdfddnkalmdm\n"
                    "3. Mở extension → Export → Header String → Copy\n"
                    "4. Quay lại tab 'Nhập Cookies' → Dán vào ô → Xác nhận",
                )

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
            left_wrap, bg=COLOR_PANEL, highlightbackground=COLOR_BORDER,
            highlightthickness=1, padx=18, pady=16,
        )
        left_card.pack(fill="both", expand=True)
        left = left_card

        tk.Label(left, text="Soạn bài đăng", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Segoe UI", 16, "bold")).pack(anchor="w")
        tk.Label(
            left,
            text="✅ Đã đăng   ⏳ Chờ duyệt   ❌ Lỗi  —  chỉ báo OK khi có post ID",
            bg=COLOR_PANEL, fg=COLOR_ACCENT2, font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(4, 12))

        tk.Label(left, text="Nội dung", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Segoe UI", 11, "bold")).pack(anchor="w")

        msg_frame = tk.Frame(left, bg=COLOR_BORDER, padx=1, pady=1)
        msg_frame.pack(fill="both", expand=True, pady=(6, 12))
        self._msg_text = scrolledtext.ScrolledText(
            msg_frame, height=11, bg="#FFFFFF", fg=COLOR_INPUT_FG,
            insertbackground=COLOR_TEXT, relief="flat",
            font=("Segoe UI", 12), wrap=tk.WORD, padx=10, pady=8,
        )
        self._msg_text.pack(fill="both", expand=True)
        self._msg_text.bind("<KeyRelease>", self._schedule_draft_save)

        # Image
        img_row = tk.Frame(left, bg=COLOR_PANEL)
        img_row.pack(fill="x", pady=4)
        tk.Label(img_row, text="Ảnh đính kèm", bg=COLOR_PANEL,
                 fg=COLOR_TEXT, font=("Segoe UI", 10, "bold")).pack(side="left")

        self._image_var = tk.StringVar()
        img_box = SoftEntry(img_row, textvariable=self._image_var, width=34)
        img_box.pack(side="left", padx=(10, 6))

        HoverButton(
            img_row, text="  Chọn ảnh  ", command=self._browse_image,
            bg=COLOR_SURFACE, fg=COLOR_ACCENT2, hover_bg="#FFD7B5",
            font=("Segoe UI", 10, "bold"), padx=10, pady=6,
        ).pack(side="left")
        HoverButton(
            img_row, text=" Xóa ", command=lambda: self._image_var.set(""),
            bg="#FEE2E2", fg=COLOR_ERROR, hover_bg="#FECACA",
            font=("Segoe UI", 10, "bold"), padx=8, pady=6,
        ).pack(side="left", padx=4)

        # Delay + timer row
        delay_row = tk.Frame(left, bg=COLOR_PANEL)
        delay_row.pack(fill="x", pady=(12, 4))
        tk.Label(delay_row, text="Delay (giây)", bg=COLOR_PANEL,
                 fg=COLOR_TEXT, font=("Segoe UI", 10, "bold")).pack(side="left")
        self._delay_var = tk.DoubleVar(value=25)
        delay_spin = tk.Spinbox(
            delay_row, from_=8, to=300, textvariable=self._delay_var,
            width=5, bg="#FFFFFF", fg=COLOR_INPUT_FG, relief="solid",
            font=("Segoe UI", 12), buttonbackground=COLOR_SURFACE,
            insertbackground=COLOR_TEXT, highlightthickness=1,
            highlightbackground=COLOR_BORDER,
            command=self._schedule_draft_save,
        )
        delay_spin.pack(side="left", padx=(10, 4), ipady=4)
        tk.Label(
            delay_row, text="(≥25s tránh FB chặn spam)",
            bg=COLOR_PANEL, fg=COLOR_TEXT_DIM, font=("Segoe UI", 9),
        ).pack(side="left", padx=(4, 0))

        self._elapsed_var = tk.StringVar(value="⏱ Thời gian: 00:00")
        tk.Label(
            delay_row, textvariable=self._elapsed_var,
            bg=COLOR_PANEL, fg=COLOR_ACCENT2, font=("Segoe UI", 12, "bold"),
        ).pack(side="right")

        # Buttons
        btn_row = tk.Frame(left, bg=COLOR_PANEL)
        btn_row.pack(fill="x", pady=(14, 4))

        self._post_btn = HoverButton(
            btn_row, text="  🚀  Bắt đầu đăng bài  ", command=self._start_posting,
            bg=COLOR_BUTTON, fg="white", font=("Segoe UI", 13, "bold"),
            padx=28, pady=12,
        )
        self._post_btn.pack(side="left", padx=(0, 10))

        self._stop_btn = HoverButton(
            btn_row, text="  ⏹  Dừng  ", command=self._stop_posting,
            bg="#FFFFFF", fg=COLOR_ERROR, hover_bg="#FEE2E2",
            font=("Segoe UI", 12, "bold"), padx=18, pady=12, state="disabled",
        )
        self._stop_btn.pack(side="left")

        # Right progress panel
        right = tk.Frame(
            tab, bg=COLOR_PANEL, width=300,
            highlightbackground=COLOR_BORDER, highlightthickness=1,
        )
        right.pack(side="right", fill="y", padx=(0, 14), pady=12)
        right.pack_propagate(False)

        tk.Label(right, text="Tiến trình", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Segoe UI", 14, "bold")).pack(pady=(14, 4), padx=14, anchor="w")

        self._status_line = tk.StringVar(value="Chưa chạy")
        tk.Label(
            right, textvariable=self._status_line, bg=COLOR_PANEL,
            fg=COLOR_TEXT_DIM, font=("Segoe UI", 10), wraplength=260, justify="left",
        ).pack(padx=14, anchor="w")

        style = ttk.Style()
        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor="#FFEDD5", background=COLOR_ACCENT,
            borderwidth=0, lightcolor=COLOR_ACCENT, darkcolor=COLOR_ACCENT,
            thickness=14,
        )
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            right, variable=self._progress_var,
            style="Accent.Horizontal.TProgressbar",
            maximum=100, length=260,
        )
        self._progress_bar.pack(padx=14, pady=(10, 6))

        self._progress_label = tk.Label(
            right, text="0 / 0", bg=COLOR_PANEL,
            fg=COLOR_TEXT, font=("Segoe UI", 12, "bold"),
        )
        self._progress_label.pack()

        stats = tk.Frame(right, bg=COLOR_PANEL)
        stats.pack(fill="x", padx=14, pady=10)

        def stat_lbl(text, color):
            f = tk.Frame(stats, bg=COLOR_SURFACE, padx=8, pady=6)
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
        self._mini_log = LogBox(right, height=12, font=("Consolas", 9))
        self._mini_log.pack(fill="both", expand=True, padx=10, pady=(0, 12))

        self._post_start_ts = None
        self._timer_job = None

    def _browse_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif *.bmp"), ("All files", "*.*")],
            title="Chọn ảnh đính kèm",
        )
        if path:
            cached = self._cache_image(path)
            self._image_var.set(cached)
            self._persist_draft()
            self._log(f"Đã lưu ảnh: {cached}", "ok")

    def _unique_message(self, message: str, group_id: str) -> str:
        """
        Thêm dấu ẩn (zero-width) riêng mỗi nhóm.
        Giúp tránh FB coi là spam trùng + tránh xác minh nhầm bài nhóm trước.
        """
        seed = f"{group_id}-{uuid.uuid4().hex[:8]}"
        bits = "".join(f"{ord(c):08b}" for c in seed[:10])
        zw = "".join("\u200b" if b == "0" else "\u200c" for b in bits)
        return message.rstrip() + zw

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

    def _live(self, msg: str, tag: str = "info"):
        """Ghi log tức thì vào cả mini log và nhật ký."""
        self._mini_log.log(msg, tag)
        self._log(msg, tag)
        self._status_line.set(msg[:80])
        self.update_idletasks()

    def _start_posting(self):
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

        image = self._image_var.get().strip() or None
        if image:
            image = self._cache_image(image)
            self._image_var.set(image)
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
        self._tick_timer()

        self._live(f"▶ Bắt đầu đăng vào {len(groups)} nhóm (delay {delay}s)", "bold")
        self._live("✅ Đã đăng | ⏳ Chờ duyệt | ❌ Lỗi — mỗi nhóm dùng post_id riêng", "info")

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
                # Nội dung có dấu ẩn riêng từng nhóm
                msg_for_group = self._unique_message(message, gid)

                def _prog(msg, _n=n, _t=t, _name=gname, _gid=gid):
                    self.after(
                        0,
                        lambda m=msg: self._live(f"[{_n}/{_t}] {_name} [{_gid}] — {m}", "info"),
                    )

                self.after(
                    0,
                    lambda: self._live(f"[{n}/{t}] Đang xử lý: {gname} [{gid}]…", "info"),
                )

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
                           p=pct, i=n, tt=t: self._on_post_result(
                        st, name, gid_, res, url, o, pnd, e, r, p, i, tt
                    ),
                )

                if idx < len(groups) - 1 and not self._stop_flag:
                    # Delay tăng dần nhẹ sau mỗi nhóm để giảm spam block
                    wait_s = int(delay) + min(idx * 2, 20)
                    for sec in range(wait_s):
                        if self._stop_flag:
                            break
                        left = wait_s - sec
                        self.after(
                            0,
                            lambda l=left: self._status_line.set(f"Chờ {l}s rồi đăng nhóm tiếp…"),
                        )
                        time.sleep(1)

            self.after(0, self._on_posting_done)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_post_result(self, status, name, gid, res, url, o, pnd, e, r, p, i, t):
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

        self._live(f"[{i}/{t}] {icon} {label} — {name} [{gid}]", tag)
        self._live(f"    → {res}", tag)
        self._live(f"    🔗 {url}", "info")

    def _stop_posting(self):
        self._stop_flag = True
        self._stop_btn.config(state="disabled")
        self._live("⏹ Đang dừng sau bài hiện tại…", "warn")

    def _on_posting_done(self):
        self._posting = False
        self._post_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
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

    def _save_all_now(self):
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
