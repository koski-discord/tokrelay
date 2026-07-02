from __future__ import annotations

import asyncio
import sys

from tokrelay.client import TikTokClient


async def main(url: str) -> None:
    async with TikTokClient() as client:
        post = await client.fetch(url)
        print(post.model_dump_json(indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python examples/preview.py <tiktok-url>")
    asyncio.run(main(sys.argv[1]))
