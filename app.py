from flask import Flask, request, jsonify
import os
import json
import time
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN_FILE = "tokens.json"

def load_tokens():
    try:
        if not os.path.exists(TOKEN_FILE):
            return None
        with open(TOKEN_FILE, "r") as f:
            return json.load(f)
    except:
        return None

@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "API running"})

@app.route('/health', methods=['GET'])
def health():
    tokens = load_tokens()
    if tokens:
        return jsonify({'status': 'healthy', 'tokens': len(tokens)})
    return jsonify({'status': 'unhealthy'}), 500

@app.route('/token-info', methods=['GET'])
def token_info():
    tokens = load_tokens()
    if not tokens:
        return jsonify({"error": "No tokens"}), 500
    return jsonify({"total": len(tokens), "message": "Tokens loaded"})

@app.route('/like', methods=['GET'])
def like():
    return jsonify({
        "status": 2,
        "message": "API under maintenance",
        "LikesGivenByAPI": 0
    })

if __name__ == '__main__':
    app.run()
