import os, json
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_SIGN_SECRET = os.environ["SLACK_SIGN_SECRET"]

app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGN_SECRET)
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

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

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ---------- Commands ----------
@app.command("/watch")
def add_channel(ack, respond, command):
    ack()
    user_id = command["user_id"]
    text = command.get("text", "").strip().replace("#", "")
    if not text:
        respond("Usage: `/watch #channel-name`")
        return

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
    text = command.get("text", "").strip().replace("#", "")
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
        respond("You’re not monitoring any channels yet.")
    else:
        channels_list = "\n".join(f"• #{c}" for c in channels)
        respond(f"👀 You’re currently monitoring:\n{channels_list}")

# ---------- Flask routes ----------
@flask_app.route("/watch", methods=["POST"])
def watch_route(): return handler.handle(request)

@flask_app.route("/unwatch", methods=["POST"])
def unwatch_route(): return handler.handle(request)

@flask_app.route("/list", methods=["POST"])
def list_route(): return handler.handle(request)

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 3000)))
