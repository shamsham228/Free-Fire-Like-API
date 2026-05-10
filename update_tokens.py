import requests
import json
import time
from datetime import datetime
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
    """Read UID and password from file"""
    try:
        with open(UIDPASS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error reading uidpass.json: {e}")
        return []

def fetch_token(uid, password):
    """Fetch token from API"""
    url = f"{API_URL}?uid={uid}&password={password}"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        token = data.get("token")
        
        if token:
            logger.info(f"✅ Token fetched for UID {uid}")
            return token
        else:
            logger.warning(f"❌ No token returned for UID {uid}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error(f"❌ Timeout fetching token for UID {uid}")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Connection error for UID {uid}")
        return None
    except Exception as e:
        logger.error(f"❌ Error fetching token for UID {uid}: {e}")
        return None

def update_token_file(token_list):
    """Update tokens.json file"""
    try:
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            json.dump(token_list, f, ensure_ascii=False, indent=4)
        logger.info(f"✅ Updated tokens.json with {len(token_list)} tokens")
        return True
    except Exception as e:
        logger.error(f"❌ Error updating tokens.json: {e}")
        return False

def main():
    logger.info("=" * 50)
    logger.info("Starting token update process...")
    logger.info("=" * 50)
    
    uidpass_list = read_uidpass()
    
    if not uidpass_list:
        logger.error("❌ No UID/password pairs found in uidpass.json")
        return
    
    logger.info(f"Found {len(uidpass_list)} UID/password pairs")
    
    new_tokens = []
    success_count = 0
    failed_count = 0
    
    for item in uidpass_list:
        uid = item.get("uid")
        password = item.get("password")
        
        if not uid or not password:
            logger.warning(f"Skipping invalid entry: {item}")
            continue
        
        logger.info(f"Fetching token for UID: {uid}...")
        token = fetch_token(uid, password)
        
        if token:
            new_tokens.append({"token": token})
            success_count += 1
            time.sleep(0.5)  # Delay between requests
        else:
            failed_count += 1
    
    logger.info("=" * 50)
    logger.info(f"Results: {success_count} successful, {failed_count} failed")
    logger.info("=" * 50)
    
    if new_tokens:
        if update_token_file(new_tokens):
            logger.info("✅ Token update completed successfully!")
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
