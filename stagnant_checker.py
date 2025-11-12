import os, json
from datetime import datetime, timedelta
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from dotenv import load_dotenv

load_dotenv()

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
NOTIFY_USER = "U123ABCDE"

client = WebClient(token=SLACK_BOT_TOKEN)

def load_channels():
    if not os.path.exists("watched_channels.json"):
        return []
    with open("watched_channels.json", "r") as f:
        return json.load(f)["channels"]

def get_channel_id(channel_name):
    try:
        result = client.conversations_list(types="public_channel,private_channel")
        for c in result["channels"]:
            if c["name"] == channel_name:
                return c["id"]
    except SlackApiError as e:
        print(f"Error fetching channels: {e}")
    return None

def get_latest_message(channel_id):
    try:
        result = client.conversations_history(channel=channel_id, limit=1)
        if result["messages"]:
            return result["messages"][0]
    except SlackApiError as e:
        print(f"Error fetching messages: {e}")
    return None

def message_is_stagnant(message):
    ts = float(message["ts"])
    msg_time = datetime.fromtimestamp(ts)
    two_days_ago = datetime.now() - timedelta(days=2)
    has_replies = "reply_count" in message and message["reply_count"] > 0
    return msg_time < two_days_ago and not has_replies

def notify_user(report):
    try:
        client.chat_postMessage(channel=NOTIFY_USER, text=report)
    except SlackApiError as e:
        print(f"Error sending report: {e}")

def run_check():
    channels = load_channels()
    stagnant = []
    for ch in channels:
        cid = get_channel_id(ch)
        if not cid:
            continue
        msg = get_latest_message(cid)
        if msg and message_is_stagnant(msg):
            stagnant.append(ch)
    if stagnant:
        notify_user("⚠️ Stagnant channels:\n" + "\n".join(f"• #{c}" for c in stagnant))
    else:
        notify_user("✅ All monitored channels are active.")

if __name__ == "__main__":
    run_check()
