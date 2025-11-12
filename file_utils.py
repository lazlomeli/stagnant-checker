import os
import json
import fcntl
import time
from datetime import datetime, timedelta

def load_json_with_lock(filename, default=None):
    """
    Safely load JSON data with file locking to prevent race conditions.
    
    Args:
        filename: Path to the JSON file
        default: Default value to return if file doesn't exist or is empty
    
    Returns:
        Loaded JSON data or default value
    """
    if default is None:
        default = {}
    
    if not os.path.exists(filename):
        return default
    
    with open(filename, "r") as f:
        # Acquire shared lock for reading
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            data = default
        finally:
            # Release lock
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    
    return data


def save_json_with_lock(filename, data):
    """
    Safely save JSON data with file locking to prevent race conditions.
    
    Args:
        filename: Path to the JSON file
        data: Data to save (must be JSON serializable)
    """
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
    
    # Ensure file exists
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            json.dump({}, f)
    
    with open(filename, "r+") as f:
        # Acquire exclusive lock for writing
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        finally:
            # Release lock
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def atomic_json_update(filename, update_func, default=None):
    """
    Atomically update a JSON file by applying an update function.
    
    This ensures the entire read-modify-write operation is atomic,
    preventing race conditions even when multiple processes/threads
    are trying to update the file simultaneously.
    
    Args:
        filename: Path to the JSON file
        update_func: Function that takes current data and returns modified data
        default: Default value if file doesn't exist
    
    Returns:
        The updated data
    
    Example:
        def add_channel(data):
            data['channels'].append('new-channel')
            return data
        
        atomic_json_update('data.json', add_channel, {'channels': []})
    """
    if default is None:
        default = {}
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(filename) if os.path.dirname(filename) else ".", exist_ok=True)
    
    # Ensure file exists
    if not os.path.exists(filename):
        with open(filename, "w") as f:
            json.dump(default, f)
    
    with open(filename, "r+") as f:
        # Acquire exclusive lock for the entire operation
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            # Read current data
            f.seek(0)
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = default
            
            # Apply update function
            updated_data = update_func(data)
            
            # Write back
            f.seek(0)
            f.truncate()
            json.dump(updated_data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
            
            return updated_data
        finally:
            # Release lock
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


# Channel cache management
CHANNEL_CACHE_FILE = "channel_cache.json"
CACHE_EXPIRY_HOURS = 24

def load_channel_cache():
    """
    Load the channel name → ID cache.
    
    Returns:
        dict: {
            "channels": {"channel-name": "channel_id"},
            "last_updated": "ISO timestamp"
        }
    """
    return load_json_with_lock(CHANNEL_CACHE_FILE, {"channels": {}, "last_updated": None})


def save_channel_cache(cache_data):
    """
    Save the channel name → ID cache.
    
    Args:
        cache_data: Dictionary with channels mapping and last_updated timestamp
    """
    save_json_with_lock(CHANNEL_CACHE_FILE, cache_data)


def is_cache_valid(cache_data):
    """
    Check if the cache is still valid (not expired).
    
    Args:
        cache_data: Cache dictionary with last_updated field
    
    Returns:
        bool: True if cache is valid, False if expired or never updated
    """
    if not cache_data.get("last_updated"):
        return False
    
    last_updated = datetime.fromisoformat(cache_data["last_updated"])
    expiry_time = datetime.now() - timedelta(hours=CACHE_EXPIRY_HOURS)
    
    return last_updated > expiry_time


def get_cached_channel_id(channel_name):
    """
    Get channel ID from cache if available and valid.
    
    Args:
        channel_name: Name of the channel
    
    Returns:
        Channel ID if found in valid cache, None otherwise
    """
    cache = load_channel_cache()
    
    if is_cache_valid(cache):
        return cache["channels"].get(channel_name)
    
    return None


def update_channel_cache(channel_mapping):
    """
    Update the channel cache with new channel name → ID mappings.
    
    Args:
        channel_mapping: Dictionary of channel_name → channel_id
    """
    cache = load_channel_cache()
    cache["channels"].update(channel_mapping)
    cache["last_updated"] = datetime.now().isoformat()
    save_channel_cache(cache)


def refresh_full_cache(client):
    """
    Refresh the entire channel cache by fetching all channels from Slack.
    This should be called periodically or when cache expires.
    
    Args:
        client: Slack WebClient instance
    
    Returns:
        dict: Updated channel mapping
    """
    from slack_sdk.errors import SlackApiError
    
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
    
    # Save the updated cache
    cache_data = {
        "channels": channel_mapping,
        "last_updated": datetime.now().isoformat()
    }
    save_channel_cache(cache_data)
    
    return channel_mapping

