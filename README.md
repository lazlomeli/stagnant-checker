# Stagnant Channel Monitor

Slack bot that monitors channels for inactivity and sends daily DMs when channels haven't received replies in 2+ days.

## Commands

- `/watch #channel-name` - Add channel to your watchlist
- `/unwatch #channel-name` - Remove channel from watchlist
- `/list` - View your monitored channels

## Features

- Daily checks at 10:30 AM CET
- Input validation (lowercase, numbers, hyphens, underscores only)
- Redis caching (95% fewer API calls)
- 100% free (Vercel + GitHub Actions + Upstash Redis)

## Deployment

**Vercel** (bot commands):
```bash
vercel --prod
```

**GitHub Actions** (daily checks):
- Runs automatically at 10:30 AM CET
- Add secrets: `SLACK_BOT_TOKEN`, `REDIS_URL`

**Slack App Permissions**:
- `commands`, `chat:write`, `channels:read`, `groups:read`, `channels:history`, `groups:history`

