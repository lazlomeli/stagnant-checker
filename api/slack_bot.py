print(">>> slack_bot.py STARTED IMPORTING", flush=True)

import os
print(">>> imported os", flush=True)

import re
print(">>> imported re", flush=True)

import json
print(">>> imported json", flush=True)

import logging
print(">>> imported logging", flush=True)

import redis
print(">>> imported redis", flush=True)

from slack_bolt import App
print(">>> imported slack_bolt.App", flush=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DATA_KEY = "user_data"


def get_redis():
    print(">>> get_redis() called", flush=True)
    url = os.environ.get("REDIS_URL")
    print(f">>> REDIS_URL = {url}", flush=True)

    if not url:
        logger.warning("REDIS_URL missing")
        return None

    try:
        print(">>> Attempting Redis connection", flush=True)
        r = redis.Redis.from_url(
            url,
            socket_connect_timeout=5,
            socket_timeout=5,
            decode_responses=False,
        )
        r.ping()
        print(">>> Redis connected successfully", flush=True)
        return r
    except Exception as e:
        print(f">>> Redis ERROR: {e}", flush=True)
        logger.error(f"Redis error: {e}")
        return None


def validate_channel_name(name):
    return True, None  # keep simple for debugging


def register_commands(app, r):
    print(">>> register_commands() called", flush=True)
    @app.command("/watch")
    def watch_cmd(ack, respond, command):
        ack()
        respond("debug watch ok")

    @app.command("/unwatch")
    def unwatch_cmd(ack, respond, command):
        ack()
        respond("debug unwatch ok")

    @app.command("/list")
    def list_cmd(ack, respond, command):
        ack()
        respond("debug list ok")


def load_data(r):
    print(">>> load_data() called", flush=True)
    raw = r.get(DATA_KEY)
    return json.loads(raw) if raw else {}


def save_data(r, data):
    print(">>> save_data() called", flush=True)
    try:
        r.set(DATA_KEY, json.dumps(data))
        return True
    except:
        return False


def create_bolt_handler():
    print(">>> create_bolt_handler() called", flush=True)

    print(">>> Creating Bolt App...", flush=True)
    app = App(
        token=os.environ.get("SLACK_BOT_TOKEN"),
        signing_secret=os.environ.get("SLACK_SIGN_SECRET"),
    )
    print(">>> Bolt App initialized", flush=True)

    r = get_redis()
    print(">>> Redis instance =", r, flush=True)

    register_commands(app, r)
    print(">>> Commands registered", flush=True)

    print(">>> Creating SlackRequestHandler...", flush=True)
    from slack_bolt.adapter.flask import SlackRequestHandler
    handler = SlackRequestHandler(app)
    print(">>> SlackRequestHandler created", flush=True)

    print(">>> slack_bot.py IMPORT COMPLETED", flush=True)
    return handler
