import os
import json
import redis
from flask import Flask, request
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler

print("Loading index.py (main handler)...", flush=True)

# Environment variables
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_SIGN_SECRET = os.environ.get("SLACK_SIGN_SECRET", "")
REDIS_URL = os.environ.get("REDIS_URL", "")

# Initialize Redis
try:
    r = redis.Redis.from_url(
        REDIS_URL,
        socket_connect_timeout=5,
        socket_timeout=5,
        decode_responses=False
    ) if REDIS_URL else None
    print(f"✓ Redis initialized: {r is not None}", flush=True)
except Exception as e:
    print(f"✗ Redis connection error: {e}", flush=True)
    r = None

# Initialize Slack App
slack_app = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGN_SECRET,
    process_before_response=True
)
print("✓ Slack app initialized", flush=True)

DATA_KEY = "user_data"

# ---------- Data Functions ----------
def load_data():
    """Load user data from Redis."""
    try:
        if not r:
            return {}
        data = r.get(DATA_KEY)
        return json.loads(data) if data else {}
    except Exception as e:
        print(f"Error loading data: {e}", flush=True)
        return {}

def save_data(data):
    """Save user data to Redis."""
    try:
        if not r:
            return False
        r.set(DATA_KEY, json.dumps(data))
        return True
    except Exception as e:
        print(f"Error saving data: {e}", flush=True)
        return False

# ---------- Slash Commands ----------
@slack_app.command("/watch")
def handle_watch(ack, respond, command):
    try:
        print(f"✓ /watch from user {command['user_id']}", flush=True)
        ack()
        
        user_id = command["user_id"]
        text = command.get("text", "").strip()
        
        if not text.startswith("#"):
            respond("Usage: `/watch #channel-name`\nPlease include the # symbol.")
            return
        
        channel_name = text[1:].lower()
        if not channel_name:
            respond("Usage: `/watch #channel-name`")
            return
        
        data = load_data()
        user_data = data.get(user_id, {"channels": []})
        
        if channel_name in user_data["channels"]:
            respond(f"Channel *#{channel_name}* is already being monitored.")
        else:
            if len(user_data["channels"]) >= 50:
                respond("❌ You've reached the maximum of 50 monitored channels.")
                return
            
            user_data["channels"].append(channel_name)
            data[user_id] = user_data
            
            if not save_data(data):
                respond("❌ Error saving data. Please try again.")
                return
            
            respond(f"✅ Added *#{channel_name}* to your personal watchlist.")
            print(f"✓ Added {channel_name} for {user_id}", flush=True)
    except Exception as e:
        print(f"✗ Error in /watch: {e}", flush=True)
        respond(f"❌ An error occurred: {str(e)}")

@slack_app.command("/unwatch")
def handle_unwatch(ack, respond, command):
    try:
        print(f"✓ /unwatch from user {command['user_id']}", flush=True)
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
            print(f"✓ Removed {channel_name} for {user_id}", flush=True)
    except Exception as e:
        print(f"✗ Error in /unwatch: {e}", flush=True)
        respond(f"❌ An error occurred: {str(e)}")

@slack_app.command("/list")
def handle_list(ack, respond, command):
    try:
        print(f"✓ /list from user {command['user_id']}", flush=True)
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
            print(f"✓ Listed {len(channels)} channels for {user_id}", flush=True)
    except Exception as e:
        print(f"✗ Error in /list: {e}", flush=True)
        respond(f"❌ An error occurred: {str(e)}")

# ---------- Flask App ----------
app = Flask(__name__)
handler = SlackRequestHandler(slack_app)

@app.route("/", methods=["GET"])
def health():
    return {"status": "ok", "redis": r is not None}, 200

@app.route("/watch", methods=["POST"])
@app.route("/unwatch", methods=["POST"])
@app.route("/list", methods=["POST"])
def slack_events():
    print(f"✓ Slack request received: {request.path}", flush=True)
    return handler.handle(request)

print("✓ Index module loaded successfully", flush=True)

