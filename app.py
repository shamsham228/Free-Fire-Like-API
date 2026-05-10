from flask import Flask, request, jsonify
import asyncio
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from google.protobuf.json_format import MessageToJson
import binascii
import aiohttp
import requests
import json
import like_pb2
import like_count_pb2
import uid_generator_pb2
from google.protobuf.message import DecodeError
import base64
import time
import logging
from datetime import datetime, timedelta

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN_FILE = "tokens.json"
UIDPASS_FILE = "uidpass.json"
CACHE_FILE = "like_cache.json"

LIKE_LIMITS = {
    "level_1_2": {
        "daily_likes": 20,
        "likes_per_uid": 5,
        "requests_per_call": 5
    },
    "level_3_10": {
        "daily_likes": 50,
        "likes_per_uid": 10,
        "requests_per_call": 10
    },
    "level_11_30": {
        "daily_likes": 150,
        "likes_per_uid": 30,
        "requests_per_call": 30
    },
    "level_30_plus": {
        "daily_likes": 300,
        "likes_per_uid": 50,
        "requests_per_call": 50
    }
}

def load_tokens():
    try:
        if not os.path.exists(TOKEN_FILE):
            logger.warning(f"{TOKEN_FILE} not found")
            return None
        with open(TOKEN_FILE, "r") as f:
            tokens = json.load(f)
        logger.info(f"Loaded {len(tokens)} tokens")
        return tokens
    except Exception as e:
        logger.error(f"Error loading tokens: {e}")
        return None

def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            cache = json.load(f)
        return cache
    except:
        return {}

def save_cache(cache):
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving cache: {e}")

def get_token_info(token):
    try:
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        decoded_payload = base64.urlsafe_b64decode(payload).decode('utf-8')
        return json.loads(decoded_payload)
    except Exception as e:
        logger.error(f"Error decoding token: {e}")
        return None

def is_token_expired(token):
    info = get_token_info(token)
    if not info:
        return True
    exp_time = info.get('exp', 0)
    current_time = int(time.time())
    if current_time > exp_time:
        logger.warning(f"Token expired!")
        return True
    hours_left = (exp_time - current_time) / 3600
    logger.info(f"Token expires in {hours_left:.2f} hours")
    return False

def get_like_limit(level):
    if level <= 2:
        return LIKE_LIMITS["level_1_2"]
    elif level <= 10:
        return LIKE_LIMITS["level_3_10"]
    elif level <= 30:
        return LIKE_LIMITS["level_11_30"]
    else:
        return LIKE_LIMITS["level_30_plus"]

def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded_message = pad(plaintext, AES.block_size)
        encrypted_message = cipher.encrypt(padded_message)
        return binascii.hexlify(encrypted_message).decode('utf-8')
    except Exception as e:
        logger.error(f"Error encrypting message: {e}")
        return None

def create_protobuf_message(user_id, region):
    try:
        message = like_pb2.like()
        message.uid = int(user_id)
        message.region = region
        return message.SerializeToString()
    except Exception as e:
        logger.error(f"Error creating protobuf message: {e}")
        return None

async def send_request(encrypted_uid, token, url, delay=0.5):
    try:
        edata = bytes.fromhex(encrypted_uid)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB53"
        }
        await asyncio.sleep(delay)
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=edata, headers=headers, timeout=aiohttp.ClientTimeout(total=20)) as response:
                if response.status != 200:
                    logger.warning(f"Request failed with status: {response.status}")
                    return False
                return True
    except Exception as e:
        logger.error(f"Exception in send_request: {e}")
        return False

async def send_multiple_requests(uid, server_name, url, request_count):
    try:
        region = server_name
        protobuf_message = create_protobuf_message(uid, region)
        if protobuf_message is None:
            logger.error("Failed to create protobuf message.")
            return 0
        encrypted_uid = encrypt_message(protobuf_message)
        if encrypted_uid is None:
            logger.error("Encryption failed.")
            return 0
        tokens = load_tokens()
        if tokens is None or len(tokens) == 0:
            logger.error("No valid tokens available.")
            return 0
        tasks = []
        for i in range(request_count):
            token = tokens[i % len(tokens)]["token"]
            delay = 0.8 + (i * 0.1)
            tasks.append(send_request(encrypted_uid, token, url, delay=delay))
        logger.info(f"Sending {request_count} like requests with delays...")
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r is True)
        logger.info(f"Successful requests: {success_count}/{request_count}")
        return success_count
    except Exception as e:
        logger.error(f"Exception in send_multiple_requests: {e}")
        return 0

def create_protobuf(uid):
    try:
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        return message.SerializeToString()
    except Exception as e:
        logger.error(f"Error creating uid protobuf: {e}")
        return None

def enc(uid):
    protobuf_data = create_protobuf(uid)
    if protobuf_data is None:
        return None
    encrypted_uid = encrypt_message(protobuf_data)
    return encrypted_uid

def make_request(encrypt, server_name, token):
    try:
        if server_name == "IND":
            url = "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            url = "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
        else:
            url = "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"
        edata = bytes.fromhex(encrypt)
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Connection': "Keep-Alive",
            'Accept-Encoding': "gzip",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1",
            'X-GA': "v1 1",
            'ReleaseVersion': "OB53"
        }
        response = requests.post(url, data=edata, headers=headers, verify=False, timeout=20)
        hex_data = response.content.hex()
        binary = bytes.fromhex(hex_data)
        decode = decode_protobuf(binary)
        return decode
    except Exception as e:
        logger.error(f"Error in make_request: {e}")
        return None

def decode_protobuf(binary):
    try:
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        return items
    except DecodeError as e:
        logger.error(f"Error decoding Protobuf data: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during protobuf decoding: {e}")
        return None

def check_daily_limit(token_id):
    cache = load_cache()
    today = datetime.now().strftime("%Y-%m-%d")
    key = f"{token_id}_{today}"
    if key not in cache:
        cache[key] = 0
    return cache[key], key

def update_cache(key, likes_added):
    cache = load_cache()
    if key not in cache:
        cache[key] = 0
    cache[key] += likes_added
    save_cache(cache)

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "credit": "https://t.me/paglu_dev",
        "message": "Welcome to the Free Fire Like API (FIXED v2.0)",
        "status": "API is running",
        "endpoints": "/like?uid=<uid>&server_name=<server_name>",
        "example": "/like?uid=123456789&server_name=IND",
        "note": "Level 1-2 accounts: 20 likes/day max"
    })

@app.route('/health', methods=['GET'])
def health():
    tokens = load_tokens()
    if not tokens:
        return jsonify({'status': 'unhealthy', 'error': 'No tokens loaded'}), 500
    valid_tokens = [t for t in tokens if not is_token_expired(t.get('token', ''))]
    return jsonify({
        'status': 'healthy',
        'total_tokens': len(tokens),
        'valid_tokens': len(valid_tokens),
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/token-info', methods=['GET'])
def token_info():
    tokens = load_tokens()
    if not tokens:
        return jsonify({
            "error": "No tokens loaded",
            "message": "tokens.json is empty or missing"
        }), 500
    info_list = []
    for idx, token_obj in enumerate(tokens):
        token = token_obj.get('token', '')
        if not token:
            info_list.append({"index": idx, "error": "Empty token"})
            continue
        info = get_token_info(token)
        if info:
            info_list.append({
                "index": idx,
                "account_id": info.get('account_id'),
                "nickname": info.get('nickname'),
                "region": info.get('lock_region'),
                "expired": is_token_expired(token),
                "hours_left": round((info.get('exp', 0) - int(time.time())) / 3600, 2)
            })
        else:
            info_list.append({"index": idx, "error": "Cannot decode token"})
    return jsonify({
        "total_tokens": len(tokens),
        "valid_tokens": sum(1 for t in info_list if "error" not in t),
        "tokens": info_list
    })

@app.route('/debug', methods=['GET'])
def debug():
    tokens = load_tokens()
    if not tokens:
        return jsonify({
            "error": "No tokens loaded",
            "tokens_file_exists": os.path.exists(TOKEN_FILE),
            "tokens_file_size": os.path.getsize(TOKEN_FILE) if os.path.exists(TOKEN_FILE) else 0
        }), 500
    token_status = []
    for idx, token_obj in enumerate(tokens):
        token = token_obj.get('token', '')
        if not token:
            token_status.append({"error": "Empty token", "index": idx})
            continue
        info = get_token_info(token)
        if not info:
            token_status.append({"error": "Cannot decode token", "index": idx})
            continue
        token_status.append({
            "index": idx,
            "account_id": info.get('account_id'),
            "nickname": info.get('nickname'),
            "region": info.get('lock_region'),
            "expired": is_token_expired(token),
            "expires_in_hours": round((info.get('exp', 0) - int(time.time())) / 3600, 2)
        })
    return jsonify({
        "total_tokens": len(tokens),
        "valid_tokens": sum(1 for t in token_status if "error" not in t),
        "token_details": token_status
    })

@app.route('/like', methods=['GET'])
def handle_requests():
    uid = request.args.get("uid")
    if not uid:
        return jsonify({"error": "UID is required"}), 400
    try:
        tokens = load_tokens()
        if tokens is None or not tokens:
            return jsonify({
                "error": "Failed to load tokens",
                "message": "No valid tokens found. tokens.json is empty",
                "status": 0
            }), 500
        valid_tokens = [t for t in tokens if not is_token_expired(t.get('token', ''))]
        if not valid_tokens:
            return jsonify({
                "error": "All tokens expired",
                "message": "Please update tokens",
                "status": 0
            }), 400
        token = valid_tokens[0]['token']
        token_info = get_token_info(token)
        if not token_info:
            return jsonify({"error": "Cannot decode token", "status": 0}), 500
        server_name = request.args.get("server_name", "").upper()
        if not server_name:
            server_name = token_info.get('lock_region', 'IND').upper()
        if not server_name:
            return jsonify({"error": "server_name could not be determined"}), 400
        encrypted_uid = enc(uid)
        if encrypted_uid is None:
            return jsonify({"error": "Encryption of UID failed"}), 500
        before = make_request(encrypted_uid, server_name, token)
        if before is None:
            return jsonify({
                "error": "Failed to retrieve player info",
                "message": "Invalid UID or server error",
                "status": 0
            }), 500
        data_before = json.loads(MessageToJson(before))
        account_info_before = data_before.get('AccountInfo', {})
        before_like = int(account_info_before.get('Likes', 0) or 0)
        player_level = int(account_info_before.get('Level', 0) or 0)
        player_uid = int(account_info_before.get('UID', 0) or 0)
        player_name = str(account_info_before.get('PlayerNickname', 'Unknown'))
        logger.info(f"Target: {player_uid}, Level: {player_level}, Before: {before_like}")
        limit_config = get_like_limit(player_level)
        request_count = limit_config['requests_per_call']
        max_daily_likes = limit_config['daily_likes']
        max_likes_per_uid = limit_config['likes_per_uid']
        token_id = token_info.get('account_id', 'unknown')
        current_daily_likes, cache_key = check_daily_limit(token_id)
        if current_daily_likes >= max_daily_likes:
            return jsonify({
                "error": "Daily like limit reached",
                "message": f"Sent {current_daily_likes}/{max_daily_likes} today",
                "status": 0,
                "daily_limit": max_daily_likes,
                "current_likes": current_daily_likes
            }), 429
        if before_like + request_count > max_likes_per_uid:
            request_count = max(1, max_likes_per_uid - before_like)
            logger.info(f"Adjusted request count to {request_count}")
        if server_name == "IND":
            url = "https://client.ind.freefiremobile.com/LikeProfile"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            url = "https://client.us.freefiremobile.com/LikeProfile"
        else:
            url = "https://clientbp.ggpolarbear.com/LikeProfile"
        logger.info(f"Sending {request_count} likes...")
        success_count = asyncio.run(send_multiple_requests(uid, server_name, url, request_count))
        time.sleep(2)
        after = make_request(encrypted_uid, server_name, token)
        if after is None:
            return jsonify({
                "error": "Failed to check likes after request",
                "status": 0
            }), 500
        data_after = json.loads(MessageToJson(after))
        account_info_after = data_after.get('AccountInfo', {})
        after_like = int(account_info_after.get('Likes', 0) or 0)
        like_given = after_like - before_like
        update_cache(cache_key, like_given)
        status = 1 if like_given > 0 else 2
        response = {
            "credit": "https://t.me/paglu_dev",
            "LikesGivenByAPI": like_given,
            "LikesafterCommand": after_like,
            "LikesbeforeCommand": before_like,
            "PlayerNickname": player_name,
            "PlayerLevel": player_level,
            "Region": server_name,
            "UID": player_uid,
            "status": status,
            "message": "✅ Likes sent successfully!" if status == 1 else "❌ Failed to send likes",
            "daily_limit_info": {
                "max_daily_likes": max_daily_likes,
                "likes_sent_today": current_daily_likes + like_given,
                "remaining": max_daily_likes - (current_daily_likes + like_given)
            },
            "account_level": player_level,
            "max_likes_per_uid": max_likes_per_uid
        }
        logger.info(f"Response: Status={status}, Likes={like_given}")
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        return jsonify({"error": str(e), "status": 0}), 500

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False)
