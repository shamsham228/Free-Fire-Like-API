from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/', methods=['GET'])
def index():
    return jsonify({"status": "OK"})

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy'})

@app.route('/like', methods=['GET'])
def like():
    return jsonify({
        "status": 2,
        "message": "API under maintenance - token server down",
        "LikesGivenByAPI": 0
    })

@app.route('/token-info', methods=['GET'])
def token_info():
    return jsonify({"error": "Token server unavailable"})

if __name__ == '__main__':
    app.run()
