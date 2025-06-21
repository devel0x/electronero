# Telegram Bot for Electronero RPC

This bot exposes all wallet and daemon RPC methods via Telegram commands.
It relies on `electronero.php` for JSON-RPC interaction.

## Setup

1. Install PHP with the cURL extension.
2. Set the `TELEGRAM_TOKEN` environment variable to your bot token.
3. Run the bot:

```bash
php modules/PHP/telegram.php
```

The bot uses long polling to receive updates and provides a simple menu system.

## Usage

- `/menu` &mdash; shows buttons for "Wallet" and "Daemon" RPC groups.
- `/wallet` &mdash; displays a keyboard with wallet RPC methods.
- `/daemon` &mdash; displays a keyboard with daemon RPC methods.
- `/help` &mdash; lists all available RPC commands as plain text.
- Any other command `/method {json}` calls the corresponding RPC method.
  - `method` must match a wallet or daemon RPC name.
  - Optional JSON parameters can be supplied after a space.

### Example

```
/get_balance {"account_index":0}
/get_info
```

The first example calls the wallet's `get_balance` method; the second
invokes the daemon's `get_info` method.

The response from the RPC server is returned to the chat as JSON.
