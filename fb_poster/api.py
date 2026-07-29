"""Facebook Graph API client."""

import time
import logging
from typing import Optional
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


class FacebookAPIError(Exception):
    """Raised when the Facebook API returns an error."""

    def __init__(self, message: str, code: int = 0, subcode: int = 0):
        super().__init__(message)
        self.code = code
        self.subcode = subcode


class RateLimitError(FacebookAPIError):
    """Raised when API rate limit is hit."""


class FacebookClient:
    """Thin wrapper around the Facebook Graph API."""

    def __init__(self, access_token: str, timeout: int = 30):
        self.access_token = access_token
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "fb-group-poster/1.0"})

    def _base_params(self) -> dict:
        return {"access_token": self.access_token}

    def _handle_response(self, response: requests.Response) -> dict:
        try:
            data = response.json()
        except ValueError:
            response.raise_for_status()
            return {}

        if "error" in data:
            err = data["error"]
            msg = err.get("message", "Unknown Facebook API error")
            code = err.get("code", 0)
            subcode = err.get("error_subcode", 0)
            # Rate-limit codes: 4, 17, 32, 613
            if code in (4, 17, 32, 613):
                raise RateLimitError(msg, code, subcode)
            raise FacebookAPIError(msg, code, subcode)

        response.raise_for_status()
        return data

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        wait=wait_exponential(multiplier=30, min=60, max=600),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _post(self, endpoint: str, **data) -> dict:
        params = self._base_params()
        url = f"{GRAPH_API_BASE}/{endpoint}"
        response = self.session.post(url, params=params, data=data, timeout=self.timeout)
        return self._handle_response(response)

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        wait=wait_exponential(multiplier=30, min=60, max=600),
        stop=stop_after_attempt(4),
        reraise=True,
    )
    def _get(self, endpoint: str, **params) -> dict:
        all_params = {**self._base_params(), **params}
        url = f"{GRAPH_API_BASE}/{endpoint}"
        response = self.session.get(url, params=all_params, timeout=self.timeout)
        return self._handle_response(response)

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_me(self) -> dict:
        """Return basic info about the authenticated user."""
        return self._get("me", fields="id,name")

    def get_my_groups(self, limit: int = 200) -> list[dict]:
        """Return all groups the user has joined (requires groups_access_member_info)."""
        groups: list[dict] = []
        endpoint = "me/groups"
        params = {"fields": "id,name,privacy", "limit": limit}
        while True:
            data = self._get(endpoint, **params)
            groups.extend(data.get("data", []))
            paging = data.get("paging", {})
            next_url = paging.get("next")
            if not next_url:
                break
            # Extract cursor for next page
            cursors = paging.get("cursors", {})
            after = cursors.get("after")
            if not after:
                break
            params["after"] = after
        return groups

    def post_text_to_group(self, group_id: str, message: str) -> dict:
        """Post a plain-text message to a group feed."""
        return self._post(f"{group_id}/feed", message=message)

    def post_link_to_group(self, group_id: str, message: str, link: str) -> dict:
        """Post a message with a link to a group feed."""
        return self._post(f"{group_id}/feed", message=message, link=link)

    def post_photo_to_group(
        self,
        group_id: str,
        message: str,
        image_path: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> dict:
        """Post a photo with caption to a group.

        Provide either ``image_path`` (local file) or ``image_url``.
        """
        if image_path:
            path = Path(image_path)
            if not path.is_file():
                raise FileNotFoundError(f"Image not found: {image_path}")
            params = self._base_params()
            url = f"{GRAPH_API_BASE}/{group_id}/photos"
            with open(path, "rb") as fh:
                response = self.session.post(
                    url,
                    params=params,
                    data={"message": message},
                    files={"source": (path.name, fh, "image/jpeg")},
                    timeout=self.timeout,
                )
            return self._handle_response(response)
        elif image_url:
            return self._post(f"{group_id}/photos", message=message, url=image_url)
        else:
            raise ValueError("Provide either image_path or image_url.")
