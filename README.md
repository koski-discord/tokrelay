# TokRelay

Repo name suggestion: `tokrelay`

TokRelay is a small async Python client for turning public TikTok links into clean Discord-ready metadata. It uses TikTok's public oEmbed endpoint first, then attempts to read public page metadata as a fallback/enrichment layer.

It is meant for previews, embeds, moderation logs, and link expanders. It does not strip watermarks or bypass platform restrictions.

## Install

```bash
pip install -e ".[discord,speed]"
```

## Quick Use

```python
import asyncio
from tokrelay import TikTokClient

async def main():
    async with TikTokClient() as client:
        post = await client.fetch("https://www.tiktok.com/@tiktok/video/7106594312292457774")
        print(post.title)
        print(post.author.username)
        print(post.thumbnail_url)

asyncio.run(main())
```

## Discord Bot Example

Copy `.env.example` to `.env`, add your bot token, then run:

```bash
python examples/discord_bot.py
```

The bot watches for TikTok URLs and replies with a rich embed.

## Notes

- TikTok changes its page data often, so the oEmbed path is treated as the stable source.
- Page scraping may return partial data depending on region, age gates, removed posts, or anti-bot responses.
- Respect TikTok's terms and creators' rights when using media links.

## Publish to GitHub

Create a GitHub repository named `tokrelay`, then push this local folder:

```bash
git remote add origin https://github.com/YOUR_USERNAME/tokrelay.git
git branch -M main
git push -u origin main
```
