import os, json
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv

load_dotenv()

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]  # xapp- token for socket mode

app = App(token=SLACK_BOT_TOKEN)

CHANNELS_FILE = "watched_channels.json"

def load_channels():
    if not os.path.exists(CHANNELS_FILE):
        return {"channels": []}
    with open(CHANNELS_FILE, "r") as f:
        return json.load(f)

def save_channels(data):
    with open(CHANNELS_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.command("/watchchannel")
def add_channel(ack, respond, command):
    ack()
    text = command.get("text", "").strip().replace("#", "")
    if not text:
        respond("Usage: `/watchchannel #channel-name`")
        return
    data = load_channels()
    if text in data["channels"]:
        respond(f"Channel *#{text}* is already being monitored.")
    else:
        data["channels"].append(text)
        save_channels(data)
        respond(f"✅ Added *#{text}* to watchlist.")

@app.command("/unwatchchannel")
def remove_channel(ack, respond, command):
    ack()
    text = command.get("text", "").strip().replace("#", "")
    data = load_channels()
    if text not in data["channels"]:
        respond(f"Channel *#{text}* is not being monitored.")
    else:
        data["channels"].remove(text)
        save_channels(data)
        respond(f"🗑️ Removed *#{text}* from watchlist.")

@app.command("/listchannels")
def list_channels(ack, respond):
    ack()
    data = load_channels()
    if not data["channels"]:
        respond("No channels are being monitored.")
    else:
        channels_list = "\n".join(f"• #{c}" for c in data["channels"])
        respond(f"Currently monitored channels:\n{channels_list}")

if __name__ == "__main__":
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
