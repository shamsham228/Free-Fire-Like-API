import requests
import json
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Connection error for UID {uid}")
        return None
    except Exception as e:
        logger.error(f"❌ Error for UID {uid}: {e}")
        return None

def update_token_file(token_list):
    try:
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(token_list, f, ensure_ascii=False, indent=4)
        logger.info(f"✅ Updated tokens.json with {len(token_list)} tokens")
        return True
    except Exception as e:
        logger.error(f"❌ Error saving tokens: {e}")
        return False

def main():
    logger.info("=" * 60)
    logger.info("TOKEN UPDATE PROCESS STARTED")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("=" * 60)
    
    uidpass_list = read_uidpass()
    
    if not uidpass_list:
        logger.error("❌ No UID/password pairs found")
        return False
    
    logger.info(f"Found {len(uidpass_list)} accounts")
    
    new_tokens = []
    success_count = 0
    failed_count = 0
    
    for item in uidpass_list:
        uid = item.get("uid")
        password = item.get("password")
        
        if not uid or not password:
            logger.warning(f"Skipping invalid entry")
            continue
        
        token = fetch_token(uid, password)
        
        if token:
            new_tokens.append({"token": token})
            success_count += 1
        else:
            failed_count += 1
        
        time.sleep(0.5)  # Delay between requests
    
    logger.info("=" * 60)
    logger.info(f"RESULTS: {success_count} success, {failed_count} failed")
    logger.info("=" * 60)
    
    if new_tokens:
        if update_token_file(new_tokens):
            logger.info("✅ TOKEN UPDATE SUCCESSFUL")
            return True
        else:
            logger.error("❌ Failed to save tokens")
            return False
    else:
        logger.error("❌ No tokens were fetched")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
