# Token Explorer

This lightweight Flask application provides a simple token transaction explorer for the Electronero network. It queries `electronero-wallet-rpc` to retrieve transfer history.

## Requirements

- Python 3.8+
- `Flask` and `requests` (`pip install -r requirements.txt`)

## Usage

Run `electronero-wallet-rpc` on `localhost:18082` and then start the explorer:

```bash
python3 app.py
```

Visit <http://localhost:5000> in a browser. The home page lists all known tokens and lets you search by token or participant address. A filter box above the table makes it easy to find a specific token. Results are displayed in responsive tables with a search box. A theme toggle allows switching between light and dark modes and your preference is saved in `localStorage`.

## Features

- Responsive layout with light and dark themes
- Lists all known tokens with on-page search
- History queries by token address or participant address
- Simple forms on the home page for ad hoc lookups
- Token history pages show a stats card with name, symbol, supply, and creator fee

## Endpoints

- `/token/<token_address>` – JSON token history. Optional `address` query parameter filters by participant.
- `/address/<address>` – JSON address history.

When using query parameters (`/token?token=...` or `/address?addr=...`), results render as styled HTML pages.

The wallet RPC currently returns transfer history under a `transfers` field. The explorer
handles this and displays each entry in a table.

## Future Enhancements

We plan to continue improving the explorer with features such as:

- Persistent caching of token data to reduce RPC load
- Sorting and filtering options on history tables
- Graphs summarizing token transfer activity over time
- Support for additional wallet RPC endpoints
- User preferences stored in browser local storage

Contributions are welcome!
