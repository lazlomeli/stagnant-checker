import os
import re
import json
import redis
import logging
import traceback
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
from flask import Flask, request

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_SIGN_SECRET = os.environ.get("SLACK_SIGN_SECRET", "")
REDIS_URL = os.environ.get("REDIS_URL", "")

# Initialize Redis with connection timeout
logger.info("Initializing Redis connection...")
try:
    r = redis.Redis.from_url(
        REDIS_URL,
        socket_connect_timeout=5,
        socket_timeout=5,
        decode_responses=False
    ) if REDIS_URL else None
    if r:
        logger.info("Redis connection initialized successfully")
    else:
        logger.warning("Redis URL not provided, Redis is disabled")
except Exception as e:
    logger.error(f"Redis connection error: {e}")
    logger.debug(traceback.format_exc())
    r = None

# Initialize Slack App (may fail if token is invalid, but won't crash)
logger.info("Initializing Slack App...")
try:
    app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGN_SECRET)
    logger.info("Slack App initialized successfully")
except Exception as e:
    logger.error(f"Slack App initialization error: {e}")
    logger.debug(traceback.format_exc())
    # Create a dummy app to prevent crashes
    app = None
flask_app = Flask(__name__)
handler = SlackRequestHandler(app) if app else None

DATA_KEY = "user_data"

# ---------- Storage Helpers ----------
def load_data():
    """Load user data from Redis with error handling."""
    try:
        if not r:
            logger.error("Cannot load data: Redis connection is not available")
            return {}
        
        data = r.get(DATA_KEY)
        result = json.loads(data) if data else {}
        logger.debug(f"Data loaded successfully. Keys: {list(result.keys())}")
        return result
    except Exception as e:
        logger.error(f"Error loading data from Redis: {e}")
        logger.debug(traceback.format_exc())
        return {}

def save_data(data):
    """
    Save user data to Redis.
    
    Returns:
        bool: True if save was successful, False otherwise
    """
    try:
        if not r:
            logger.error("Cannot save data: Redis connection is not available")
            return False
        
        r.set(DATA_KEY, json.dumps(data))
        logger.debug(f"Data saved successfully. Keys: {list(data.keys())}")
        return True
    except Exception as e:
        logger.error(f"Error saving data to Redis: {e}")
        logger.debug(traceback.format_exc())
        return False

def validate_channel_name(channel_name):
    """
    Validate and sanitize channel name according to Slack's naming rules.
    
    Args:
        channel_name: Channel name to validate
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not channel_name:
        return False, "Channel name cannot be empty"
    
    # Slack channel names: lowercase letters, numbers, hyphens, underscores
    # Maximum length is 80 characters
    if not re.match(r'^[a-z0-9\-_]{1,80}$', channel_name):
        return False, (
            "Invalid channel name. Channel names must:\n"
            "• Be 1-80 characters long\n"
            "• Only contain lowercase letters, numbers, hyphens, and underscores\n"
            "• Not contain spaces or special characters"
        )
    
    return True, None

# ---------- Commands ----------
@app.command("/watch")
def add_channel(ack, respond, command):
    try:
        logger.info("=== /watch command received ===")
        logger.info(f"Command payload: {json.dumps(command, default=str)}")
        
        ack()
        logger.info("Command acknowledged")
        
        user_id = command["user_id"]
        text = command.get("text", "").strip()
        logger.info(f"User ID: {user_id}, Text: '{text}'")
        
        # Require # symbol
        if not text.startswith("#"):
            logger.warning(f"Invalid format - missing # symbol: '{text}'")
            respond("Usage: `/watch #channel-name`\nPlease include the # symbol.")
            return
        
        # Remove # and convert to lowercase
        channel_name = text[1:].lower()
        logger.info(f"Parsed channel name: '{channel_name}'")
        
        if not channel_name:
            logger.warning("Empty channel name provided")
            respond("Usage: `/watch #channel-name`")
            return
        
        # Validate channel name
        is_valid, error_msg = validate_channel_name(channel_name)
        if not is_valid:
            logger.warning(f"Invalid channel name: {error_msg}")
            respond(f"❌ {error_msg}")
            return
        
        logger.info("Channel name validated successfully")

        # Load, update, save
        logger.info("Loading existing data...")
        data = load_data()
        user_data = data.get(user_id, {"channels": []})
        logger.info(f"User currently monitoring {len(user_data['channels'])} channels")
        
        if channel_name in user_data["channels"]:
            logger.info(f"Channel #{channel_name} already in watchlist")
            respond(f"Channel *#{channel_name}* is already being monitored.")
        else:
            # Limit: 50 channels per user
            if len(user_data["channels"]) >= 50:
                logger.warning(f"User {user_id} has reached channel limit")
                respond("❌ You've reached the maximum of 50 monitored channels.")
                return
            
            logger.info(f"Adding channel #{channel_name} to watchlist...")
            user_data["channels"].append(channel_name)
            data[user_id] = user_data
            
            if not save_data(data):
                logger.error("Failed to save data to Redis")
                respond("❌ Error saving data. Please try again.")
                return
            
            logger.info(f"✅ Successfully added #{channel_name} for user {user_id}")
            respond(f"✅ Added *#{channel_name}* to your personal watchlist.")
    
    except Exception as e:
        logger.error(f"FATAL ERROR in /watch command: {e}")
        logger.error(traceback.format_exc())
        try:
            respond(f"❌ An unexpected error occurred. Please try again or contact support.\nError: {str(e)}")
        except:
            logger.error("Failed to send error response to user")
        raise

@app.command("/unwatch")
def unwatch(ack, respond, command):
    try:
        logger.info("=== /unwatch command received ===")
        logger.info(f"Command payload: {json.dumps(command, default=str)}")
        
        ack()
        logger.info("Command acknowledged")
        
        user_id = command["user_id"]
        text = command.get("text", "").strip()
        logger.info(f"User ID: {user_id}, Text: '{text}'")
        
        # Require # symbol
        if not text.startswith("#"):
            logger.warning(f"Invalid format - missing # symbol: '{text}'")
            respond("Usage: `/unwatch #channel-name`\nPlease include the # symbol.")
            return
        
        # Remove # and convert to lowercase
        channel_name = text[1:].lower()
        logger.info(f"Parsed channel name: '{channel_name}'")
        
        if not channel_name:
            logger.warning("Empty channel name provided")
            respond("Usage: `/unwatch #channel-name`")
            return
        
        # Validate channel name
        is_valid, error_msg = validate_channel_name(channel_name)
        if not is_valid:
            logger.warning(f"Invalid channel name: {error_msg}")
            respond(f"❌ {error_msg}")
            return
        
        logger.info("Channel name validated successfully")
        
        # Load, update, save
        logger.info("Loading existing data...")
        data = load_data()
        user_data = data.get(user_id, {"channels": []})
        logger.info(f"User currently monitoring {len(user_data['channels'])} channels")

        if channel_name not in user_data["channels"]:
            logger.info(f"Channel #{channel_name} not in watchlist")
            respond(f"Channel *#{channel_name}* is not in your watchlist.")
        else:
            logger.info(f"Removing channel #{channel_name} from watchlist...")
            user_data["channels"].remove(channel_name)
            data[user_id] = user_data
            
            if not save_data(data):
                logger.error("Failed to save data to Redis")
                respond("❌ Error saving data. Please try again.")
                return
            
            logger.info(f"✅ Successfully removed #{channel_name} for user {user_id}")
            respond(f"🗑️ Removed *#{channel_name}* from your watchlist.")
    
    except Exception as e:
        logger.error(f"FATAL ERROR in /unwatch command: {e}")
        logger.error(traceback.format_exc())
        try:
            respond(f"❌ An unexpected error occurred. Please try again or contact support.\nError: {str(e)}")
        except:
            logger.error("Failed to send error response to user")
        raise

@app.command("/list")
def list_channels(ack, respond, command):
    try:
        logger.info("=== /list command received ===")
        logger.info(f"Command payload: {json.dumps(command, default=str)}")
        
        ack()
        logger.info("Command acknowledged")
        
        user_id = command["user_id"]
        logger.info(f"User ID: {user_id}")
        
        logger.info("Loading existing data...")
        data = load_data()
        user_data = data.get(user_id, {"channels": []})
        channels = user_data["channels"]
        logger.info(f"User is monitoring {len(channels)} channels")

        if not channels:
            logger.info("User has no channels in watchlist")
            respond("You're not monitoring any channels yet.")
        else:
            channels_list = "\n".join(f"• #{c}" for c in channels)
            logger.info(f"Sending list of {len(channels)} channels to user")
            respond(f"👀 You're currently monitoring:\n{channels_list}")
    
    except Exception as e:
        logger.error(f"FATAL ERROR in /list command: {e}")
        logger.error(traceback.format_exc())
        try:
            respond(f"❌ An unexpected error occurred. Please try again or contact support.\nError: {str(e)}")
        except:
            logger.error("Failed to send error response to user")
        raise

# ---------- Flask routes for Vercel ----------
@flask_app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint."""
    logger.info("Health check endpoint called")
    status = {
        "status": "running",
        "slack_configured": bool(SLACK_BOT_TOKEN and app),
        "redis_configured": bool(REDIS_URL and r),
    }
    logger.debug(f"Health check status: {status}")
    return status, 200

@flask_app.route("/watch", methods=["POST"])
def watch_route():
    logger.info("=== /watch route called ===")
    logger.debug(f"Request headers: {dict(request.headers)}")
    logger.debug(f"Request data: {request.get_data(as_text=True)[:500]}")  # Log first 500 chars
    
    if not handler:
        logger.error("Handler not available - Slack app not configured")
        return {"error": "Slack app not configured. Please check SLACK_BOT_TOKEN and SLACK_SIGN_SECRET."}, 503
    
    try:
        result = handler.handle(request)
        logger.info("Request handled successfully")
        return result
    except Exception as e:
        logger.error(f"Error handling /watch request: {e}")
        logger.error(traceback.format_exc())
        raise

@flask_app.route("/unwatch", methods=["POST"])
def unwatch_route():
    logger.info("=== /unwatch route called ===")
    logger.debug(f"Request headers: {dict(request.headers)}")
    logger.debug(f"Request data: {request.get_data(as_text=True)[:500]}")  # Log first 500 chars
    
    if not handler:
        logger.error("Handler not available - Slack app not configured")
        return {"error": "Slack app not configured. Please check SLACK_BOT_TOKEN and SLACK_SIGN_SECRET."}, 503
    
    try:
        result = handler.handle(request)
        logger.info("Request handled successfully")
        return result
    except Exception as e:
        logger.error(f"Error handling /unwatch request: {e}")
        logger.error(traceback.format_exc())
        raise

@flask_app.route("/list", methods=["POST"])
def list_route():
    logger.info("=== /list route called ===")
    logger.debug(f"Request headers: {dict(request.headers)}")
    logger.debug(f"Request data: {request.get_data(as_text=True)[:500]}")  # Log first 500 chars
    
    if not handler:
        logger.error("Handler not available - Slack app not configured")
        return {"error": "Slack app not configured. Please check SLACK_BOT_TOKEN and SLACK_SIGN_SECRET."}, 503
    
    try:
        result = handler.handle(request)
        logger.info("Request handled successfully")
        return result
    except Exception as e:
        logger.error(f"Error handling /list request: {e}")
        logger.error(traceback.format_exc())
        raise

# For Vercel serverless
app_handler = flask_app
