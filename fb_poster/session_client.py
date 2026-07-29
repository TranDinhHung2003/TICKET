"""
Facebook Session Client — đăng bài bằng cookie/session, không cần developer account.

Cách hoạt động:
  1. Đăng nhập bằng email + mật khẩu để lấy cookies (hoặc nhập cookies thủ công).
  2. Dùng cookies đó để gọi các endpoint mobile/web của Facebook.

Lưu ý: Phương pháp này sử dụng giao diện không chính thức của Facebook.
Facebook có thể yêu cầu xác minh (CAPTCHA, 2FA) nếu phát hiện đăng nhập bất thường.
"""

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

# Facebook mobile endpoint — ít bị chặn hơn desktop
MOBILE_URL = "https://mbasic.facebook.com"
# Facebook GraphQL endpoint dùng cho một số tác vụ
GRAPH_URL = "https://www.facebook.com/api/graphql/"


class SessionLoginError(Exception):
    """Raised khi đăng nhập thất bại."""


class SessionPostError(Exception):
    """Raised khi đăng bài thất bại."""


class FacebookSessionClient:
    """
    Đăng bài lên nhóm Facebook bằng session cookies — không cần developer account.

    Sử dụng:
        client = FacebookSessionClient()
        client.login("email@gmail.com", "matkhau")
        client.post_to_group("GROUP_ID", "Nội dung bài đăng")
    """

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Mobile Safari/537.36"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    def __init__(self, cookies_file: Optional[str] = None):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._logged_in = False

        if cookies_file and Path(cookies_file).exists():
            self.load_cookies(cookies_file)

    # ------------------------------------------------------------------
    # Đăng nhập
    # ------------------------------------------------------------------

    def login(self, email: str, password: str) -> bool:
        """
        Đăng nhập bằng email + mật khẩu qua giao diện mobile Facebook.

        Trả về True nếu thành công, raise SessionLoginError nếu thất bại.
        """
        logger.info("Đang đăng nhập với tài khoản: %s", email)

        # Bước 1: Lấy trang đăng nhập để lấy các trường ẩn (lm, jazoest, ...)
        resp = self.session.get(f"{MOBILE_URL}/login/", timeout=30)
        resp.raise_for_status()

        form_data = self._extract_login_form(resp.text)
        if not form_data:
            raise SessionLoginError("Không thể đọc form đăng nhập từ Facebook.")

        # Bước 2: Submit form đăng nhập
        form_data.update({"email": email, "pass": password})
        login_resp = self.session.post(
            f"{MOBILE_URL}/login/device-based/regular/login/",
            data=form_data,
            allow_redirects=True,
            timeout=30,
        )

        # Kiểm tra đăng nhập thành công
        if self._is_logged_in(login_resp.text):
            self._logged_in = True
            logger.info("Đăng nhập thành công!")
            return True

        # Kiểm tra các thông báo lỗi phổ biến
        if "checkpoint" in login_resp.url or "checkpoint" in login_resp.text:
            raise SessionLoginError(
                "Facebook yêu cầu xác minh bảo mật (checkpoint). "
                "Hãy đăng nhập thủ công trên trình duyệt trước, "
                "sau đó dùng lệnh 'fb-poster session export-cookies' để lấy cookies."
            )
        if "incorrect" in login_resp.text.lower() or "wrong" in login_resp.text.lower():
            raise SessionLoginError("Email hoặc mật khẩu không đúng.")

        raise SessionLoginError(
            "Đăng nhập thất bại. Facebook có thể đang chặn đăng nhập tự động. "
            "Hãy thử xuất cookies từ trình duyệt (xem hướng dẫn bên dưới)."
        )

    def _extract_login_form(self, html: str) -> dict:
        """Trích xuất các trường form ẩn từ trang đăng nhập."""
        fields = {}
        for name, value in re.findall(
            r'<input[^>]+name=["\']([^"\']+)["\'][^>]+value=["\']([^"\']*)["\']',
            html,
        ):
            fields[name] = value
        for name, value in re.findall(
            r'<input[^>]+value=["\']([^"\']*)["\'][^>]+name=["\']([^"\']+)["\']',
            html,
        ):
            fields[name] = value
        return fields

    def _is_logged_in(self, html: str) -> bool:
        """Kiểm tra xem đã đăng nhập chưa dựa vào nội dung HTML."""
        indicators = ["mbasic_logout_button", "logout", "/logout", "c_user"]
        return any(ind in html for ind in indicators) and "login" not in html[:500].lower()

    # ------------------------------------------------------------------
    # Quản lý cookies
    # ------------------------------------------------------------------

    def save_cookies(self, path: str) -> None:
        """Lưu cookies hiện tại ra file JSON."""
        cookies = {c.name: c.value for c in self.session.cookies}
        Path(path).write_text(json.dumps(cookies, indent=2), encoding="utf-8")
        logger.info("Đã lưu cookies vào %s", path)

    def load_cookies(self, path: str) -> None:
        """Nạp cookies từ file JSON."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        for name, value in data.items():
            self.session.cookies.set(name, value, domain=".facebook.com")
        self._logged_in = "c_user" in data
        logger.info("Đã nạp cookies từ %s (logged_in=%s)", path, self._logged_in)

    def set_cookies_from_dict(self, cookies: dict) -> None:
        """Đặt cookies trực tiếp từ dict."""
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain=".facebook.com")
        self._logged_in = "c_user" in cookies

    def set_cookies_from_string(self, cookie_string: str) -> None:
        """
        Đặt cookies từ chuỗi dạng:  name1=value1; name2=value2

        Lấy chuỗi này bằng cách:
        1. Đăng nhập Facebook trên Chrome/Firefox
        2. Mở DevTools (F12) → tab Application → Cookies → facebook.com
        3. Hoặc dùng extension EditThisCookie / Cookie-Editor
        4. Copy toàn bộ cookies dưới dạng chuỗi
        """
        cookies = {}
        for part in cookie_string.split(";"):
            part = part.strip()
            if "=" in part:
                name, _, value = part.partition("=")
                cookies[name.strip()] = value.strip()
        self.set_cookies_from_dict(cookies)

    # ------------------------------------------------------------------
    # Đăng bài
    # ------------------------------------------------------------------

    def get_my_groups(self) -> list[dict]:
        """Lấy danh sách nhóm từ trang profile (parsing HTML mbasic)."""
        groups = []
        url = f"{MOBILE_URL}/groups/?seemore=1"
        resp = self.session.get(url, timeout=30)

        # Tìm tất cả link nhóm
        for gid, name in re.findall(
            r'href="/groups/(\d+)[^"]*"[^>]*>([^<]+)<', resp.text
        ):
            groups.append({"id": gid, "name": name.strip()})

        # Loại bỏ trùng lặp
        seen = set()
        unique = []
        for g in groups:
            if g["id"] not in seen:
                seen.add(g["id"])
                unique.append(g)
        return unique

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=5, max=30), reraise=True)
    def post_to_group(
        self,
        group_id: str,
        message: str,
        image_path: Optional[str] = None,
    ) -> bool:
        """
        Đăng bài lên nhóm Facebook.

        Args:
            group_id: ID của nhóm Facebook.
            message: Nội dung bài đăng.
            image_path: (tuỳ chọn) Đường dẫn ảnh cục bộ.

        Returns:
            True nếu đăng thành công.
        """
        # Bước 1: Lấy trang đăng bài của nhóm (lấy token form)
        group_url = f"{MOBILE_URL}/groups/{group_id}/"
        resp = self.session.get(group_url, timeout=30)

        if resp.status_code != 200:
            raise SessionPostError(f"Không thể truy cập nhóm {group_id}: HTTP {resp.status_code}")

        # Tìm form đăng bài
        post_action = self._find_post_form_action(resp.text, group_id)
        form_data = self._extract_post_form_fields(resp.text)

        if not post_action or not form_data:
            raise SessionPostError(
                f"Không tìm thấy form đăng bài trong nhóm {group_id}. "
                "Có thể bạn chưa là thành viên hoặc nhóm không cho phép đăng bài."
            )

        form_data["xc_message"] = message
        form_data["view_post"] = "Đăng"  # nút submit

        if image_path:
            return self._post_with_photo(post_action, form_data, image_path)

        # Bước 2: Submit bài đăng
        post_resp = self.session.post(
            f"{MOBILE_URL}{post_action}" if post_action.startswith("/") else post_action,
            data=form_data,
            allow_redirects=True,
            timeout=30,
        )

        if self._post_succeeded(post_resp.text, group_id):
            logger.info("Đã đăng bài vào nhóm %s thành công", group_id)
            return True

        raise SessionPostError(f"Đăng bài vào nhóm {group_id} thất bại.")

    def _find_post_form_action(self, html: str, group_id: str) -> Optional[str]:
        """Tìm action URL của form đăng bài."""
        # Tìm form có chứa compose/post
        patterns = [
            r'<form[^>]+action="(/groups/[^"]*compose[^"]*)"',
            r'<form[^>]+action="(/a/group/post/[^"]*)"',
            r'<form[^>]+action="([^"]*groups/' + group_id + r'[^"]*)"',
        ]
        for pattern in patterns:
            m = re.search(pattern, html)
            if m:
                return m.group(1)
        # Fallback: tìm form đầu tiên có method POST trong trang nhóm
        m = re.search(r'<form[^>]+method=["\']post["\'][^>]+action="([^"]+)"', html, re.IGNORECASE)
        if m:
            return m.group(1)
        return None

    def _extract_post_form_fields(self, html: str) -> dict:
        """Trích xuất các trường ẩn của form đăng bài."""
        fields = {}
        for name, value in re.findall(
            r'<input[^>]+type=["\']hidden["\'][^>]+name=["\']([^"\']+)["\'][^>]+value=["\']([^"\']*)["\']',
            html,
            re.IGNORECASE,
        ):
            fields[name] = value
        for name, value in re.findall(
            r'<input[^>]+name=["\']([^"\']+)["\'][^>]+type=["\']hidden["\'][^>]+value=["\']([^"\']*)["\']',
            html,
            re.IGNORECASE,
        ):
            fields[name] = value
        return fields

    def _post_with_photo(self, action: str, form_data: dict, image_path: str) -> bool:
        """Đăng bài kèm ảnh."""
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Không tìm thấy ảnh: {image_path}")

        url = f"{MOBILE_URL}{action}" if action.startswith("/") else action
        with open(path, "rb") as fh:
            resp = self.session.post(
                url,
                data=form_data,
                files={"file1": (path.name, fh, "image/jpeg")},
                allow_redirects=True,
                timeout=60,
            )
        return self._post_succeeded(resp.text, "")

    def _post_succeeded(self, html: str, group_id: str) -> bool:
        """Kiểm tra xem bài đăng có thành công không."""
        # Các dấu hiệu thành công
        success_signs = [
            "Bài viết của bạn",
            "Your post",
            "story_menu_item",
            "post_action",
            group_id,
        ]
        error_signs = ["error", "lỗi", "không thể", "failed"]
        text_lower = html.lower()
        has_success = any(s.lower() in html for s in success_signs)
        has_error = any(s in text_lower for s in error_signs[:3])
        return has_success and not has_error
