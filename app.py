from flask import Flask, request, jsonify
import json
import time
import base64
import requests
import logging
import sys
import os
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import binascii

try:
    import like_pb2
    import like_count_pb2
    import uid_generator_pb2
except ImportError as e:
    print(f"❌ FATAL: Protobuf files missing: {e}")
    sys.exit(1)

from google.protobuf.json_format import MessageToJson

app = Flask(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TOKEN_FILE = "tokens.json"
UIDPASS_FILE = "uidpass.json"

# ===== TOKEN MANAGEMENT =====

def load_tokens():
    """Load tokens from JSON file"""
    try:
        if not os.path.exists(TOKEN_FILE):
            logger.warning(f"⚠️ File not found: {TOKEN_FILE}")
            return []
        
        with open(TOKEN_FILE, "r") as f:
            data = json.load(f)
            logger.info(f"✅ Loaded {len(data)} tokens from {TOKEN_FILE}")
            return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"❌ Error loading {TOKEN_FILE}: {e}", exc_info=True)
        return []

def save_tokens(tokens):
    """Save tokens to JSON file"""
    try:
        with open(TOKEN_FILE, "w") as f:
            json.dump(tokens, f, indent=2)
        logger.info(f"✅ Saved {len(tokens)} tokens to {TOKEN_FILE}")
        return True
    except Exception as e:
        logger.error(f"❌ Error saving {TOKEN_FILE}: {e}")
        return False

def get_token_info(token):
    """Decode JWT token"""
    try:
        if not token or '.' not in token:
            logger.debug("❌ Invalid token format")
            return None
        
        parts = token.split('.')
        if len(parts) != 3:
            logger.debug(f"❌ Token has {len(parts)} parts, expected 3")
            return None
        
        payload = parts[1]
        payload += '=' * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload).decode('utf-8')
        info = json.loads(decoded)
        
        logger.debug(f"✅ Token decoded: account_id={info.get('account_id')}, exp={info.get('exp')}")
        return info
    except Exception as e:
        logger.error(f"❌ Token decode error: {e}")
        return None

def is_token_expired(token):
    """Check if token is expired"""
    try:
        info = get_token_info(token)
        if not info:
            return True
        
        exp_time = info.get('exp', 0)
        current_time = int(time.time())
        is_expired = current_time > exp_time
        
        hours_left = (exp_time - current_time) / 3600
        logger.debug(f"Token expiry: {is_expired} (hours left: {hours_left:.1f})")
        
        return is_expired
    except Exception as e:
        logger.error(f"❌ Expiry check error: {e}")
        return True

def encrypt_message(plaintext):
    """Encrypt using AES"""
    try:
        key = b'Yg&tc%DEuh6%Zc^8'
        iv = b'6oyZDr22E3ychjM%'
        cipher = AES.new(key, AES.MODE_CBC, iv)
        padded = pad(plaintext, AES.block_size)
        encrypted = cipher.encrypt(padded)
        hex_encrypted = binascii.hexlify(encrypted).decode('utf-8')
        logger.debug(f"✅ Encrypted {len(plaintext)} bytes -> {len(hex_encrypted)} hex chars")
        return hex_encrypted
    except Exception as e:
        logger.error(f"❌ Encryption error: {e}")
        return None

def create_protobuf(uid):
    """Create UID protobuf"""
    try:
        message = uid_generator_pb2.uid_generator()
        message.saturn_ = int(uid)
        message.garena = 1
        data = message.SerializeToString()
        logger.debug(f"✅ Created protobuf for UID {uid}: {len(data)} bytes")
        return data
    except Exception as e:
        logger.error(f"❌ Protobuf error: {e}")
        return None

def enc(uid):
    """Encrypt UID"""
    try:
        protobuf_data = create_protobuf(uid)
        if not protobuf_data:
            logger.error(f"❌ Failed to create protobuf for {uid}")
            return None
        
        encrypted = encrypt_message(protobuf_data)
        if not encrypted:
            logger.error(f"❌ Failed to encrypt protobuf for {uid}")
            return None
        
        logger.info(f"✅ UID {uid} encrypted successfully")
        return encrypted
    except Exception as e:
        logger.error(f"❌ Encryption failed: {e}")
        return None

def get_server_url(server_name, endpoint):
    """Get correct server URL"""
    server_name = server_name.upper()
    
    if server_name == "IND":
        url = f"https://client.ind.freefiremobile.com/{endpoint}"
    elif server_name in {"BR", "US", "SAC", "NA"}:
        url = f"https://client.us.freefiremobile.com/{endpoint}"
    else:
        url = f"https://clientbp.ggpolarbear.com/{endpoint}"
    
    logger.debug(f"Server URL: {url}")
    return url

def make_request(encrypted_uid, server_name, token):
    """Fetch player info from Free Fire"""
    try:
        url = get_server_url(server_name, "GetPlayerPersonalShow")
        
        logger.info(f"📤 Making request to Free Fire: {url}")
        
        edata = bytes.fromhex(encrypted_uid)
        logger.debug(f"Converted encrypted data: {len(edata)} bytes")
        
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Authorization': f"Bearer {token[:50]}...",
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1",
            'ReleaseVersion': "OB53"
        }
        
        logger.debug(f"Headers: {list(headers.keys())}")
        logger.debug(f"Making POST request...")
        
        response = requests.post(url, data=edata, headers=headers, verify=False, timeout=20)
        
        logger.info(f"📊 Response status: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        logger.debug(f"Response size: {len(response.content)} bytes")
        
        if response.status_code != 200:
            logger.error(f"❌ Server returned {response.status_code}")
            try:
                logger.error(f"Response body: {response.text[:500]}")
            except:
                logger.error(f"Response (hex): {response.content.hex()[:100]}")
            return None
        
        logger.debug(f"✅ Got 200 response, parsing protobuf...")
        
        try:
            binary = bytes.fromhex(response.content.hex())
            logger.debug(f"Binary data length: {len(binary)} bytes")
            
            items = like_count_pb2.Info()
            items.ParseFromString(binary)
            
            logger.debug(f"Protobuf parsed successfully")
            
            data = json.loads(MessageToJson(items))
            logger.debug(f"Converted to JSON: {json.dumps(data)[:200]}")
            
            logger.info(f"✅ Player info fetched successfully")
            return items
            
        except Exception as parse_error:
            logger.error(f"❌ Protobuf parsing error: {parse_error}", exc_info=True)
            logger.error(f"Raw response (first 200 bytes): {response.content[:200]}")
            return None
        
    except requests.exceptions.Timeout:
        logger.error(f"❌ Request timeout (20s)")
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"❌ Connection error: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Request error: {e}", exc_info=True)
        return None

def send_like_request(encrypted_uid, token, server_name):
    """Send like to Free Fire"""
    try:
        url = get_server_url(server_name, "LikeProfile")
        
        logger.info(f"💌 Sending like to: {url}")
        
        edata = bytes.fromhex(encrypted_uid)
        
        headers = {
            'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 9; ASUS_Z01QD Build/PI)",
            'Authorization': f"Bearer {token[:50]}...",
            'Content-Type': "application/x-www-form-urlencoded",
            'X-Unity-Version': "2018.4.11f1",
            'ReleaseVersion': "OB53"
        }
        
        response = requests.post(url, data=edata, headers=headers, verify=False, timeout=20)
        
        success = response.status_code == 200
        logger.info(f"💌 Like response: {response.status_code} ({'✅ Success' if success else '❌ Failed'})")
        
        return success
        
    except Exception as e:
        logger.error(f"❌ Like error: {e}", exc_info=True)
        return False

# ============ ROUTES ============

@app.route('/', methods=['GET'])
def index():
    logger.info("📍 Index endpoint called")
    return jsonify({
        "status": "✅ API Running",
        "version": "2.1",
        "credit": "https://t.me/paglu_dev"
    })

@app.route('/health', methods=['GET'])
def health():
    logger.info("📍 Health check")
    tokens = load_tokens()
    valid_count = sum(1 for t in tokens if not is_token_expired(t.get('token', '')))
    
    return jsonify({
        'status': 'healthy' if valid_count > 0 else 'unhealthy',
        'total_tokens': len(tokens),
        'valid_tokens': valid_count
    }), 200 if valid_count > 0 else 500

@app.route('/token-info', methods=['GET'])
def token_info():
    logger.info("📍 Token info requested")
    tokens = load_tokens()
    
    if not tokens:
        logger.warning("⚠️ No tokens available")
        return jsonify({"error": "No tokens", "total_tokens": 0}), 500
    
    info_list = []
    valid_count = 0
    
    for idx, token_obj in enumerate(tokens):
        token = token_obj.get('token', '')
        
        if not token:
            info_list.append({"index": idx, "status": "❌ EMPTY"})
            continue
        
        info = get_token_info(token)
        if not info:
            info_list.append({"index": idx, "status": "❌ INVALID"})
            continue
        
        exp_time = info.get('exp', 0)
        current_time = int(time.time())
        is_expired = current_time > exp_time
        hours_left = (exp_time - current_time) / 3600
        
        status = "❌ EXPIRED" if is_expired else "✅ VALID"
        info_list.append({
            "index": idx,
            "status": status,
            "account_id": info.get('account_id'),
            "hours_left": round(hours_left, 2)
        })
        
        if not is_expired:
            valid_count += 1
    
    logger.info(f"✅ Token info: {valid_count}/{len(tokens)} valid")
    
    return jsonify({
        "total_tokens": len(tokens),
        "valid_tokens": valid_count,
        "tokens": info_list
    })

@app.route('/like', methods=['GET'])
def handle_like():
    uid = request.args.get("uid", "").strip()
    server_name = request.args.get("server_name", "IND").upper()
    
    logger.info(f"🎯 LIKE REQUEST: UID={uid}, Server={server_name}")
    
    # Validate input
    if not uid or not uid.isdigit():
        logger.warning(f"⚠️ Invalid UID: {uid}")
        return jsonify({
            "error": "Invalid UID - must be numeric",
            "status": 0
        }), 400
    
    try:
        # ===== STEP 1: LOAD TOKENS =====
        logger.info("Step 1: Loading tokens...")
        tokens = load_tokens()
        
        if not tokens:
            logger.error("❌ No tokens available!")
            return jsonify({
                "error": "No tokens available in tokens.json",
                "status": 0
            }), 500
        
        logger.info(f"✅ Loaded {len(tokens)} tokens")
        
        # ===== STEP 2: FIND VALID TOKEN =====
        logger.info("Step 2: Finding valid token...")
        valid_token = None
        
        for idx, t in enumerate(tokens):
            token = t.get('token', '')
            
            if not token:
                logger.debug(f"Token #{idx}: Empty")
                continue
            
            if is_token_expired(token):
                logger.debug(f"Token #{idx}: Expired")
                continue
            
            valid_token = token
            logger.info(f"✅ Using token #{idx}")
            break
        
        if not valid_token:
            logger.error("❌ All tokens are expired or invalid!")
            return jsonify({
                "error": "All tokens expired - please refresh tokens",
                "status": 0
            }), 400
        
        # ===== STEP 3: ENCRYPT UID =====
        logger.info("Step 3: Encrypting UID...")
        encrypted_uid = enc(uid)
        
        if not encrypted_uid:
            logger.error("❌ Encryption failed!")
            return jsonify({
                "error": "Failed to encrypt UID",
                "status": 0
            }), 500
        
        logger.info(f"✅ UID encrypted: {len(encrypted_uid)} chars")
        
        # ===== STEP 4: GET PLAYER INFO (BEFORE) =====
        logger.info("Step 4: Fetching player info (BEFORE)...")
        before = make_request(encrypted_uid, server_name, valid_token)
        
        if before is None:
            logger.error("❌ Failed to fetch player info!")
            return jsonify({
                "error": "Failed to fetch player info - UID may not exist or API error",
                "status": 0
            }), 500
        
        logger.info("✅ Player info fetched")
        
        # ===== STEP 5: PARSE BEFORE DATA =====
        logger.info("Step 5: Parsing player data...")
        try:
            data_before = json.loads(MessageToJson(before))
            account_info = data_before.get('AccountInfo', {})
            
            before_like = int(account_info.get('Likes', 0) or 0)
            player_uid = int(account_info.get('UID', 0) or 0)
            player_name = str(account_info.get('PlayerNickname', 'Unknown'))
            player_level = int(account_info.get('Level', 0) or 0)
            
            logger.info(f"✅ Player: {player_name} (UID: {player_uid}, Level: {player_level})")
            logger.info(f"   Likes before: {before_like}")
            
            if player_uid == 0:
                logger.error(f"❌ Invalid UID returned: {player_uid}")
                return jsonify({
                    "error": "Invalid UID - player not found",
                    "status": 0
                }), 400
            
        except Exception as parse_error:
            logger.error(f"❌ Failed to parse player data: {parse_error}", exc_info=True)
            return jsonify({
                "error": "Failed to parse player data",
                "status": 0
            }), 500
        
        # ===== STEP 6: SEND LIKE =====
        logger.info("Step 6: Sending like...")
        time.sleep(1)
        
        like_sent = send_like_request(encrypted_uid, valid_token, server_name)
        
        if not like_sent:
            logger.warning("⚠️ Like request returned false")
        else:
            logger.info("✅ Like sent")
        
        # ===== STEP 7: WAIT & GET PLAYER INFO (AFTER) =====
        logger.info("Step 7: Waiting 3 seconds before checking...")
        time.sleep(3)
        
        logger.info("Step 7b: Fetching player info (AFTER)...")
        after = make_request(encrypted_uid, server_name, valid_token)
        
        if after is None:
            logger.error("❌ Failed to fetch player info after like")
            return jsonify({
                "error": "Failed to verify like",
                "status": 2,
                "PlayerNickname": player_name,
                "UID": player_uid,
                "LikesbeforeCommand": before_like
            })
        
        logger.info("✅ Player info fetched (after)")
        
        # ===== STEP 8: PARSE AFTER DATA =====
        logger.info("Step 8: Parsing player data (after)...")
        try:
            data_after = json.loads(MessageToJson(after))
            after_like = int(data_after.get('AccountInfo', {}).get('Likes', 0) or 0)
            
            logger.info(f"   Likes after: {after_like}")
            
        except Exception as parse_error:
            logger.error(f"❌ Failed to parse after data: {parse_error}", exc_info=True)
            return jsonify({
                "error": "Failed to parse after data",
                "status": 2
            })
        
        # ===== STEP 9: CALCULATE RESULT =====
        logger.info("Step 9: Calculating result...")
        
        like_given = after_like - before_like
        status = 1 if like_given > 0 else 2
        
        logger.info(f"✅ FINAL RESULT:")
        logger.info(f"   Before: {before_like}")
        logger.info(f"   After: {after_like}")
        logger.info(f"   Given: {like_given}")
        logger.info(f"   Status: {status}")
        
        # ===== STEP 10: RETURN RESPONSE =====
        response = {
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
        }
        
        logger.info(f"✅ Returning response")
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"❌ FATAL ERROR: {e}", exc_info=True)
        return jsonify({
            "error": f"Server error: {str(e)[:100]}",
            "status": 0
        }), 500

if __name__ == '__main__':
    logger.info("=" * 70)
    logger.info("🚀 Starting Free Fire Like API v2.1")
    logger.info("=" * 70)
    
    tokens = load_tokens()
    logger.info(f"📊 Initial state: {len(tokens)} tokens loaded")
    
    app.run(debug=False, threaded=True)
