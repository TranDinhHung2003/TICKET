"""
Facebook Group Poster — Ứng dụng GUI Desktop
Đăng bài quảng cáo lên nhiều nhóm Facebook tự động.
"""

import json
import os
import re
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

APP_TITLE = "Facebook Group Poster"
APP_VERSION = "1.0.0"
COOKIES_FILE = Path.home() / ".fb_poster_cookies.json"
MOBILE_URL = "https://mbasic.facebook.com"

COLOR_BG = "#1a1a2e"
COLOR_PANEL = "#16213e"
COLOR_CARD = "#0f3460"
COLOR_ACCENT = "#e94560"
COLOR_ACCENT2 = "#533483"
COLOR_TEXT = "#eaeaea"
COLOR_TEXT_DIM = "#a0a0b0"
COLOR_SUCCESS = "#4ade80"
COLOR_ERROR = "#f87171"
COLOR_WARNING = "#fbbf24"
COLOR_BUTTON = "#e94560"
COLOR_BUTTON_HOVER = "#c73652"
COLOR_INPUT_BG = "#0a1628"
COLOR_INPUT_FG = "#eaeaea"


# ──────────────────────────────────────────────────────────────────────────────
# Facebook Session Backend
# ──────────────────────────────────────────────────────────────────────────────

class FacebookBackend:
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Mobile Safari/537.36"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.logged_in = False
        self._proxy = None

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

    def load_cookies(self, path: Path) -> bool:
        if not path.exists():
            return False
        data = json.loads(path.read_text(encoding="utf-8"))
        for name, value in data.items():
            self.session.cookies.set(name, value, domain=".facebook.com")
        self.logged_in = "c_user" in data
        return self.logged_in

    def save_cookies(self, path: Path):
        cookies = {c.name: c.value for c in self.session.cookies}
        path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")

    def set_cookies_from_string(self, cookie_str: str) -> bool:
        cookies = {}
        for part in cookie_str.split(";"):
            part = part.strip()
            if "=" in part:
                name, _, value = part.partition("=")
                cookies[name.strip()] = value.strip()
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain=".facebook.com")
        self.logged_in = "c_user" in cookies
        return self.logged_in

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
                timeout=30,
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
        try:
            resp = self.session.get(f"{MOBILE_URL}/", timeout=15)
            m = re.search(r'<title>([^<]+)</title>', resp.text)
            if m:
                return m.group(1).strip()
        except Exception:
            pass
        return "Người dùng Facebook"

    def scan_groups(self, progress_cb=None) -> list[dict]:
        """
        Quét danh sách nhóm từ nhiều endpoint khác nhau.
        Ưu tiên endpoint trả nhiều nhóm nhất.
        """
        groups: list[dict] = []
        seen: set[str] = set()

        # Danh sách endpoint sẽ thử theo thứ tự
        scan_urls = [
            f"{MOBILE_URL}/groups/?seemore=1",
            f"{MOBILE_URL}/groups/",
            "https://m.facebook.com/groups/?seemore=1",
            "https://m.facebook.com/groups/",
            f"{MOBILE_URL}/groups/feed/",
            f"{MOBILE_URL}/me/groups/",
        ]

        raw_pages: list[str] = []

        for url in scan_urls:
            try:
                if progress_cb:
                    progress_cb(f"🔍 Đang quét: {url}")
                resp = self.session.get(url, timeout=30)
                html = resp.text
                raw_pages.append(html)

                # Theo dõi tất cả link phân trang (xem thêm)
                more_links = re.findall(
                    r'href="(/groups/[^"]*(?:seemore|cursor|after)[^"]*)"', html
                )
                for link in more_links[:5]:
                    try:
                        r2 = self.session.get(f"{MOBILE_URL}{link}", timeout=20)
                        raw_pages.append(r2.text)
                    except Exception:
                        pass
            except Exception as exc:
                if progress_cb:
                    progress_cb(f"⚠️ Bỏ qua {url}: {exc}")

        if progress_cb:
            progress_cb("🔍 Đang trích xuất danh sách nhóm…")

        for html in raw_pages:
            self._extract_groups_from_html(html, groups, seen)

        # Nếu vẫn không tìm thấy, thử lấy qua GraphQL API nội bộ
        if not groups:
            if progress_cb:
                progress_cb("🔍 Thử phương pháp khác (GraphQL)…")
            gql_groups = self._scan_groups_graphql(progress_cb)
            for g in gql_groups:
                if g["id"] not in seen:
                    seen.add(g["id"])
                    groups.append(g)

        return groups

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

    def _scan_groups_graphql(self, progress_cb=None) -> list[dict]:
        """Thử lấy nhóm qua endpoint GraphQL nội bộ của Facebook."""
        groups: list[dict] = []
        try:
            # Lấy __user và __a token từ cookies/header
            cookies_dict = {c.name: c.value for c in self.session.cookies}
            uid = cookies_dict.get("c_user", "")
            if not uid:
                return groups

            # Gọi API groups của user
            url = f"{MOBILE_URL}/{uid}/groups/"
            if progress_cb:
                progress_cb(f"🔍 Quét profile groups: {url}")
            resp = self.session.get(url, timeout=30)
            seen: set[str] = set()
            self._extract_groups_from_html(resp.text, groups, seen)

            # Thử thêm trang app/groups
            url2 = f"{MOBILE_URL}/app/groups/"
            resp2 = self.session.get(url2, timeout=20)
            self._extract_groups_from_html(resp2.text, groups, seen)

        except Exception:
            pass
        return groups

    def post_to_group(self, group_id: str, message: str, image_path: str = None) -> tuple[bool, str]:
        try:
            group_url = f"{MOBILE_URL}/groups/{group_id}/"
            resp = self.session.get(group_url, timeout=30)
            if resp.status_code != 200:
                return False, f"HTTP {resp.status_code}"

            action = self._find_form_action(resp.text, group_id)
            fields = self._extract_hidden_fields(resp.text)

            if not action:
                return False, "Không tìm thấy form đăng bài (không phải thành viên?)"

            fields["xc_message"] = message
            fields["view_post"] = "Đăng"

            post_url = f"{MOBILE_URL}{action}" if action.startswith("/") else action

            if image_path and Path(image_path).is_file():
                with open(image_path, "rb") as fh:
                    post_resp = self.session.post(
                        post_url, data=fields,
                        files={"file1": (Path(image_path).name, fh, "image/jpeg")},
                        allow_redirects=True, timeout=60,
                    )
            else:
                post_resp = self.session.post(
                    post_url, data=fields,
                    allow_redirects=True, timeout=30,
                )

            if self._post_ok(post_resp.text):
                return True, "Thành công"
            return False, "Không xác nhận được bài đăng"

        except Exception as exc:
            return False, str(exc)

    def _find_form_action(self, html: str, group_id: str) -> str:
        patterns = [
            r'<form[^>]+action="(/groups/[^"]*compose[^"]*)"',
            r'<form[^>]+action="(/a/group/post/[^"]*)"',
            r'action="(/groups/' + group_id + r'/[^"]*)"',
        ]
        for p in patterns:
            m = re.search(p, html)
            if m:
                return m.group(1)
        m = re.search(r'<form[^>]+method=["\']post["\'][^>]+action="([^"]+)"', html, re.I)
        return m.group(1) if m else ""

    def _extract_hidden_fields(self, html: str) -> dict:
        """Trích xuất các hidden input field."""
        fields = {}
        for input_tag in re.finditer(r'<input\b([^>]*?)/?>', html, re.I | re.S):
            attrs_str = input_tag.group(1)
            attrs = {}
            for m in re.finditer(r'\b(\w+)\s*=\s*["\']([^"\']*)["\']', attrs_str):
                attrs[m.group(1).lower()] = m.group(2)
            name = attrs.get("name", "")
            value = attrs.get("value", "")
            itype = attrs.get("type", "").lower()
            if name and itype in ("hidden", ""):
                fields[name] = value
        return fields

    def _post_ok(self, html: str) -> bool:
        return any(x in html for x in ["story_menu", "Bài viết của bạn", "Your post", "post_action"])


# ──────────────────────────────────────────────────────────────────────────────
# Custom Widgets
# ──────────────────────────────────────────────────────────────────────────────

class HoverButton(tk.Button):
    def __init__(self, master, **kw):
        self._bg = kw.get("bg", COLOR_BUTTON)
        self._hover_bg = kw.pop("hover_bg", COLOR_BUTTON_HOVER)
        super().__init__(master, **kw)
        self.bind("<Enter>", lambda e: self.config(bg=self._hover_bg))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))


class LogBox(scrolledtext.ScrolledText):
    def __init__(self, master, **kw):
        defaults = dict(
            bg=COLOR_INPUT_BG, fg=COLOR_TEXT, font=("Consolas", 9),
            wrap=tk.WORD, state="disabled", relief="flat",
            insertbackground=COLOR_TEXT,
        )
        defaults.update(kw)
        super().__init__(master, **defaults)
        self.tag_config("ok", foreground=COLOR_SUCCESS)
        self.tag_config("err", foreground=COLOR_ERROR)
        self.tag_config("warn", foreground=COLOR_WARNING)
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
        self.title(f"{APP_TITLE} v{APP_VERSION}")
        self.geometry("1050x720")
        self.minsize(900, 620)
        self.configure(bg=COLOR_BG)
        self.resizable(True, True)

        # Try to set icon (works when bundled with PyInstaller)
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

        # Load saved cookies on startup
        self._auto_login()
        self._build_ui()

    def _auto_login(self):
        if COOKIES_FILE.exists():
            self.backend.load_cookies(COOKIES_FILE)

    # ── UI BUILD ──────────────────────────────────────────────────────────────

    def _build_ui(self):
        # Header
        header = tk.Frame(self, bg=COLOR_CARD, height=56)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        tk.Label(
            header,
            text=f"  📣  {APP_TITLE}",
            bg=COLOR_CARD, fg=COLOR_TEXT,
            font=("Segoe UI", 15, "bold"),
        ).pack(side="left", padx=16, pady=10)

        self._status_var = tk.StringVar(value="⚪ Chưa đăng nhập")
        tk.Label(
            header,
            textvariable=self._status_var,
            bg=COLOR_CARD, fg=COLOR_TEXT_DIM,
            font=("Segoe UI", 10),
        ).pack(side="right", padx=20)

        # Notebook tabs
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Custom.TNotebook",
            background=COLOR_BG, borderwidth=0,
        )
        style.configure(
            "Custom.TNotebook.Tab",
            background=COLOR_PANEL, foreground=COLOR_TEXT_DIM,
            padding=[16, 8], font=("Segoe UI", 10),
        )
        style.map(
            "Custom.TNotebook.Tab",
            background=[("selected", COLOR_CARD)],
            foreground=[("selected", COLOR_TEXT)],
        )

        nb = ttk.Notebook(self, style="Custom.TNotebook")
        nb.pack(fill="both", expand=True, padx=0, pady=0)

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

        card = tk.Frame(outer, bg=COLOR_PANEL, padx=40, pady=36)
        card.pack(pady=40, padx=20)

        tk.Label(card, text="Đăng nhập Facebook", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Segoe UI", 14, "bold")).grid(row=0, column=0, columnspan=2, pady=(0, 20))

        # ── Notebook bên trong: Email/Password vs Cookie ──
        inner_nb = ttk.Notebook(card, style="Custom.TNotebook")
        inner_nb.grid(row=1, column=0, columnspan=2)

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
        self._login_status.grid(row=2, column=0, columnspan=2, pady=(16, 0))

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
        if ok:
            self.backend.save_cookies(COOKIES_FILE)
            self._login_status.config(text="✅ Cookies hợp lệ! Đã lưu.", fg=COLOR_SUCCESS)
            self._on_login_success_ui()
        else:
            self._login_status.config(
                text="⚠️ Không tìm thấy c_user trong cookies. Thử lại.", fg=COLOR_WARNING
            )

    def _on_login_success_ui(self):
        name = self.backend.get_profile_name() if self.backend.logged_in else "?"
        self._status_var.set(f"🟢 Đã đăng nhập: {name}")
        self._log(f"Đã đăng nhập thành công: {name}", "ok")

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
            messagebox.showwarning("Chưa đăng nhập", "Vui lòng đăng nhập trước.")
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
        if groups:
            self._scan_progress_var.set(f"✅ Quét xong — tìm thấy {len(groups)} nhóm")
            self._log(f"Quét xong: {len(groups)} nhóm", "ok")
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
        self._manual_id_var.set("")
        self._manual_name_var.set("")
        self._log(f"Đã thêm nhóm thủ công: {name} ({gid})", "ok")

    # ── POST TAB ──────────────────────────────────────────────────────────────

    def _build_post_tab(self):
        tab = self._tab_post

        # Left: compose
        left = tk.Frame(tab, bg=COLOR_BG)
        left.pack(side="left", fill="both", expand=True, padx=(16, 8), pady=12)

        tk.Label(left, text="Soạn bài đăng", bg=COLOR_BG, fg=COLOR_TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 8))

        tk.Label(left, text="Nội dung bài đăng:", bg=COLOR_BG, fg=COLOR_TEXT_DIM,
                 font=("Segoe UI", 10)).pack(anchor="w")

        self._msg_text = scrolledtext.ScrolledText(
            left, height=10, bg=COLOR_INPUT_BG, fg=COLOR_INPUT_FG,
            insertbackground=COLOR_TEXT, relief="flat",
            font=("Segoe UI", 11), wrap=tk.WORD,
        )
        self._msg_text.pack(fill="both", expand=True, pady=(4, 10))

        # Image
        img_row = tk.Frame(left, bg=COLOR_BG)
        img_row.pack(fill="x", pady=4)
        tk.Label(img_row, text="Ảnh đính kèm (tuỳ chọn):", bg=COLOR_BG,
                 fg=COLOR_TEXT_DIM, font=("Segoe UI", 10)).pack(side="left")

        self._image_var = tk.StringVar()
        img_entry = tk.Entry(img_row, textvariable=self._image_var, width=32,
                             bg=COLOR_INPUT_BG, fg=COLOR_INPUT_FG, insertbackground=COLOR_TEXT,
                             relief="flat", font=("Segoe UI", 10))
        img_entry.pack(side="left", padx=(8, 4), ipady=4)

        HoverButton(
            img_row, text="📁", command=self._browse_image,
            bg=COLOR_CARD, fg=COLOR_TEXT, relief="flat", cursor="hand2",
            font=("Segoe UI", 11), padx=6,
        ).pack(side="left")

        HoverButton(
            img_row, text="✖", command=lambda: self._image_var.set(""),
            bg=COLOR_CARD, fg=COLOR_ERROR, relief="flat", cursor="hand2",
            font=("Segoe UI", 11), padx=6,
        ).pack(side="left", padx=4)

        # Delay
        delay_row = tk.Frame(left, bg=COLOR_BG)
        delay_row.pack(fill="x", pady=8)
        tk.Label(delay_row, text="Delay giữa các bài (giây):", bg=COLOR_BG,
                 fg=COLOR_TEXT_DIM, font=("Segoe UI", 10)).pack(side="left")
        self._delay_var = tk.DoubleVar(value=20)
        delay_spin = tk.Spinbox(
            delay_row, from_=5, to=300, textvariable=self._delay_var,
            width=6, bg=COLOR_INPUT_BG, fg=COLOR_INPUT_FG, relief="flat",
            font=("Segoe UI", 11), buttonbackground=COLOR_CARD,
            insertbackground=COLOR_TEXT,
        )
        delay_spin.pack(side="left", padx=(8, 4), ipady=3)
        tk.Label(delay_row, text="giây", bg=COLOR_BG, fg=COLOR_TEXT_DIM,
                 font=("Segoe UI", 10)).pack(side="left")

        # Buttons
        btn_row = tk.Frame(left, bg=COLOR_BG)
        btn_row.pack(fill="x", pady=(8, 0))

        self._post_btn = HoverButton(
            btn_row, text="  🚀  Bắt đầu đăng bài  ", command=self._start_posting,
            bg=COLOR_BUTTON, fg="white", font=("Segoe UI", 12, "bold"),
            relief="flat", cursor="hand2", padx=24, pady=10,
        )
        self._post_btn.pack(side="left", padx=(0, 8))

        self._stop_btn = HoverButton(
            btn_row, text="⏹  Dừng", command=self._stop_posting,
            bg=COLOR_CARD, fg=COLOR_ERROR, font=("Segoe UI", 11, "bold"),
            relief="flat", cursor="hand2", padx=16, pady=10, state="disabled",
        )
        self._stop_btn.pack(side="left")

        # Right: progress
        right = tk.Frame(tab, bg=COLOR_PANEL, width=280)
        right.pack(side="right", fill="y", padx=(0, 16), pady=12)
        right.pack_propagate(False)

        tk.Label(right, text="Tiến trình đăng bài", bg=COLOR_PANEL, fg=COLOR_TEXT,
                 font=("Segoe UI", 11, "bold")).pack(pady=(12, 6), padx=12, anchor="w")

        # Progress bar
        style = ttk.Style()
        style.configure("Red.Horizontal.TProgressbar",
                        troughcolor=COLOR_INPUT_BG, background=COLOR_ACCENT)
        self._progress_var = tk.DoubleVar(value=0)
        self._progress_bar = ttk.Progressbar(
            right, variable=self._progress_var,
            style="Red.Horizontal.TProgressbar",
            maximum=100, length=240,
        )
        self._progress_bar.pack(padx=12, pady=(0, 8))

        self._progress_label = tk.Label(right, text="0 / 0", bg=COLOR_PANEL,
                                        fg=COLOR_TEXT_DIM, font=("Segoe UI", 10))
        self._progress_label.pack()

        # Stats
        stats = tk.Frame(right, bg=COLOR_PANEL)
        stats.pack(fill="x", padx=12, pady=8)

        def stat_lbl(text, color):
            f = tk.Frame(stats, bg=COLOR_PANEL)
            f.pack(fill="x", pady=3)
            lbl = tk.Label(f, text="0", bg=COLOR_PANEL, fg=color,
                           font=("Segoe UI", 18, "bold"))
            lbl.pack(side="left")
            tk.Label(f, text=f"  {text}", bg=COLOR_PANEL, fg=COLOR_TEXT_DIM,
                     font=("Segoe UI", 10)).pack(side="left")
            return lbl

        self._ok_lbl = stat_lbl("Thành công", COLOR_SUCCESS)
        self._err_lbl = stat_lbl("Thất bại", COLOR_ERROR)
        self._skip_lbl = stat_lbl("Đang chờ", COLOR_WARNING)

        # Mini log in post tab
        tk.Label(right, text="Log nhanh:", bg=COLOR_PANEL, fg=COLOR_TEXT_DIM,
                 font=("Segoe UI", 9)).pack(padx=12, anchor="w", pady=(12, 2))
        self._mini_log = LogBox(right, height=10, font=("Consolas", 8))
        self._mini_log.pack(fill="both", expand=True, padx=8, pady=(0, 12))

    def _browse_image(self):
        path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.gif *.bmp"), ("All files", "*.*")],
            title="Chọn ảnh đính kèm",
        )
        if path:
            self._image_var.set(path)

    def _get_selected_groups(self) -> list[dict]:
        return [g for var, g in self._group_vars if var.get()]

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
        delay = float(self._delay_var.get())

        self._posting = True
        self._stop_flag = False
        self._post_btn.config(state="disabled")
        self._stop_btn.config(state="normal")
        self._ok_lbl.config(text="0")
        self._err_lbl.config(text="0")
        self._skip_lbl.config(text=str(len(groups)))
        self._progress_var.set(0)
        self._progress_label.config(text=f"0 / {len(groups)}")
        self._mini_log.clear()
        self._log(f"Bắt đầu đăng bài vào {len(groups)} nhóm…", "bold")

        def _worker():
            ok_count = 0
            err_count = 0
            for idx, g in enumerate(groups):
                if self._stop_flag:
                    self.after(0, lambda: self._log("⏹ Đã dừng bởi người dùng.", "warn"))
                    break

                gid = g["id"]
                gname = g["name"]
                self.after(0, lambda n=gname: self._log(f"→ Đang đăng: {n}…", "info"))

                success, msg_result = self.backend.post_to_group(gid, message, image)

                def _update(i=idx, ok=success, name=gname, res=msg_result, ok_c=ok_count, err_c=err_count):
                    pass  # handled below

                if success:
                    ok_count += 1
                else:
                    err_count += 1

                remaining = len(groups) - idx - 1
                pct = ((idx + 1) / len(groups)) * 100

                self.after(0, lambda ok=success, name=gname, res=msg_result,
                                      o=ok_count, e=err_count, r=remaining, p=pct, i=idx+1, t=len(groups): (
                    self._ok_lbl.config(text=str(o)),
                    self._err_lbl.config(text=str(e)),
                    self._skip_lbl.config(text=str(r)),
                    self._progress_var.set(p),
                    self._progress_label.config(text=f"{i} / {t}"),
                    self._mini_log.log(
                        f"{'✓' if ok else '✗'} {name}: {res}",
                        "ok" if ok else "err",
                    ),
                    self._log(
                        f"[{i}/{t}] {'✅' if ok else '❌'} {name} — {res}",
                        "ok" if ok else "err",
                    ),
                ))

                if idx < len(groups) - 1 and not self._stop_flag:
                    time.sleep(delay)

            self.after(0, self._on_posting_done)

        threading.Thread(target=_worker, daemon=True).start()

    def _stop_posting(self):
        self._stop_flag = True
        self._stop_btn.config(state="disabled")
        self._log("⏹ Đang dừng sau bài hiện tại…", "warn")

    def _on_posting_done(self):
        self._posting = False
        self._post_btn.config(state="normal")
        self._stop_btn.config(state="disabled")
        ok = int(self._ok_lbl.cget("text"))
        err = int(self._err_lbl.cget("text"))
        self._log(f"✅ Hoàn thành! {ok} thành công, {err} thất bại.", "bold")
        messagebox.showinfo("Hoàn thành", f"Đã đăng bài xong!\n✅ {ok} thành công\n❌ {err} thất bại")

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
