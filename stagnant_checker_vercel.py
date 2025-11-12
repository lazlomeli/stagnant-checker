import os
import json
from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

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

# Fallback to file-based storage
if not USE_REDIS:
    from file_utils import (
        load_json_with_lock,
        load_channel_cache,
        is_cache_valid,
        refresh_full_cache,
        update_channel_cache
    )

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
client = WebClient(token=SLACK_BOT_TOKEN)

DATA_KEY = "user_data"
CACHE_KEY = "channel_cache"

# ---------- Storage Helpers ----------
def load_data():
    """Load user data from Redis or file."""
    if USE_REDIS:
        data = r.get(DATA_KEY)
        return json.loads(data) if data else {}
    else:
        return load_json_with_lock("user_data.json", {})

def load_cache():
    """Load channel cache from Redis or file."""
    if USE_REDIS:
        cache = r.get(CACHE_KEY)
        return json.loads(cache) if cache else {"channels": {}, "last_updated": None}
    else:
        return load_channel_cache()

def save_cache(cache_data):
    """Save channel cache to Redis or file."""
    if USE_REDIS:
        r.set(CACHE_KEY, json.dumps(cache_data))
    else:
        from file_utils import save_channel_cache
        save_channel_cache(cache_data)

def is_cache_valid_redis(cache_data):
    """Check if cache is valid."""
    if not cache_data.get("last_updated"):
        return False
    
    last_updated = datetime.fromisoformat(cache_data["last_updated"])
    expiry_time = datetime.now() - timedelta(hours=24)
    
    return last_updated > expiry_time

def refresh_cache_redis():
    """Refresh the entire channel cache."""
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
    """Get channel ID with caching."""
    cache = load_cache()
    
    # Check if cache is valid
    if USE_REDIS:
        valid = is_cache_valid_redis(cache)
    else:
        valid = is_cache_valid(cache)
    
    if valid:
        channel_id = cache["channels"].get(channel_name)
        if channel_id:
            return channel_id
        print(f"Channel '{channel_name}' not in cache, attempting single lookup...")
    else:
        print("Cache expired or invalid, refreshing channel cache...")
        if USE_REDIS:
            channel_mapping = refresh_cache_redis()
        else:
            channel_mapping = refresh_full_cache(client)
        
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
                    # Update cache
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
    try:
        result = client.conversations_history(channel=channel_id, limit=1)
        if result["messages"]:
            return result["messages"][0]
    except SlackApiError as e:
        print(f"Error fetching messages from {channel_id}: {e}")
    return None

def message_is_stagnant(message):
    ts = float(message["ts"])
    msg_time = datetime.fromtimestamp(ts)
    two_days_ago = datetime.now() - timedelta(days=2)
    has_replies = message.get("reply_count", 0) > 0
    return msg_time < two_days_ago and not has_replies

def notify_user(user_id, report):
    try:
        client.chat_postMessage(channel=user_id, text=report)
    except SlackApiError as e:
        print(f"Error sending message to {user_id}: {e}")

# ---------- Main ----------
def run_check():
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

