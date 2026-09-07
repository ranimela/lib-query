"""ntfy Alert Dispatcher module."""

import base64
import httpx
from src.models import Coupon


def _encode_rfc2047(text: str) -> str:
    """Encode a string into RFC 2047 format for safe HTTP header transport."""
    if text.isascii():
        return text
    b64_str = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"=?utf-8?b?{b64_str}?="


class Notifier:
    """Dispatches notifications via ntfy HTTP API."""

    def __init__(self, ntfy_topic_url: str, timeout_seconds: float = 10.0) -> None:
        self.ntfy_topic_url = ntfy_topic_url
        self.timeout_seconds = timeout_seconds

    def notify_coupon(self, coupon: Coupon) -> bool:
        """Send a notification for a single new coupon.

        Args:
            coupon: The novel Coupon object to notify.

        Returns:
            True if HTTP dispatch succeeded, False otherwise.
        """
        title_text = f"🎁 {coupon.title}"
        if coupon.code:
            title_text = f"🎁 {coupon.title} (Code: {coupon.code})"

        body_lines = [f"Title: {coupon.title}"]
        if coupon.code:
            body_lines.append(f"Coupon Code: {coupon.code}")
        if coupon.expiration_date:
            body_lines.append(f"Expires: {coupon.expiration_date}")
        if coupon.description:
            body_lines.append(f"Details: {coupon.description}")

        message_text = "\n".join(body_lines)

        headers = {
            "Title": _encode_rfc2047(title_text),
            "Priority": "3",  # Normal priority
            "Tags": "ticket,library,coupon",
        }
        if coupon.link:
            headers["Actions"] = f"view, Open Coupon, {coupon.link}"

        try:
            response = httpx.post(
                self.ntfy_topic_url,
                content=message_text.encode("utf-8"),
                headers=headers,
                timeout=self.timeout_seconds,
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def notify_failure(self, error_summary: str, details: str = "") -> bool:
        """Send a high-priority system alert when pipeline execution fails.

        Args:
            error_summary: Brief description of the failure.
            details: Extended diagnostic details or error string.

        Returns:
            True if HTTP dispatch succeeded, False otherwise.
        """
        title_text = f"Library Scraper Failed: {error_summary}"
        headers = {
            "Title": _encode_rfc2047(title_text),
            "Priority": "5",  # High / urgent priority
            "Tags": "warning,alert,robot",
        }
        message_text = f"Execution failed at {error_summary}.\n\nDetails: {details}"

        try:
            response = httpx.post(
                self.ntfy_topic_url,
                content=message_text.encode("utf-8"),
                headers=headers,
                timeout=self.timeout_seconds,
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def notify_status(self, message: str) -> bool:
        """Send an informational status notification (daily run heartbeat).

        Args:
            message: Status message content.

        Returns:
            True if HTTP dispatch succeeded, False otherwise.
        """
        title_text = "Library Scraper Run Completed"
        headers = {
            "Title": _encode_rfc2047(title_text),
            "Priority": "2",  # Low/info priority
            "Tags": "information,robot",
        }
        try:
            response = httpx.post(
                self.ntfy_topic_url,
                content=message.encode("utf-8"),
                headers=headers,
                timeout=self.timeout_seconds,
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False


