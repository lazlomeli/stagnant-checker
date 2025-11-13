import os
import re
import json
import logging
import traceback
import redis
from slack_bolt import App

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DATA_KEY = "user_data"


def get_redis():
    url = os.environ.get("REDIS_URL")
    if not url:
        logger.warning("REDIS_URL missing")
        return None

    try:
        r = redis.Redis.from_url(
            url,
            socket_connect_timeout=5,
            socket_timeout=5,
            decode_responses=False,
        )
        r.ping()
        return r
    except Exception as e:
        logger.error(f"Redis error: {e}")
        return None


def validate_channel_name(name):
    if not name:
        return False, "Channel name cannot be empty"
    if not re.match(r"^[a-z0-9\-_]{1,80}$", name):
        return False, (
            "Invalid channel name. Channel names must:\n"
            "• Be 1-80 characters long\n"
            "• Only contain lowercase letters, numbers, hyphens, and underscores"
        )
    return True, None


def register_commands(app, r):
    @app.command("/watch")
    def watch_cmd(ack, respond, command):
        ack()
        user_id = command["user_id"]
        text = command.get("text", "").strip()

        if not text.startswith("#"):
            respond("Usage: /watch #channel")
            return

        channel = text[1:].lower()
        ok, msg = validate_channel_name(channel)

        if not ok:
            respond(f"❌ {msg}")
            return

        data = load_data(r)
        user = data.get(user_id, {"channels": []})

        if channel in user["channels"]:
            respond(f"Already watching #{channel}")
            return

        user["channels"].append(channel)
        data[user_id] = user

        if not save_data(r, data):
            respond("Redis error")
            return

        respond(f"Watching #{channel}")

    @app.command("/unwatch")
    def unwatch_cmd(ack, respond, command):
        ack()
        user_id = command["user_id"]
        text = command.get("text", "").strip()

        if not text.startswith("#"):
            respond("Usage: /unwatch #channel")
            return

        channel = text[1:].lower()

        data = load_data(r)
        user = data.get(user_id, {"channels": []})

        if channel not in user["channels"]:
            respond(f"#{channel} is not watched")
            return

        user["channels"].remove(channel)
        data[user_id] = user

        if not save_data(r, data):
            respond("Redis error")
            return

        respond(f"Unwatched #{channel}")

    @app.command("/list")
    def list_cmd(ack, respond, command):
        ack()
        user_id = command["user_id"]

        data = load_data(r)
        user = data.get(user_id, {"channels": []})

        if not user["channels"]:
            respond("No watched channels")
            return

        items = "\n".join(f"• #{c}" for c in user["channels"])
        respond(f"Watched channels:\n{items}")


def load_data(r):
    raw = r.get(DATA_KEY)
    return json.loads(raw) if raw else {}


def save_data(r, data):
    try:
        r.set(DATA_KEY, json.dumps(data))
        return True
    except:
        return False


def create_bolt_handler():
    """Factory for Vercel serverless calls."""
    logger.info("Initializing Bolt App")

    app = App(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        signing_secret=os.environ.get("SLACK_SIGN_SECRET"),
    )

    r = get_redis()
    register_commands(app, r)

    from slack_bolt.adapter.flask import SlackRequestHandler
    return SlackRequestHandler(app)
