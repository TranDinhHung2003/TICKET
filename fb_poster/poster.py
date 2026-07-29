"""Core posting logic: iterate over a list of groups and post content."""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from .api import FacebookClient, FacebookAPIError, RateLimitError

logger = logging.getLogger(__name__)


@dataclass
class PostResult:
    group_id: str
    group_name: str
    success: bool
    post_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class PostConfig:
    """Configuration for a single posting campaign."""

    message: str
    link: Optional[str] = None
    image_path: Optional[str] = None
    image_url: Optional[str] = None
    # Seconds to wait between posts to avoid rate limits
    delay_between_posts: float = 10.0
    # Skip groups whose IDs are in this set
    skip_group_ids: set[str] = field(default_factory=set)


class GroupPoster:
    """Posts content to multiple Facebook groups."""

    def __init__(self, client: FacebookClient):
        self.client = client

    def post_to_groups(
        self,
        groups: list[dict],
        config: PostConfig,
        progress_callback=None,
    ) -> list[PostResult]:
        """Post ``config`` content to every group in ``groups``.

        Args:
            groups: List of dicts with ``id`` and ``name`` keys.
            config: Content and timing configuration.
            progress_callback: Optional callable(result, index, total) called
                after each attempt.

        Returns:
            List of PostResult instances.
        """
        results: list[PostResult] = []
        total = len(groups)

        for idx, group in enumerate(groups):
            group_id = str(group.get("id", ""))
            group_name = group.get("name", group_id)

            if group_id in config.skip_group_ids:
                logger.info("Skipping group %s (%s)", group_id, group_name)
                continue

            result = self._post_one(group_id, group_name, config)
            results.append(result)

            if progress_callback:
                progress_callback(result, idx + 1, total)

            # Throttle between posts (skip delay after the last one)
            if idx < total - 1 and config.delay_between_posts > 0:
                time.sleep(config.delay_between_posts)

        return results

    def _post_one(self, group_id: str, group_name: str, config: PostConfig) -> PostResult:
        try:
            if config.image_path or config.image_url:
                data = self.client.post_photo_to_group(
                    group_id,
                    config.message,
                    image_path=config.image_path,
                    image_url=config.image_url,
                )
            elif config.link:
                data = self.client.post_link_to_group(group_id, config.message, config.link)
            else:
                data = self.client.post_text_to_group(group_id, config.message)

            post_id = data.get("id") or data.get("post_id")
            logger.info("Posted to %s (%s): post_id=%s", group_name, group_id, post_id)
            return PostResult(
                group_id=group_id,
                group_name=group_name,
                success=True,
                post_id=post_id,
            )
        except RateLimitError as exc:
            logger.error("Rate limit hit for group %s: %s", group_name, exc)
            return PostResult(
                group_id=group_id,
                group_name=group_name,
                success=False,
                error=f"Rate limit: {exc}",
            )
        except FacebookAPIError as exc:
            logger.error("API error for group %s: %s", group_name, exc)
            return PostResult(
                group_id=group_id,
                group_name=group_name,
                success=False,
                error=str(exc),
            )
        except Exception as exc:
            logger.error("Unexpected error for group %s: %s", group_name, exc)
            return PostResult(
                group_id=group_id,
                group_name=group_name,
                success=False,
                error=str(exc),
            )
