from __future__ import annotations

import os

import discord
from dotenv import load_dotenv

from tokrelay.client import TikTokClient, TikTokClientError, find_tiktok_urls


load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)


@bot.event
async def on_ready() -> None:
    print(f"TokRelay is online as {bot.user}")


@bot.event
async def on_message(message: discord.Message) -> None:
    if message.author.bot:
        return

    urls = find_tiktok_urls(message.content)
    if not urls:
        return

    async with TikTokClient() as client:
        for url in urls[:3]:
            try:
                post = await client.fetch(url)
            except TikTokClientError as exc:
                await message.reply(f"I could not preview that TikTok: {exc}", mention_author=False)
                continue

            embed = discord.Embed(
                title=post.discord_title,
                url=str(post.canonical_url or post.source_url),
                color=0x25F4EE,
            )

            if post.author.username:
                name = f"@{post.author.username}"
                embed.set_author(name=name, url=str(post.author.profile_url or "https://www.tiktok.com"))

            if post.thumbnail_url:
                embed.set_image(url=str(post.thumbnail_url))

            stats = []
            if post.engagement.plays is not None:
                stats.append(f"{post.engagement.plays:,} plays")
            if post.engagement.likes is not None:
                stats.append(f"{post.engagement.likes:,} likes")
            if post.engagement.comments is not None:
                stats.append(f"{post.engagement.comments:,} comments")
            if stats:
                embed.set_footer(text=" | ".join(stats))

            await message.reply(embed=embed, mention_author=False)


token = os.getenv("DISCORD_TOKEN")
if not token:
    raise SystemExit("Set DISCORD_TOKEN in your environment or .env file.")

bot.run(token)

