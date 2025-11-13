# app.py
import logging

from flask import Flask, request
from slack_bolt.adapter.flask import SlackRequestHandler

from slack_bot import bolt_app, SLACK_BOT_TOKEN, REDIS_URL, r

logger = logging.getLogger(__name__)
logger.info("Loading Flask app entrypoint")

app = Flask(__name__)
handler = SlackRequestHandler(bolt_app)

# ---------- Health Check ----------
@app.route("/", methods=["GET"])
def health_check():
    logger.info("Health check called")
    status = {
        "status": "running",
        "slack_configured": bool(SLACK_BOT_TOKEN),
        "redis_configured": bool(REDIS_URL and r),
    }
    return status, 200


# ---------- Slack Slash Command Routes ----------
# You can point each Slack command to a different URL
# e.g. /watch → /watch, /unwatch → /unwatch, /list → /list

@app.route("/watch", methods=["POST"])
def watch_route():
    logger.info("HTTP /watch route called")
    return handler.handle(request)


@app.route("/unwatch", methods=["POST"])
def unwatch_route():
    logger.info("HTTP /unwatch route called")
    return handler.handle(request)


@app.route("/list", methods=["POST"])
def list_route():
    logger.info("HTTP /list route called")
    return handler.handle(request)

