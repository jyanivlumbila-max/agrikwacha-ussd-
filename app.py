from flask import Flask, request

app = Flask(__name__)

@app.route('/ussd', methods=['POST', 'GET'])
def ussd():
    phoneNumber = request.values.get("phoneNumber", "")
    text = request.values.get("text", "")
    
    if text == "":
        response = "CON Welcome to AgriKwacha. Your farming payment platform.\n"
        response += "1. Register Delivery\n"
        response += "2. My Payments\n"
        response += "3. Confirm Delivery\n"
        response += "4. Help\n"
        response += "0. Exit"
    else:
        response = "CON Welcome to AgriKwacha. 1.Register Delivery. 2.My Payments. 3.Confirm Delivery. 4.Help. 0.Exit"
    
    return response, 200

@app.route('/', methods=['GET'])
def home():
    return "AgriKwacha USSD Service is running.", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
