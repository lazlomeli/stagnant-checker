import os
import json
import redis
from slack_bolt import App
from slack_bolt.adapter.aws_lambda import SlackRequestHandler

print("Loading list.py module...", flush=True)

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
    process_before_response=True
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

@app.command("/list")
def handle_list(ack, respond, command):
    try:
        print(f"List command received from user {command['user_id']}", flush=True)
        ack()
        
        user_id = command["user_id"]
        
        # Load data
        data = load_data()
        user_data = data.get(user_id, {"channels": []})
        channels = user_data["channels"]
        
        if not channels:
            respond("You're not monitoring any channels yet.")
        else:
            channels_list = "\n".join(f"• #{c}" for c in channels)
            respond(f"👀 You're currently monitoring:\n{channels_list}")
            print(f"User {user_id} has {len(channels)} channels", flush=True)
    
    except Exception as e:
        print(f"Error in list command: {e}", flush=True)
        respond(f"❌ An error occurred: {str(e)}")

# Vercel serverless handler
handler = SlackRequestHandler(app)

def handle(request):
    """Main handler for Vercel"""
    print("List handler called", flush=True)
    return handler.handle(request)

