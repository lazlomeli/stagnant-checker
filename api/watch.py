import os
import json
import redis
from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler

# Print for debugging
print("Loading watch.py module...", flush=True)

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
except Exception as e:
    print(f"Redis connection error: {e}", flush=True)
    r = None

# Initialize Slack App
app = App(
    token=SLACK_BOT_TOKEN,
    signing_secret=SLACK_SIGN_SECRET,
    process_before_response=True  # Important for serverless
)

DATA_KEY = "user_data"

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

@app.command("/watch")
def handle_watch(ack, respond, command):
    try:
        print(f"Watch command received from user {command['user_id']}", flush=True)
        ack()
        
        user_id = command["user_id"]
        text = command.get("text", "").strip()
        
        # Validate input
        if not text.startswith("#"):
            respond("Usage: `/watch #channel-name`\nPlease include the # symbol.")
            return
        
        channel_name = text[1:].lower()
        
        if not channel_name:
            respond("Usage: `/watch #channel-name`")
            return
        
        # Load and update data
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
            print(f"Successfully added {channel_name} for user {user_id}", flush=True)
    
    except Exception as e:
        print(f"Error in watch command: {e}", flush=True)
        respond(f"❌ An error occurred: {str(e)}")

# Vercel serverless handler
handler = SlackRequestHandler(app)

def handle(request):
    """Main handler for Vercel"""
    print("Watch handler called", flush=True)
    return handler.handle(request)

