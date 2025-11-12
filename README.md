# Stagnant Channel Monitor

A Slack bot that monitors channels for inactivity and sends daily notifications when channels haven't received replies in over 2 days.

## Features

- **Personal watchlists**: Each user maintains their own list of channels to monitor
- **Slash commands**: Easy channel management via `/watch`, `/unwatch`, and `/list`
- **Daily checks**: Automated cron job runs daily at 9 AM
- **DM notifications**: Users receive direct messages with stagnant channel reports
- **Thread-safe**: File locking prevents data corruption from concurrent access
- **API optimization**: Channel caching dramatically reduces Slack API calls
- **Input validation**: Robust channel name validation prevents invalid entries

## Setup

1. **Create a Slack App** with these permissions:
   - `commands`
   - `chat:write`
   - `channels:read`
   - `groups:read`
   - `channels:history`
   - `groups:history`

2. **Add Slash Commands**:
   - `/watch` - Add a channel to your watchlist
   - `/unwatch` - Remove a channel from your watchlist
   - `/list` - View your monitored channels

3. **Environment Variables**:
   ```
   SLACK_BOT_TOKEN=xoxb-your-bot-token
   SLACK_SIGN_SECRET=your-signing-secret
   PORT=3000
   ```

4. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

5. **Run**:
   ```bash
   python bot.py  
   python stagnant_checker.py
   ```

## Deployment

Configured for Render.com with:
- Web service for the bot server
- Cron job for daily checks (9 AM UTC)

See `render.yaml` for deployment configuration.

## Usage

```
/watch #general       → Add #general to your watchlist
/unwatch #general     → Remove #general from your watchlist
/list                 → See all channels you're monitoring
```

You'll receive a DM each day listing any stagnant channels (no replies in 2+ days).

## Technical Enhancements

### File Locking (Race Condition Prevention)
The application uses `fcntl` file locking to prevent race conditions when multiple processes read/write JSON files simultaneously. This ensures data integrity when:
- Multiple users add/remove channels concurrently
- The bot processes commands while the checker script runs

### API Rate Limit Optimization
Implements intelligent channel caching to minimize Slack API calls:
- **Cache Duration**: 24 hours
- **Cache File**: `channel_cache.json`
- **Performance**: Reduces API calls from O(users × channels) to O(1) for cached channels
- **Example**: With 50 users watching 10 channels each, the system goes from 500+ API calls to just 1 per day

The cache automatically refreshes when:
- It expires (after 24 hours)
- A channel is not found in the cache
- The script runs for the first time

### Input Validation
Channel names are validated against Slack's naming rules:
- Only lowercase letters, numbers, hyphens, and underscores
- Maximum length of 80 characters
- Prevents injection attacks and invalid API calls

