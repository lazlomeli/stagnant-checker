from flask import Flask, request
from slack_bot import create_bolt_handler

app = Flask(__name__)
handler = create_bolt_handler()

@app.route("/", methods=["GET"])
def health():
    return {"status": "ok"}, 200

@app.route("/watch", methods=["POST"])
def watch():
    return handler.handle(request)

@app.route("/unwatch", methods=["POST"])
def unwatch():
    return handler.handle(request)

@app.route("/list", methods=["POST"])
def list_route():
    return handler.handle(request)
