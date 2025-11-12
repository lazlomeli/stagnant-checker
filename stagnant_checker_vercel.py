import os
import json
import redis
from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
REDIS_URL = os.environ["REDIS_URL"]

# Initialize Redis and Slack client
r = redis.Redis.from_url(REDIS_URL)
client = WebClient(token=SLACK_BOT_TOKEN)

DATA_KEY = "user_data"
CACHE_KEY = "channel_cache"

# ---------- Storage Helpers ----------
def load_data():
    """Load user data from Redis."""
    data = r.get(DATA_KEY)
    return json.loads(data) if data else {}

def load_cache():
    """Load channel cache from Redis."""
    cache = r.get(CACHE_KEY)
    return json.loads(cache) if cache else {"channels": {}, "last_updated": None}

def save_cache(cache_data):
    """Save channel cache to Redis."""
    r.set(CACHE_KEY, json.dumps(cache_data))

def is_cache_valid(cache_data):
    """Check if cache is valid (not expired)."""
    if not cache_data.get("last_updated"):
        return False
    
    last_updated = datetime.fromisoformat(cache_data["last_updated"])
    expiry_time = datetime.now() - timedelta(hours=24)
    
    return last_updated > expiry_time

def refresh_cache():
    """Refresh the entire channel cache from Slack API."""
    channel_mapping = {}
    
    try:
        cursor = None
        while True:
            result = client.conversations_list(
                types="public_channel,private_channel",
                limit=1000,
                cursor=cursor
            )
            
            for c in result["channels"]:
                channel_mapping[c["name"]] = c["id"]
            
            cursor = result.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
    except SlackApiError as e:
        print(f"Error refreshing channel cache: {e}")
        return None
    
    cache_data = {
        "channels": channel_mapping,
        "last_updated": datetime.now().isoformat()
    }
    save_cache(cache_data)
    
    return channel_mapping

# ---------- Helpers ----------
def get_channel_id(channel_name):
    """Get channel ID with caching to reduce API calls."""
    cache = load_cache()
    
    # Check if cache is valid
    if is_cache_valid(cache):
        channel_id = cache["channels"].get(channel_name)
        if channel_id:
            return channel_id
        print(f"Channel '{channel_name}' not in cache, attempting single lookup...")
    else:
        # Cache expired, refresh it
        print("Cache expired or invalid, refreshing channel cache...")
        channel_mapping = refresh_cache()
        if channel_mapping:
            return channel_mapping.get(channel_name)
        return None
    
    # Single lookup for missing channel
    try:
        cursor = None
        while True:
            result = client.conversations_list(
                types="public_channel,private_channel",
                limit=1000,
                cursor=cursor
            )
            for c in result["channels"]:
                if c["name"] == channel_name:
                    # Update cache with this new channel
                    cache["channels"][channel_name] = c["id"]
                    save_cache(cache)
                    return c["id"]
            
            cursor = result.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
    except SlackApiError as e:
        print(f"Error fetching channel '{channel_name}': {e}")
    
    return None

def get_latest_message(channel_id):
    """Get the most recent message from a channel."""
    try:
        result = client.conversations_history(channel=channel_id, limit=1)
        if result["messages"]:
            return result["messages"][0]
    except SlackApiError as e:
        print(f"Error fetching messages from {channel_id}: {e}")
    return None

def message_is_stagnant(message):
    """Check if a message is stagnant (>2 days old with no replies)."""
    ts = float(message["ts"])
    msg_time = datetime.fromtimestamp(ts)
    two_days_ago = datetime.now() - timedelta(days=2)
    has_replies = message.get("reply_count", 0) > 0
    return msg_time < two_days_ago and not has_replies

def notify_user(user_id, report):
    """Send a DM to a user with the stagnant channel report."""
    try:
        client.chat_postMessage(channel=user_id, text=report)
    except SlackApiError as e:
        print(f"Error sending message to {user_id}: {e}")

# ---------- Main ----------
def run_check():
    """Main function to check all users' watched channels for stagnation."""
    print("Running stagnant channel check...")
    data = load_data()
    if not data:
        print("No users configured.")
        return

    for user_id, info in data.items():
        channels = info.get("channels", [])
        if not channels:
            continue

        stagnant = []
        for ch in channels:
            cid = get_channel_id(ch)
            if not cid:
                continue
            msg = get_latest_message(cid)
            if msg and message_is_stagnant(msg):
                stagnant.append(ch)

        if stagnant:
            report = "⚠️ *Your stagnant channels:*\n" + "\n".join(f"• #{c}" for c in stagnant)
        else:
            report = "✅ All your monitored channels are active."

        notify_user(user_id, report)

    print("Done.")

if __name__ == "__main__":
    run_check()
