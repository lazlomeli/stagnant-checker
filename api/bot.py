import os
import re
import json
import redis
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_SIGN_SECRET = os.environ["SLACK_SIGN_SECRET"]
REDIS_URL = os.environ["REDIS_URL"]

# Initialize Redis with connection timeout
r = redis.Redis.from_url(
    REDIS_URL,
    socket_connect_timeout=5,
    socket_timeout=5,
    decode_responses=False
)

app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGN_SECRET)
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

DATA_KEY = "user_data"

# ---------- Storage Helpers ----------
def load_data():
    """Load user data from Redis with error handling."""
    try:
        data = r.get(DATA_KEY)
        return json.loads(data) if data else {}
    except Exception as e:
        print(f"Error loading data from Redis: {e}")
        return {}

def save_data(data):
    """Save user data to Redis."""
    r.set(DATA_KEY, json.dumps(data))

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
    text = command.get("text", "").strip()
    
    # Require # symbol
    if not text.startswith("#"):
        respond("Usage: `/watch #channel-name`\nPlease include the # symbol.")
        return
    
    # Remove # and convert to lowercase
    channel_name = text[1:].lower()
    
    if not channel_name:
        respond("Usage: `/watch #channel-name`")
        return
    
    # Validate channel name
    is_valid, error_msg = validate_channel_name(channel_name)
    if not is_valid:
        respond(f"❌ {error_msg}")
        return

    # Load, update, save
    data = load_data()
    user_data = data.get(user_id, {"channels": []})
    
    if channel_name in user_data["channels"]:
        respond(f"Channel *#{channel_name}* is already being monitored.")
    else:
        # Limit: 50 channels per user
        if len(user_data["channels"]) >= 50:
            respond("❌ You've reached the maximum of 50 monitored channels.")
            return
        
        user_data["channels"].append(channel_name)
        data[user_id] = user_data
        
        if not save_data(data):
            respond("❌ Error saving data. Please try again.")
            return
        
        respond(f"✅ Added *#{channel_name}* to your personal watchlist.")

@app.command("/unwatch")
def unwatch(ack, respond, command):
    ack()
    user_id = command["user_id"]
    text = command.get("text", "").strip()
    
    # Require # symbol
    if not text.startswith("#"):
        respond("Usage: `/unwatch #channel-name`\nPlease include the # symbol.")
        return
    
    # Remove # and convert to lowercase
    channel_name = text[1:].lower()
    
    if not channel_name:
        respond("Usage: `/unwatch #channel-name`")
        return
    
    # Validate channel name
    is_valid, error_msg = validate_channel_name(channel_name)
    if not is_valid:
        respond(f"❌ {error_msg}")
        return
    
    # Load, update, save
    data = load_data()
    user_data = data.get(user_id, {"channels": []})

    if channel_name not in user_data["channels"]:
        respond(f"Channel *#{channel_name}* is not in your watchlist.")
    else:
        user_data["channels"].remove(channel_name)
        data[user_id] = user_data
        
        if not save_data(data):
            respond("❌ Error saving data. Please try again.")
            return
        
        respond(f"🗑️ Removed *#{channel_name}* from your watchlist.")

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
