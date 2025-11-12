import os
import re
import json
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request

# Import Redis storage for Vercel
try:
    import redis
    REDIS_URL = os.environ.get("REDIS_URL")
    if REDIS_URL:
        r = redis.Redis.from_url(REDIS_URL)
        USE_REDIS = True
    else:
        USE_REDIS = False
except ImportError:
    USE_REDIS = False

# Fallback to file-based storage for local development
if not USE_REDIS:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from file_utils import load_json_with_lock, atomic_json_update

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_SIGN_SECRET = os.environ["SLACK_SIGN_SECRET"]

app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGN_SECRET)
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

DATA_KEY = "user_data"

# ---------- Storage Helpers ----------
def load_data():
    """Load user data from Redis or file."""
    if USE_REDIS:
        data = r.get(DATA_KEY)
        return json.loads(data) if data else {}
    else:
        return load_json_with_lock("user_data.json", {})

def save_data(data):
    """Save user data to Redis or file."""
    if USE_REDIS:
        r.set(DATA_KEY, json.dumps(data))
    else:
        def update(d):
            return data
        atomic_json_update("user_data.json", update, {})

def validate_channel_name(channel_name):
    """
    Validate and sanitize channel name according to Slack's naming rules.
    
    Args:
        channel_name: Channel name to validate
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not channel_name:
        return False, "Channel name cannot be empty"
    
    # Slack channel names: lowercase letters, numbers, hyphens, underscores
    # Maximum length is 80 characters
    if not re.match(r'^[a-z0-9\-_]{1,80}$', channel_name):
        return False, (
            "Invalid channel name. Channel names must:\n"
            "• Be 1-80 characters long\n"
            "• Only contain lowercase letters, numbers, hyphens, and underscores\n"
            "• Not contain spaces or special characters"
        )
    
    return True, None

# ---------- Commands ----------
@app.command("/watch")
def add_channel(ack, respond, command):
    ack()
    user_id = command["user_id"]
    text = command.get("text", "").strip().replace("#", "").lower()
    
    if not text:
        respond("Usage: `/watch #channel-name`")
        return
    
    # Validate channel name
    is_valid, error_msg = validate_channel_name(text)
    if not is_valid:
        respond(f"❌ {error_msg}")
        return

    # Load, update, save
    data = load_data()
    user_data = data.get(user_id, {"channels": []})
    
    if text in user_data["channels"]:
        respond(f"Channel *#{text}* is already being monitored.")
    else:
        user_data["channels"].append(text)
        data[user_id] = user_data
        save_data(data)
        respond(f"✅ Added *#{text}* to your personal watchlist.")

@app.command("/unwatch")
def unwatch(ack, respond, command):
    ack()
    user_id = command["user_id"]
    text = command.get("text", "").strip().replace("#", "").lower()
    
    if not text:
        respond("Usage: `/unwatch #channel-name`")
        return
    
    # Validate channel name
    is_valid, error_msg = validate_channel_name(text)
    if not is_valid:
        respond(f"❌ {error_msg}")
        return
    
    # Load, update, save
    data = load_data()
    user_data = data.get(user_id, {"channels": []})

    if text not in user_data["channels"]:
        respond(f"Channel *#{text}* is not in your watchlist.")
    else:
        user_data["channels"].remove(text)
        data[user_id] = user_data
        save_data(data)
        respond(f"🗑️ Removed *#{text}* from your watchlist.")

@app.command("/list")
def list_channels(ack, respond, command):
    ack()
    user_id = command["user_id"]
    data = load_data()
    user_data = data.get(user_id, {"channels": []})
    channels = user_data["channels"]

    if not channels:
        respond("You're not monitoring any channels yet.")
    else:
        channels_list = "\n".join(f"• #{c}" for c in channels)
        respond(f"👀 You're currently monitoring:\n{channels_list}")

# ---------- Flask routes for Vercel ----------
@flask_app.route("/watch", methods=["POST"])
def watch_route():
    return handler.handle(request)

@flask_app.route("/unwatch", methods=["POST"])
def unwatch_route():
    return handler.handle(request)

@flask_app.route("/list", methods=["POST"])
def list_route():
    return handler.handle(request)

# For Vercel serverless
app_handler = flask_app

# For local development
if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))

