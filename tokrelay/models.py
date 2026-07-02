from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import AnyUrl, BaseModel, Field


class Author(BaseModel):
    id: str | None = None
    username: str | None = None
    display_name: str | None = None
    avatar_url: AnyUrl | None = None
    profile_url: AnyUrl | None = None


class MusicInfo(BaseModel):
    id: str | None = None
    title: str | None = None
    author: str | None = None
    album: str | None = None
    duration_seconds: int | None = None
    cover_url: AnyUrl | None = None
    play_url: AnyUrl | None = None
    is_original: bool | None = None


class Engagement(BaseModel):
    plays: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saves: int | None = None


class TikTokPost(BaseModel):
    source_url: AnyUrl
    canonical_url: AnyUrl | None = None
    id: str | None = None
    title: str | None = None
    description: str | None = None
    created_at: datetime | None = None
    duration_seconds: int | None = None
    thumbnail_url: AnyUrl | None = None
    cover_url: AnyUrl | None = None
    embed_html: str | None = None
    author: Author = Field(default_factory=Author)
    music: MusicInfo | None = None
    engagement: Engagement = Field(default_factory=Engagement)
    raw: dict[str, Any] = Field(default_factory=dict, exclude=True)

    @property
    def discord_title(self) -> str:
        if self.title:
            return self.title[:256]
        if self.description:
            return self.description[:256]
        if self.author.username:
            return f"TikTok by @{self.author.username}"
        return "TikTok"

    @staticmethod
    def from_unix_timestamp(value: int | str | None) -> datetime | None:
        if value in (None, ""):
            return None
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return None
