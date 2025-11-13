# slack_bot.py
import os
import re
import json
import logging
import traceback

import redis
from slack_bolt import App

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
logger.info("Loading slack_bot.py")

# ---------- Environment ----------
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_SIGN_SECRET = os.environ.get("SLACK_SIGN_SECRET", "")
REDIS_URL = os.environ.get("REDIS_URL", "")

logger.info(
    "Env loaded | SLACK_BOT_TOKEN: %s | SLACK_SIGN_SECRET: %s | REDIS_URL: %s",
    "✓" if SLACK_BOT_TOKEN else "✗",
    "✓" if SLACK_SIGN_SECRET else "✗",
    "✓" if REDIS_URL else "✗",
)

if not SLACK_BOT_TOKEN or not SLACK_SIGN_SECRET:
    logger.error("Slack tokens missing – set SLACK_BOT_TOKEN and SLACK_SIGN_SECRET")

# ---------- Redis ----------
DATA_KEY = "user_data"
r = None

if REDIS_URL:
    try:
        logger.info("Initializing Redis...")
        r = redis.Redis.from_url(
            REDIS_URL,
            socket_connect_timeout=5,
            socket_timeout=5,
            decode_responses=False,
        )
        # Test connection
        r.ping()
        logger.info("Connected to Redis successfully")
    except Exception as e:
        logger.error("Redis connection error: %s", e)
        logger.debug(traceback.format_exc())
        r = None
else:
    logger.warning("REDIS_URL not set – Redis is disabled")

# ---------- Storage Helpers ----------
def load_data():
    """Load user data from Redis with error handling."""
    if not r:
        logger.error("Cannot load data: Redis connection is not available")
        return {}

    try:
        raw = r.get(DATA_KEY)
        data = json.loads(raw) if raw else {}
        logger.debug("Data loaded. Users: %d", len(data))
        return data
    except Exception as e:
        logger.error("Error loading data from Redis: %s", e)
        logger.debug(traceback.format_exc())
        return {}


def save_data(data):
    """Save user data to Redis."""
    if not r:
        logger.error("Cannot save data: Redis connection is not available")
        return False

    try:
        r.set(DATA_KEY, json.dumps(data))
        logger.debug("Data saved. Users: %d", len(data))
        return True
    except Exception as e:
        logger.error("Error saving data to Redis: %s", e)
        logger.debug(traceback.format_exc())
        return False


def validate_channel_name(channel_name):
    """
    Validate and sanitize channel name according to Slack's naming rules.
    Returns (is_valid, error_message_or_None)
    """
    if not channel_name:
        return False, "Channel name cannot be empty"

    # Slack channel rules: lowercase letters, numbers, hyphens, underscores, max 80 chars
    if not re.match(r"^[a-z0-9\-_]{1,80}$", channel_name):
        return False, (
            "Invalid channel name. Channel names must:\n"
            "• Be 1-80 characters long\n"
            "• Only contain lowercase letters, numbers, hyphens, and underscores\n"
            "• Not contain spaces or special characters"
        )

    return True, None


# ---------- Slack Bolt App ----------
# Provide dummy values if not set to prevent init errors
bolt_app = App(
    token=SLACK_BOT_TOKEN or "xoxb-dummy",
    signing_secret=SLACK_SIGN_SECRET or "dummy-secret",
)

if not (SLACK_BOT_TOKEN and SLACK_SIGN_SECRET):
    logger.warning("Slack App initialized with dummy credentials – will fail in production")

logger.info("Registering Slack commands...")


@bolt_app.command("/watch")
def cmd_watch(ack, respond, command):
    try:
        logger.info("=== /watch command ===")
        logger.info("Payload: %s", json.dumps(command, default=str))

        ack()  # acknowledge quickly

        user_id = command["user_id"]
        text = command.get("text", "").strip()

        if not text.startswith("#"):
            respond("Usage: `/watch #channel-name`\nPlease include the # symbol.")
            return

        channel_name = text[1:].lower()

        if not channel_name:
            respond("Usage: `/watch #channel-name`")
            return

        is_valid, error_msg = validate_channel_name(channel_name)
        if not is_valid:
            respond(f"❌ {error_msg}")
            return

        data = load_data()
        user_data = data.get(user_id, {"channels": []})

        if channel_name in user_data["channels"]:
            respond(f"Channel *#{channel_name}* is already being monitored.")
            return

        if len(user_data["channels"]) >= 50:
            respond("❌ You've reached the maximum of 50 monitored channels.")
            return

        user_data["channels"].append(channel_name)
        data[user_id] = user_data

        if not save_data(data):
            respond("❌ Error saving data. Please try again.")
            return

        respond(f"✅ Added *#{channel_name}* to your personal watchlist.")
    except Exception as e:
        logger.error("Error in /watch: %s", e)
        logger.error(traceback.format_exc())
        respond(
            "❌ An unexpected error occurred. Please try again or contact support.\n"
            f"Error: {e}"
        )


@bolt_app.command("/unwatch")
def cmd_unwatch(ack, respond, command):
    try:
        logger.info("=== /unwatch command ===")
        logger.info("Payload: %s", json.dumps(command, default=str))

        ack()

        user_id = command["user_id"]
        text = command.get("text", "").strip()

        if not text.startswith("#"):
            respond("Usage: `/unwatch #channel-name`\nPlease include the # symbol.")
            return

        channel_name = text[1:].lower()

        if not channel_name:
            respond("Usage: `/unwatch #channel-name`")
            return

        is_valid, error_msg = validate_channel_name(channel_name)
        if not is_valid:
            respond(f"❌ {error_msg}")
            return

        data = load_data()
        user_data = data.get(user_id, {"channels": []})

        if channel_name not in user_data["channels"]:
            respond(f"Channel *#{channel_name}* is not in your watchlist.")
            return

        user_data["channels"].remove(channel_name)
        data[user_id] = user_data

        if not save_data(data):
            respond("❌ Error saving data. Please try again.")
            return

        respond(f"🗑️ Removed *#{channel_name}* from your watchlist.")
    except Exception as e:
        logger.error("Error in /unwatch: %s", e)
        logger.error(traceback.format_exc())
        respond(
            "❌ An unexpected error occurred. Please try again or contact support.\n"
            f"Error: {e}"
        )


@bolt_app.command("/list")
def cmd_list(ack, respond, command):
    try:
        logger.info("=== /list command ===")
        logger.info("Payload: %s", json.dumps(command, default=str))

        ack()

        user_id = command["user_id"]

        data = load_data()
        user_data = data.get(user_id, {"channels": []})
        channels = user_data["channels"]

        if not channels:
            respond("You're not monitoring any channels yet.")
            return

        channels_list = "\n".join(f"• #{c}" for c in channels)
        respond(f"👀 You're currently monitoring:\n{channels_list}")
    except Exception as e:
        logger.error("Error in /list: %s", e)
        logger.error(traceback.format_exc())
        respond(
            "❌ An unexpected error occurred. Please try again or contact support.\n"
            f"Error: {e}"
        )


logger.info("Slack commands registered and bolt_app ready")

