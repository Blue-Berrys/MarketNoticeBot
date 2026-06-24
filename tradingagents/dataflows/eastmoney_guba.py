"""Public Eastmoney Guba posts for verified ticker-specific communities.

Only explicit, manually verified dedicated-bar mappings are queried. Unknown
symbols do not fall back to Eastmoney's generic ``股市实战吧`` because those
posts are not evidence about the requested instrument.
"""

from __future__ import annotations

import html
import http.client
import json
import logging
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_API = "https://gbapi.eastmoney.com/webarticlelist/api/Article/Articlelist"
_UA = "Mozilla/5.0 TradingAgents/0.2 public-community-reader"

# Verified live on 2026-06-20. Add a mapping only after confirming the API's
# ``stockbar_name`` is dedicated to that exact underlying index/security.
VERIFIED_BARS: dict[str, tuple[str, str]] = {
    "000688.SS": ("zssh000688", "科创50吧"),
}


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    return " ".join(html.unescape(text).split())


def fetch_eastmoney_guba_posts(
    ticker: str,
    limit: int = 20,
    timeout: float = 10.0,
) -> str:
    """Fetch recent posts from a verified dedicated Eastmoney bar.

    Returns a prompt-ready plaintext block and degrades to an explicit
    placeholder on missing mappings, transport failures, or unexpected data.
    """
    canonical = ticker.upper()
    mapping = VERIFIED_BARS.get(canonical)
    if mapping is None:
        return (
            f"<no verified dedicated Eastmoney bar mapping for {canonical}; "
            "generic market forums were intentionally excluded>"
        )

    bar_code, expected_name = mapping
    query = urlencode(
        {
            "code": bar_code,
            "sorttype": "1",
            "ps": max(1, min(int(limit), 50)),
            "from": "CommonBaPost",
            "deviceid": "web",
            "version": "200",
            "product": "Guba",
            "plat": "Web",
        }
    )
    request = Request(
        f"{_API}?{query}",
        headers={
            "User-Agent": _UA,
            "Accept": "application/json,text/plain,*/*",
            "Referer": "https://guba.eastmoney.com/",
        },
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read())
    except (
        OSError,
        http.client.HTTPException,
        json.JSONDecodeError,
    ) as exc:
        logger.warning("Eastmoney Guba fetch failed for %s: %s", canonical, exc)
        return f"<eastmoney guba unavailable: {type(exc).__name__}>"

    posts = payload.get("re") if isinstance(payload, dict) else None
    if not isinstance(posts, list):
        return "<eastmoney guba unavailable: unexpected response shape>"

    verified = [
        post
        for post in posts
        if isinstance(post, dict) and post.get("stockbar_name") == expected_name
    ][:limit]
    if not verified:
        return (
            f"<no recent posts from verified Eastmoney bar {expected_name} "
            f"for {canonical}>"
        )

    lines = [
        f"{expected_name} — {len(verified)} recent public posts for {canonical}.",
        "Source type: retail-community opinions; not factual news.",
        "Xueqiu: anonymous access blocked by WAF. Weibo: anonymous access "
        "requires visitor verification. Neither source is represented below.",
    ]
    for post in verified:
        title = _strip_html(post.get("post_title"))
        excerpt = _strip_html(post.get("post_content"))
        if len(excerpt) > 240:
            excerpt = excerpt[:240] + "…"
        created = post.get("post_publish_time") or "?"
        reads = post.get("post_click_count")
        comments = post.get("post_comment_count")
        lines.append(
            f"[{created} · {reads if reads is not None else '?'} reads · "
            f"{comments if comments is not None else '?'} comments] {title}"
            + (f"\n  excerpt: {excerpt}" if excerpt else "")
        )
    return "\n".join(lines)
