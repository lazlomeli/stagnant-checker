import os, json
from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

load_dotenv()
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
client = WebClient(token=SLACK_BOT_TOKEN)

DATA_FILE = "user_data.json"

# ---------- Helpers ----------
def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def get_channel_id(channel_name):
    try:
        cursor = None
        while True:
            result = client.conversations_list(types="public_channel,private_channel", limit=1000, cursor=cursor)
            for c in result["channels"]:
                if c["name"] == channel_name:
                    return c["id"]
            cursor = result.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
    except SlackApiError as e:
        print(f"Error fetching channels: {e}")
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
