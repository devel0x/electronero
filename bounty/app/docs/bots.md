# Telegram and Discord Bots

This app uses Telegram and Discord bots to verify that users join your community channels before awarding points.

## Why a Telegram Bot?

The backend calls Telegram's `getChatMember` method with a bot token to check membership in your group or channel. The bot must:

1. Be created via **@BotFather** and added to your group or channel.
2. Have permission to read member status.

## Why a Discord Bot?

To verify Discord server membership the backend queries the guild's member list. The bot token must belong to a bot that:

1. Has the **Guild Members** intent enabled in the developer portal.
2. Is invited to your server with permission to view members.

## Example Telegram Bot

Below is a minimal bot using `python-telegram-bot`. Users run `/verify <username>` to link their Telegram account to their referral account. The bot forwards the request to the API and confirms membership.

```python
# telegram_bot_example.py
import os
import httpx
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

API_URL = os.getenv("APP_API_URL", "http://localhost:8000")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send /verify <username> to link your account.")

async def verify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /verify <username>")
        return
    username = context.args[0]
    httpx.post(f"{API_URL}/telegram_verify", json={"telegram_id": update.effective_user.id, "username": username})
    await update.message.reply_text("Verification request sent!")

async def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    application = ApplicationBuilder().token(token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("verify", verify))
    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Example Discord Bot

Here is a simple Discord bot using `discord.py`. Members issue `!verify <username>` in any channel. The bot contacts the API with the user's Discord ID and chosen username.

```python
# discord_bot_example.py
import os
import httpx
import discord

API_URL = os.getenv("APP_API_URL", "http://localhost:8000")
intents = discord.Intents.default()
intents.members = True

class ReferralBot(discord.Client):
    async def on_ready(self):
        print(f"Logged in as {self.user}")

    async def on_message(self, message):
        if message.author.bot:
            return
        if not message.content.startswith("!verify"):
            return
        parts = message.content.split(maxsplit=1)
        if len(parts) != 2:
            await message.channel.send("Usage: !verify <username>")
            return
        username = parts[1]
        httpx.post(f"{API_URL}/discord_verify", json={"discord_id": message.author.id, "username": username})
        await message.channel.send("Verification request sent!")

client = ReferralBot(intents=intents)
client.run(os.getenv("DISCORD_BOT_TOKEN"))
```

## Required Actions and Permissions

1. Create the bots and obtain `TELEGRAM_BOT_TOKEN` and `DISCORD_BOT_TOKEN`.
2. Add the Telegram bot to your group and note the `TELEGRAM_GROUP_ID`.
3. Invite the Discord bot to your server and set `DISCORD_GUILD_ID`.
4. Enable `Guild Members` intent for the Discord bot in the developer portal.
5. Set the bot tokens and IDs as environment variables so the backend can query the APIs.

With these bots in place, the referral app can verify users automatically whenever they join the required channels.
