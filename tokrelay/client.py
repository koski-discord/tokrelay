from __future__ import annotations

import html
import json
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode

import aiohttp

from .models import Author, Engagement, MusicInfo, TikTokPost

try:
    import orjson
except ImportError:
    orjson = None


TIKTOK_URL_RE = re.compile(
    r"https?://(?:www\.|m\.|vm\.|vt\.)?tiktok\.com/[^\s<>()\"']+",
    re.IGNORECASE,
)


class TikTokClientError(RuntimeError):
    pass


class TikTokClient:
    def __init__(
        self,
        *,
        timeout: float = 15,
        user_agent: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._owned_session = session is None
        self.session = session
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.headers = {
            "accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.9",
            "user-agent": user_agent
            or (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0 Safari/537.36 TokRelay/0.1"
            ),
        }

    async def __aenter__(self) -> "TikTokClient":
        if self.session is None:
            self.session = aiohttp.ClientSession(timeout=self.timeout, headers=self.headers)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._owned_session and self.session is not None:
            await self.session.close()

    async def fetch(self, url: str) -> TikTokPost:
        session = self._session()
        canonical_url = await self.resolve_url(url)

        oembed_data: dict[str, Any] = {}
        page_data: dict[str, Any] = {}

        try:
            oembed_data = await self._fetch_oembed(canonical_url)
        except TikTokClientError:
            pass

        try:
            page_data = await self._fetch_page_data(canonical_url)
        except TikTokClientError:
            pass

        if not oembed_data and not page_data:
            raise TikTokClientError("Could not read TikTok metadata for that URL.")

        return self._build_post(url, canonical_url, oembed_data, page_data)

    async def resolve_url(self, url: str) -> str:
        session = self._session()
        async with session.get(url, allow_redirects=True) as response:
            if response.status >= 400:
                raise TikTokClientError(f"TikTok returned HTTP {response.status} while resolving URL.")
            return str(response.url)

    async def _fetch_oembed(self, url: str) -> dict[str, Any]:
        session = self._session()
        params = urlencode({"url": url})
        endpoint = f"https://www.tiktok.com/oembed?{params}"
        async with session.get(endpoint, headers={"accept": "application/json"}) as response:
            if response.status >= 400:
                raise TikTokClientError(f"oEmbed returned HTTP {response.status}.")
            return await self._read_json(response)

    async def _fetch_page_data(self, url: str) -> dict[str, Any]:
        session = self._session()
        async with session.get(url) as response:
            if response.status >= 400:
                raise TikTokClientError(f"TikTok page returned HTTP {response.status}.")
            body = await response.text()

        for script_id in ("__UNIVERSAL_DATA_FOR_REHYDRATION__", "SIGI_STATE"):
            data = self._extract_json_script(body, script_id)
            item = self._find_item_struct(data)
            if item:
                return item
        return {}

    def _session(self) -> aiohttp.ClientSession:
        if self.session is None:
            raise TikTokClientError("Use TikTokClient as an async context manager.")
        return self.session

    async def _read_json(self, response: aiohttp.ClientResponse) -> dict[str, Any]:
        raw = await response.read()
        if orjson is not None:
            return orjson.loads(raw)
        return json.loads(raw)

    def _extract_json_script(self, body: str, script_id: str) -> dict[str, Any]:
        pattern = re.compile(
            rf'<script[^>]+id=["\']{re.escape(script_id)}["\'][^>]*>(.*?)</script>',
            re.DOTALL | re.IGNORECASE,
        )
        match = pattern.search(body)
        if not match:
            return {}
        text = html.unescape(match.group(1)).strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            if orjson is not None:
                return orjson.loads(text)
            return {}

    def _find_item_struct(self, data: Mapping[str, Any]) -> dict[str, Any]:
        if not data:
            return {}

        default_scope = data.get("__DEFAULT_SCOPE__")
        if isinstance(default_scope, Mapping):
            item = (
                default_scope.get("webapp.video-detail", {})
                .get("itemInfo", {})
                .get("itemStruct")
            )
            if isinstance(item, dict):
                return item

        item_module = data.get("ItemModule")
        if isinstance(item_module, Mapping) and item_module:
            first = next(iter(item_module.values()))
            if isinstance(first, dict):
                return first

        return {}

    def _build_post(
        self,
        source_url: str,
        canonical_url: str,
        oembed: Mapping[str, Any],
        item: Mapping[str, Any],
    ) -> TikTokPost:
        author_data = item.get("author") if isinstance(item.get("author"), Mapping) else {}
        stats = item.get("stats") if isinstance(item.get("stats"), Mapping) else {}
        video = item.get("video") if isinstance(item.get("video"), Mapping) else {}
        music = item.get("music") if isinstance(item.get("music"), Mapping) else {}

        username = author_data.get("uniqueId") or _strip_at(oembed.get("author_name"))
        profile_url = oembed.get("author_url")

        author = Author(
            id=_as_str(author_data.get("id")),
            username=username,
            display_name=author_data.get("nickname") or oembed.get("author_name"),
            avatar_url=_first_url(author_data.get("avatarLarger"), author_data.get("avatarMedium")),
            profile_url=profile_url,
        )

        music_info = None
        if music:
            music_info = MusicInfo(
                id=_as_str(music.get("id")),
                title=music.get("title"),
                author=music.get("authorName"),
                album=music.get("album"),
                duration_seconds=_as_int(music.get("duration")),
                cover_url=_first_url(music.get("coverLarge"), music.get("coverMedium")),
                play_url=_first_url(music.get("playUrl")),
                is_original=music.get("original"),
            )

        return TikTokPost(
            source_url=source_url,
            canonical_url=canonical_url,
            id=_as_str(item.get("id")),
            title=oembed.get("title") or item.get("desc"),
            description=item.get("desc") or oembed.get("title"),
            created_at=TikTokPost.from_unix_timestamp(item.get("createTime")),
            duration_seconds=_as_int(video.get("duration")),
            thumbnail_url=_first_url(oembed.get("thumbnail_url"), video.get("cover")),
            cover_url=_first_url(video.get("originCover"), video.get("dynamicCover"), video.get("cover")),
            embed_html=oembed.get("html"),
            author=author,
            music=music_info,
            engagement=Engagement(
                plays=_as_int(stats.get("playCount")),
                likes=_as_int(stats.get("diggCount")),
                comments=_as_int(stats.get("commentCount")),
                shares=_as_int(stats.get("shareCount")),
                saves=_as_int(stats.get("collectCount")),
            ),
            raw={"oembed": dict(oembed), "item": dict(item)},
        )


def find_tiktok_urls(text: str) -> list[str]:
    return [match.group(0).rstrip(".,)") for match in TIKTOK_URL_RE.finditer(text)]


def _strip_at(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    return value[1:] if value.startswith("@") else value


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _first_url(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    return None
