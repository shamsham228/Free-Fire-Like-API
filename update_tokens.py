import requests
import json
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

UIDPASS_FILE = "uidpass.json"
TOKEN_FILE = "tokens.json"
API_URL = "https://xtytdtyj-jwt.up.railway.app/token"

def read_uidpass():
    try:
        with open(UIDPASS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading uidpass.json: {e}")
        return []

def fetch_token(uid, password):
    url = f"{API_URL}?uid={uid}&password={password}"
    try:
        logger.info(f"Fetching token for UID {uid}...")
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        token = data.get("token")
        if token:
            logger.info(f"✅ Token fetched for UID {uid}")
            return token
        else:
            logger.warning(f"❌ No token for UID {uid}")
            return None
    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout for UID {uid}")
        return None
    except Exception as e:
        logger.error(f"❌ Error for UID {uid}: {e}")
        return None

def update_token_file(token_list):
    try:
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(token_list, f, ensure_ascii=False, indent=4)
        logger.info(f"✅ Saved {len(token_list)} tokens to {TOKEN_FILE}")
        return True
    except Exception as e:
        logger.error(f"❌ Error saving tokens: {e}")
        return False

def main():
    logger.info("=" * 60)
    logger.info("FREE FIRE TOKEN GENERATOR")
    logger.info("=" * 60)
    
    uidpass_list = read_uidpass()
    
    if not uidpass_list:
        logger.error("❌ No UID/password pairs in uidpass.json")
        return False
    
    logger.info(f"Found {len(uidpass_list)} accounts")
    
    new_tokens = []
    success = 0
    failed = 0
    
    for item in uidpass_list:
        uid = item.get("uid")
        password = item.get("password")
        
        if not uid or not password:
            logger.warning(f"Skipping invalid: {item}")
            continue
        
        token = fetch_token(uid, password)
        
        if token:
            new_tokens.append({"token": token})
            success += 1
        else:
            failed += 1
        
        time.sleep(0.5)
    
    logger.info("=" * 60)
    logger.info(f"Results: {success} success, {failed} failed")
    logger.info("=" * 60)
    
    if new_tokens:
        return update_token_file(new_tokens)
    else:
        logger.error("❌ No tokens generated")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
