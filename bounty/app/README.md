# Bounty Referral App

This application tracks user referral tasks using FastAPI with a MySQL backend.

## Setup

1. Install requirements
   ```bash
   pip install -r requirements.txt
   ```
2. Configure `DATABASE_URL` in `database.py` and set any API tokens (Telegram, X, Discord, Reddit) as environment variables.
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
- `POST /login` - verify credentials and return the user id
- `POST /tasks/{user_id}` - verify completion of a task and award points
- `GET /progress/{user_id}` - retrieve the user's points and completed tasks
- `GET /admin` - view the administrator dashboard (HTML)
- `GET /analytics/leaderboard` - referral leaderboard in JSON format
- `POST /payout_address` - save the ITC wallet address for payouts
- `POST /process_claim/{claim_id}` - send a manual payment using `interchained-cli`

## Submission Guidelines

1. Create an account from the `/register` page or by calling `/users` directly. Provide a unique
   `username`, `password`, `email`, plus your Telegram, Twitter, Discord and Reddit handles.
   Include the `captcha_token` returned by your CAPTCHA widget. You may also supply an optional
   `referral_code`. If you arrive at `/register?ref=123` the `123` value is used as the referrer
   ID automatically. Otherwise you can fill in the **Referral ID** field on the form. Each IP may
   register only once and duplicate emails are rejected.
2. Use the provided user ID when submitting task completion via `/tasks/{user_id}`.
3. Tasks correspond to actions such as following social profiles or registering a wallet. Each successful verification grants points.
4. Points can be exchanged for rewards once the configured threshold is met. The logic for rewards can be customised in `main.py`.
5. Submit your payout wallet address via the `/payout_address` endpoint so administrators know where to send rewards.

## Usage Guidelines

* **Run locally** – execute `uvicorn main:app --reload` after installing dependencies. Visit `http://localhost:8000` to use the simple HTML frontend. Use `/register` to create an account and `/login` to authenticate.
* **Environment variables** – provide API tokens for Telegram, X (Twitter), Discord and Reddit. Set `DATABASE_URL` to your MySQL instance.
* **Wallet and newsletter** – register web or mobile wallets via the `/wallets` endpoint, provide a payout address through `/payout_address`, and sign up to the mailing list with `/newsletter`.
* **Authentication** – supply your username and password using HTTP Basic when calling user-specific endpoints such as `/tasks/{user_id}`, `/payout_address`, `/claim/{user_id}` and `/progress/{user_id}`.
* **Languages** – set `DEFAULT_LANGUAGE` to control which translation is shown by default. Supported codes are `en`, `es` and `fr`. Users may specify `/?lang=es` or another code to view the interface in that language.

## Social Links

The homepage shows links for each task so users know which profiles to follow or posts to share. These URLs are loaded from environment variables. Set them before running the app:

```
TELEGRAM_URL       # Link to your Telegram group or channel
X_PROFILE_URL      # Link to your X/Twitter profile to follow
DISCORD_URL        # Discord invite link
WEB_WALLET_URL     # Registration page for the web wallet
MOBILE_WALLET_URL  # Registration page for the mobile wallet
NEWSLETTER_URL     # Sign‑up page for the newsletter
REDDIT_URL         # Subreddit or profile to follow
TWEET_URL          # URL of the tweet users should share
WEBSITE_URL        # Main project website
WHITEPAPER_URL     # Link to the whitepaper
REFERRAL_BASE_URL  # Base URL used when displaying the referral link
REWARD_THRESHOLD   # Minimum points needed to claim rewards
ITC_PER_POINT      # Amount of ITC paid out per point when claiming
INTERCHAINED_CLI   # Path to the `interchained-cli` executable used for payouts
DEFAULT_LANGUAGE   # Default language code for the interface (e.g. 'en')
CAPTCHA_SECRET     # Secret token for verifying CAPTCHA responses
ADMIN_PASSWORD     # Password required to access the /admin dashboard
SERVER_PORT        # Port the FastAPI server runs on
NOCAPTCHA          # Set to 'true' to bypass CAPTCHA verification
TELEGRAM_BOT_TOKEN # Token for the bot used to check Telegram membership
TELEGRAM_GROUP_ID  # Numeric ID of the Telegram group to verify
```
To obtain your Telegram group ID, invite the `@userinfobot` (or a similar bot)
to your group and send `/start`. The bot will reply with the numeric
`chat_id`, which is the value to use for `TELEGRAM_GROUP_ID`.
Usernames submitted by participants are converted to their numeric ID using
Telegram's `getChat` (also known as `resolveUsername`) before checking
membership with `getChatMember`. Handles may be supplied with or without the
`@` prefix.

### Example Environment Setup

Configure the following variables before running the server:

```bash
export DATABASE_URL="mysql+pymysql://user:password@localhost:3306/referral_db"
export TELEGRAM_URL="https://t.me/examplegroup"
export X_PROFILE_URL="https://twitter.com/example"
export DISCORD_URL="https://discord.gg/example"
export WEB_WALLET_URL="https://wallet.example.com/register"
export MOBILE_WALLET_URL="https://mwallet.example.com/signup"
export NEWSLETTER_URL="https://example.com/newsletter"
export REDDIT_URL="https://reddit.com/r/example"
export TWEET_URL="https://twitter.com/example/status/1"
export WEBSITE_URL="https://example.com"
export WHITEPAPER_URL="https://example.com/whitepaper.pdf"
export REFERRAL_BASE_URL="https://bounty.example.com/"
export REWARD_THRESHOLD="100"
export ITC_PER_POINT="0.01"
export INTERCHAINED_CLI="/usr/local/bin/interchained-cli"
export DEFAULT_LANGUAGE="en"
export CAPTCHA_SECRET="recaptcha-secret"
export ADMIN_PASSWORD="changeme"
export TELEGRAM_BOT_TOKEN="123456:ABCDEF"
export TELEGRAM_GROUP_ID="-1009876543210"
export X_BEARER_TOKEN="x-api-bearer"
export X_ACCOUNT_ID="123456789"
export DISCORD_BOT_TOKEN="discord-bot-token"
export DISCORD_GUILD_ID="123456789012345678"
export REDDIT_TOKEN="reddit-token"
export REDDIT_SUBREDDIT="example"
export X_HASHTAG="ExampleTag"
```

## Claiming Rewards

Users accumulate raw points for completing tasks. Every successful referral
increases their reward multiplier by **1%**. The multiplier is applied when a
user claims their reward rather than at the moment tasks are completed. Once a
user reaches `REWARD_THRESHOLD` base points they may issue a `POST` request to
`/claim/{user_id}` or click the **Claim Reward** button on the homepage. The
server records the claim and resets the user’s point balance. The final amount of
Interchained (ITC) awarded is calculated using `ITC_PER_POINT` and the referral
multiplier:

```
reward_itc = points * (1 + 0.01 * referrals) * ITC_PER_POINT
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
6. **Referral Leaderboard on Homepage** – highlight top referrers to drive friendly competition.
7. **Reward Tiers** – unlock special perks based on points earned.
8. **Gamified Badges** – award badges for completing sets of tasks and milestones.
