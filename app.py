from flask import Flask, request, jsonify
import json
import time
import base64
import requests
import logging
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii
import like_pb2
import like_count_pb2
import uid_generator_pb2
from google.protobuf.json_format import MessageToJson
from datetime import datetime, timedelta

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN_FILE = "tokens.json"
UIDPASS_FILE = "uidpass.json"

# ===== TOKEN MANAGEMENT =====
def load_tokens():
    try:
        with open(TOKEN_FILE, "r") as f:
            tokens = json.load(f)
            return tokens if tokens else []
    except Exception as e:
        logger.error(f"Error loading tokens: {e}")
        return []

def save_tokens(tokens):
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump(tokens, f, indent=2)
        logger.info(f"✅ Saved {len(tokens)} tokens")
    except Exception as e:
        logger.error(f"Error saving tokens: {e}")

def load_uidpass():
    try:
        with open(UIDPASS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading uidpass: {e}")
        return []

def get_token_info(token):
    """Decode JWT token to get account info"""
    try:
        if not token or '.' not in token:
            return None
        payload = token.split('.')[1]
        payload += '=' * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload).decode('utf-8')
        return json.loads(decoded)
    except Exception as e:
        logger.error(f"Token decode error: {e}")
        return None

def is_token_expired(token):
    """Check if token is expired"""
    info = get_token_info(token)
    if not info:
        return True
    exp_time = info.get('exp', 0)
    current_time = int(time.time())
    return current_time > exp_time

def fetch_new_token(uid, password):
    """Fetch new token from auth API"""
    try:
        api_url = "https://xtytdtyj-jwt.up.railway.app/token"
        url = f"{api_url}?uid={uid}&password={password}"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("token")
            if token:
                logger.info(f"✅ New token fetched for UID: {uid}")
                return token
    except Exception as e:
        logger.error(f"❌ Failed to fetch token for {uid}: {e}")
    
    return None

def refresh_expired_tokens():
    """Refresh all expired tokens"""
    logger.info("🔄 Starting token refresh...")
    tokens = load_tokens()
    uidpass_list = load_uidpass()
    
    if not tokens or not uidpass_list:
        logger.warning("⚠️ No tokens or uidpass found")
        return
    
    updated_count = 0
    
    for i, token_obj in enumerate(tokens):
        token = token_obj.get('token', '')
        
        if is_token_expired(token):
            if i < len(uidpass_list):
                uid = uidpass_list[i].get('uid')
                password = uidpass_list[i].get('password')
                
                new_token = fetch_new_token(uid, password)
                if new_token:
                    tokens[i]['token'] = new_token
                    updated_count += 1
                    time.sleep(0.5)
    
    if updated_count > 0:
        save_tokens(tokens)
        logger.info(f"✅ Refreshed {updated_count} tokens")
    else:
        logger.warning("⚠️ No tokens were refreshed")

def encrypt_message(plaintext):
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded = pad(plaintext, AES.block_size)
        encrypted = cipher.encrypt(padded)
        return binascii.hexlify(encrypted).decode('utf-8')
    except Exception as e:
        logger.error(f"Encryption error: {e}")
        return None

def create_protobuf(uid):
    try:
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        return message.SerializeToString()
    except Exception as e:
        logger.error(f"UID protobuf error: {e}")
        return None

def enc(uid):
    protobuf_data = create_protobuf(uid)
    if protobuf_data is None:
        return None
    return encrypt_message(protobuf_data)

def get_server_url(server_name, endpoint):
    """Get correct server URL based on region"""
    server_name = server_name.upper()
    
    if server_name == "IND":
        return f"https://client.ind.freefiremobile.com/{endpoint}"
    elif server_name in {"BR", "US", "SAC", "NA"}:
        return f"https://client.us.freefiremobile.com/{endpoint}"
    elif server_name == "BD":
        return f"https://clientbp.ggpolarbear.com/{endpoint}"
    else:
        return f"https://clientbp.ggpolarbear.com/{endpoint}"

def make_request(encrypted_uid, server_name, token):
    """Get player info"""
    try:
        url = get_server_url(server_name, "GetPlayerPersonalShow")
        edata = bytes.fromhex(encrypted_uid)
        
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1",
            'ReleaseVersion': "OB53"
        }
        
        response = requests.post(url, data=edata, headers=headers, verify=False, timeout=20)
        
        if response.status_code != 200:
            logger.error(f"API returned {response.status_code}")
            return None
        
        binary = bytes.fromhex(response.content.hex())
        items = like_count_pb2.Info()
        items.ParseFromString(binary)
        return items
    except Exception as e:
        logger.error(f"Request error: {e}")
        return None

def send_like_request(encrypted_uid, token, server_name):
    """Send like to player"""
    try:
        url = get_server_url(server_name, "LikeProfile")
        edata = bytes.fromhex(encrypted_uid)
        
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Authorization': f"Bearer {token}",
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1",
            'ReleaseVersion': "OB53"
        }
        
        response = requests.post(url, data=edata, headers=headers, verify=False, timeout=20)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"Like request error: {e}")
        return False

# ============ ROUTES ============

@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "status": "✅ API Running",
        "version": "2.0",
        "credit": "https://t.me/paglu_dev",
        "endpoints": {
            "health": "/health",
            "token_info": "/token-info",
            "like": "/like?uid=XXX&server_name=IND",
            "refresh_tokens": "/refresh-tokens"
        }
    })

@app.route('/health', methods=['GET'])
def health():
    tokens = load_tokens()
    valid_count = sum(1 for t in tokens if not is_token_expired(t.get('token', '')))
    
    return jsonify({
        'status': 'healthy' if valid_count > 0 else 'unhealthy',
        'total_tokens': len(tokens),
        'valid_tokens': valid_count,
        'expired_tokens': len(tokens) - valid_count
    }), 200 if valid_count > 0 else 500

@app.route('/token-info', methods=['GET'])
def token_info():
    """Check token validity"""
    tokens = load_tokens()
    if not tokens:
        return jsonify({"error": "No tokens", "status": 0}), 500
    
    info_list = []
    valid_count = 0
    
    for idx, token_obj in enumerate(tokens):
        token = token_obj.get('token', '')
        
        if not token or token.strip() == "":
            info_list.append({
                "index": idx,
                "status": "❌ EMPTY",
                "expired": True
            })
            continue
        
        info = get_token_info(token)
        if not info:
            info_list.append({
                "index": idx,
                "status": "❌ INVALID",
                "expired": True
            })
            continue
        
        exp_time = info.get('exp', 0)
        current_time = int(time.time())
        is_expired = current_time > exp_time
        hours_left = (exp_time - current_time) / 3600
        
        token_info_item = {
            "index": idx,
            "account_id": info.get('account_id'),
            "nickname": info.get('nickname'),
            "region": info.get('lock_region'),
            "expired": is_expired,
            "hours_left": round(hours_left, 2),
            "status": "❌ EXPIRED" if is_expired else "✅ VALID"
        }
        
        info_list.append(token_info_item)
        
        if not is_expired:
            valid_count += 1
    
    return jsonify({
        "total_tokens": len(tokens),
        "valid_tokens": valid_count,
        "expired_tokens": len(tokens) - valid_count,
        "tokens": info_list,
        "message": f"✅ {valid_count} token(s) are VALID" if valid_count > 0 else "❌ All tokens expired!"
    })

@app.route('/refresh-tokens', methods=['GET', 'POST'])
def refresh_tokens_route():
    """Manually refresh tokens"""
    try:
        refresh_expired_tokens()
        
        tokens = load_tokens()
        valid_count = sum(1 for t in tokens if not is_token_expired(t.get('token', '')))
        
        return jsonify({
            "status": "✅ Token refresh completed",
            "total_tokens": len(tokens),
            "valid_tokens": valid_count
        })
    except Exception as e:
        logger.error(f"Refresh error: {e}")
        return jsonify({"error": str(e), "status": 0}), 500

@app.route('/like', methods=['GET'])
def handle_like():
    uid = request.args.get("uid", "").strip()
    server_name = request.args.get("server_name", "IND").upper()
    
    if not uid or not uid.isdigit():
        return jsonify({
            "error": "Invalid UID. Must be numeric",
            "status": 0
        }), 400
    
    try:
        # Refresh tokens first
        refresh_expired_tokens()
        
        tokens = load_tokens()
        if not tokens:
            return jsonify({
                "error": "No tokens available",
                "status": 0
            }), 500
        
        # Find first valid token
        valid_token = None
        for t in tokens:
            token = t.get('token', '')
            if token and not is_token_expired(token):
                valid_token = token
                break
        
        if not valid_token:
            return jsonify({
                "error": "All tokens expired. Attempting refresh...",
                "status": 0
            }), 400
        
        logger.info(f"📤 Processing like for UID: {uid}, Server: {server_name}")
        
        encrypted_uid = enc(uid)
        if not encrypted_uid:
            return jsonify({
                "error": "Encryption failed",
                "status": 0
            }), 500
        
        # Get BEFORE
        before = make_request(encrypted_uid, server_name, valid_token)
        if before is None:
            return jsonify({
                "error": "Failed to fetch player info",
                "status": 0
            }), 500
        
        from google.protobuf.json_format import MessageToJson
        data_before = json.loads(MessageToJson(before))
        account_info = data_before.get('AccountInfo', {})
        
        before_like = int(account_info.get('Likes', 0) or 0)
        player_uid = int(account_info.get('UID', 0) or 0)
        player_name = str(account_info.get('PlayerNickname', 'Unknown'))
        player_level = int(account_info.get('Level', 0) or 0)
        
        if player_uid == 0:
            return jsonify({
                "error": "Invalid UID or player not found",
                "status": 0
            }), 400
        
        logger.info(f"👤 Player: {player_name} | Level: {player_level} | Likes: {before_like}")
        
        # Send LIKE
        time.sleep(1)
        like_sent = send_like_request(encrypted_uid, valid_token, server_name)
        
        if not like_sent:
            logger.warning("⚠️ Like request failed")
            return jsonify({
                "error": "Failed to send like",
                "status": 2,
                "PlayerNickname": player_name,
                "UID": player_uid,
                "PlayerLevel": player_level,
                "LikesbeforeCommand": before_like
            })
        
        # Wait and check AFTER
        time.sleep(3)
        after = make_request(encrypted_uid, server_name, valid_token)
        
        if after is None:
            return jsonify({
                "error": "Failed to verify like",
                "status": 2,
                "PlayerNickname": player_name,
                "UID": player_uid,
                "LikesbeforeCommand": before_like
            })
        
        data_after = json.loads(MessageToJson(after))
        after_like = int(data_after.get('AccountInfo', {}).get('Likes', 0) or 0)
        
        like_given = after_like - before_like
        status = 1 if like_given > 0 else 2
        
        logger.info(f"✅ Like sent! Before: {before_like}, After: {after_like}, Given: {like_given}")
        
        return jsonify({
            "status": status,
            "credit": "https://t.me/paglu_dev",
            "LikesGivenByAPI": like_given,
            "LikesafterCommand": after_like,
            "LikesbeforeCommand": before_like,
            "PlayerNickname": player_name,
            "PlayerLevel": player_level,
            "Region": server_name,
            "UID": player_uid,
            "message": "✅ Like sent successfully!" if status == 1 else "⚠️ Like may have failed"
        })
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)
        return jsonify({
            "error": str(e),
            "status": 0
        }), 500

if __name__ == '__main__':
    # Refresh tokens on startup
    refresh_expired_tokens()
    app.run(debug=False)
