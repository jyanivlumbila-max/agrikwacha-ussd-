cd ~/Desktop/agrikwacha-ussd

# Update app.py with the single-line version
cat > app.py << 'EOF'
from flask import Flask, request, Response

app = Flask(__name__)

@app.route('/ussd', methods=['POST', 'GET'])
def ussd():
    response_text = "CON Welcome to AgriKwacha. Your farming payment platform. 1. Register Delivery 2. My Payments 3. Confirm Delivery 4. Help 0. Exit"
    
    resp = Response(response_text, status=200)
    resp.headers['Content-Type'] = 'text/plain'
    
    return resp

@app.route('/', methods=['GET'])
def home():
    return "AgriKwacha USSD Service is running.", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
EOF

git add app.py
git commit -m "Remove line breaks - single line response"
git push
