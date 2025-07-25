# Bounty Referral App

This application tracks user referral tasks using FastAPI with a MySQL backend.

## Setup

1. Install requirements
   ```bash
   pip install -r requirements.txt
   ```
2. Create the MySQL database referenced by `DATABASE_URL` (for example `referral_db`). The tables themselves are created automatically when the server starts.
3. Configure `DATABASE_URL` in `database.py` and set any API tokens (Telegram, X, Discord, Reddit) as environment variables.
   Additionally provide the links that users should follow via environment variables:
   `TELEGRAM_URL`, `X_PROFILE_URL`, `DISCORD_URL`, `WEB_WALLET_URL`,
    `MOBILE_WALLET_URL`, `NEWSLETTER_URL`, `REDDIT_URL`, `TWEET_URL`,
   `REFERRAL_BASE_URL`, `ITC_PER_POINT`, `INTERCHAINED_CLI`,
    `DEFAULT_LANGUAGE`, `CAPTCHA_SECRET`, `ADMIN_PASSWORD`,
    `TELEGRAM_BOT_TOKEN` and `TELEGRAM_GROUP_ID`.
   The `CAPTCHA_SECRET` value comes from the Google reCAPTCHA admin
   console. Create a site at <https://www.google.com/recaptcha/admin>,
   then copy the generated **secret key** here.
   Set `NOCAPTCHA=true` to disable CAPTCHA checks during testing.
4. Run the application
   ```bash
   uvicorn main:app --reload --port ${SERVER_PORT:-8000}
   ```
5. Open `http://localhost:${SERVER_PORT:-8000}` in a browser to use the built‑in frontend.

## API Endpoints

- `POST /users` - create a new user
- `POST /tasks/{user_id}` - verify completion of a task and award points
- `GET /progress/{user_id}` - retrieve the user's points and completed tasks
- `GET /admin` - view the administrator dashboard (HTML)
- `GET /analytics/leaderboard` - referral leaderboard in JSON format
- `POST /payout_address` - save the ITC wallet address for payouts
- `POST /process_claim/{claim_id}` - send a manual payment using `interchained-cli`

## Submission Guidelines

1. Sign up with the `/users` endpoint by providing a unique `username` and `password` along with
   `email`, `telegram_handle`, `twitter_handle`, `discord_handle` and `reddit_username`.
   Include the `captcha_token` returned by your CAPTCHA widget. You may also supply
   an optional `referral_code`. If no code is provided one will be created automatically.
   Each IP may register only once and duplicate emails are rejected.
2. Use the provided user ID when submitting task completion via `/tasks/{user_id}`.
3. Tasks correspond to actions such as following social profiles or registering a wallet. Each successful verification grants points.
4. Points can be exchanged for rewards once the configured threshold is met. The logic for rewards can be customised in `main.py`.
5. Submit your payout wallet address via the `/payout_address` endpoint so administrators know where to send rewards.

## Usage Guidelines

* **Run locally** – execute `uvicorn main:app --reload` after installing dependencies. Visit `http://localhost:8000` to use the simple HTML frontend. The home page includes a short introduction for new users.
* **Environment variables** – provide API tokens for Telegram, X (Twitter), Discord and Reddit. Set `DATABASE_URL` to your MySQL instance.
* **Wallet and newsletter** – register web or mobile wallets via the `/wallets` endpoint, provide a payout address through `/payout_address`, and sign up to the mailing list with `/newsletter`.
* **Authentication** – supply your username and password using HTTP Basic when calling user-specific endpoints such as `/tasks/{user_id}`, `/payout_address`, `/claim/{user_id}` and `/progress/{user_id}`.
* **Languages** – set `DEFAULT_LANGUAGE` to control which translation is shown by default. Supported codes are `en`, `es` and `fr`. Users may specify `/?lang=es` or another code to view the interface in that language.

## Social Links

The homepage shows links for each task so users know which profiles to follow or posts to share. These URLs are loaded from environment variables. Set them before running the app:

```
TELEGRAM_URL      # Link to your Telegram group or channel
X_PROFILE_URL     # Link to your X/Twitter profile to follow
DISCORD_URL       # Discord invite link
WEB_WALLET_URL    # Registration page for the web wallet
MOBILE_WALLET_URL # Registration page for the mobile wallet
NEWSLETTER_URL    # Sign‑up page for the newsletter
REDDIT_URL        # Subreddit or profile to follow
TWEET_URL         # URL of the tweet users should share
REFERRAL_BASE_URL # Base URL used when displaying the referral link
REWARD_THRESHOLD  # Minimum points needed to claim rewards
ITC_PER_POINT     # Amount of ITC paid out per point when claiming
INTERCHAINED_CLI  # Path to the `interchained-cli` executable used for payouts
DEFAULT_LANGUAGE  # Default language code for the interface (e.g. 'en')
SERVER_PORT       # Port the FastAPI server runs on
CAPTCHA_SECRET    # Secret token for verifying CAPTCHA responses
NOCAPTCHA         # Set to 'true' to bypass CAPTCHA verification
TELEGRAM_BOT_TOKEN # Token for the bot used to check Telegram membership
TELEGRAM_GROUP_ID # Numeric ID of the Telegram group to verify
ADMIN_PASSWORD    # Password required to access the /admin dashboard
```
To obtain your Telegram group ID, invite the `@userinfobot` (or a similar bot)
to your group and send `/start`. The bot will reply with the numeric
`chat_id`, which is the value to use for `TELEGRAM_GROUP_ID`.

## Claiming Rewards

Users accumulate points for completing tasks. Once a user reaches
`REWARD_THRESHOLD` points they may issue a `POST` request to
`/claim/{user_id}` or click the **Claim Reward** button on the
homepage. The server records the claim and resets the user’s point
balance. The amount of Interchained (ITC) awarded is calculated using
`ITC_PER_POINT`:

```
reward_itc = points * ITC_PER_POINT
```

Administrators can process payouts manually based on the recorded
`reward_itc` amounts. Use `/process_claim/{claim_id}` to trigger a payment
via `interchained-cli` once ready.

## Administrator Guidelines

* Ensure a MySQL database is available and update `DATABASE_URL` accordingly. Tables are created automatically on start.
* Create and manage API tokens for third‑party services used by the verification helpers in `utils.py`.
* To modify tasks or reward logic, edit the mappings in `main.py` and the `Task` entries in the database.
* Update the social links presented on the homepage by setting the environment variables listed in the **Social Links** section. Restart the server for changes to take effect.
* Reward claims are stored in the `reward_claims` table. Review these records and distribute payouts manually to the registered wallet addresses.
* Each user record also stores a `wallet_address` field submitted via `/payout_address`. Use this to know where to send rewards.
* Use `/process_claim/{claim_id}` to execute a payment. Set `INTERCHAINED_CLI` to the path of the `interchained-cli` binary so the server can call it.
* Adjust the point-to-reward ratio by setting `ITC_PER_POINT` before starting the server. Increasing this value grants more ITC per point.
* Access the administrator dashboard at `/admin` to review user progress and reward claims. Authentication uses HTTP Basic with the password set in `ADMIN_PASSWORD`.
* Referral analytics are available at `/analytics/leaderboard` and are also shown on the dashboard.

## Administrator Dashboard

Visit `/admin` while the server is running to view all registered users, their current point totals, completed task counts, referral totals and any reward claims. This dashboard provides a quick summary for manual payout processing and tracking progress.
Authentication uses HTTP Basic. Use username `admin` and the password set in `ADMIN_PASSWORD`.

## Referral Analytics

The `/analytics/leaderboard` endpoint returns a JSON list of users sorted by the number of successful referrals. This data is also displayed on the administrator dashboard so you can easily see who is bringing in the most new users.

## Future Features

The following planned objectives are now complete:

* Multi-language support with English, Spanish and French strings
* CAPTCHA verification on signup
* Administrator dashboard and referral analytics

Upcoming improvements include:

1. **Automatic Payouts** – send rewards directly once claims are approved.
2. **In-App Notifications** – alert users when referrals sign up or rewards are processed.
3. **Advanced Reporting** – let administrators download CSV reports for rewards and referrals.
4. **Mobile App** – provide a dedicated mobile interface.
5. **OAuth Logins** – allow users to sign in with social accounts.
