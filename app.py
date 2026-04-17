
from flask import Flask, request, Response
import requests
import json
import os

app = Flask(__name__)

# ============================================================
# SECURE CONFIGURATION - READ FROM ENVIRONMENT VARIABLES
# ============================================================

AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID")

# Check if credentials are missing
if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
    print("ERROR: Missing Airtable credentials. Set AIRTABLE_API_KEY and AIRTABLE_BASE_ID in environment variables.")

# Table names
TABLE_FARMERS = "Farmers"
TABLE_DEPOTS = "Depots"
TABLE_DELIVERIES = "Deliveries"
TABLE_PRODUCTS = "Products"

# ============================================================
# USSD MENU HANDLER
# ============================================================

# In-memory session storage (for MVP - use Redis for production)
sessions = {}

@app.route('/ussd', methods=['POST', 'GET'])
def ussd():
    # Get parameters from Africa's Talking
    phoneNumber = request.values.get("phoneNumber", "").strip()  # .strip() removes spaces
    text = request.values.get("text", "")
    sessionId = request.values.get("sessionId", "")
    
    print(f"Phone: '{phoneNumber}'")
    print(f"Text: '{text}'")
    print(f"Session: {sessionId}")
    
    # Parse user input
    user_input = text.split('*') if text else []
    
    # Get farmer from Airtable
    farmer = get_farmer_by_phone(phoneNumber)
    
    # Main menu (first visit or text is empty)
    if text == "":
        response = "CON Welcome to AgriKwacha. Your farming payment platform. "
        response += "1. Register Delivery. 2. My Payments. 3. Confirm Delivery. 4. Help. 0. Exit"
        return send_response(response)
    
    # Handle menu options
    main_option = user_input[0]
    
    # OPTION 1: Register Delivery
    if main_option == "1":
        return handle_delivery_registration(phoneNumber, farmer, user_input, len(user_input), sessionId)
    
    # OPTION 2: My Payments
    elif main_option == "2":
        return handle_my_payments(phoneNumber, farmer)
    
    # OPTION 3: Confirm Delivery
    elif main_option == "3":
        return handle_confirm_delivery(phoneNumber, farmer, user_input, len(user_input), sessionId)
    
    # OPTION 4: Help
    elif main_option == "4":
        response = "CON Help. 1. How it works. 2. Contact support. 3. FAQ. 0. Back"
        return send_response(response)
    
    # OPTION 0: Exit
    elif main_option == "0":
        response = "END Thank you for using AgriKwacha. Goodbye."
        return send_response(response)
    
    # Invalid option
    else:
        response = "END Invalid option. Please try again."
        return send_response(response)

# ============================================================
# HANDLE DELIVERY REGISTRATION (Menu 1)
# ============================================================

def handle_delivery_registration(phoneNumber, farmer, user_input, level, sessionId):
    # Check if farmer is registered
    if not farmer:
        response = "END You are not registered. Please contact AgriKwacha support to register."
        return send_response(response)
    
    # Get or create session
    session = sessions.get(sessionId, {"step": "product"})
    
    # Step 1: Select product
    if session["step"] == "product":
        if level == 1:
            response = "CON Select product. 1. Maize. 2. Soya Beans. 3. Cattle. 4. Pigs. 5. Sunflower. 6. Tobacco. 0. Back"
            sessions[sessionId] = {"step": "product"}
            return send_response(response)
        else:
            product_map = {
                "1": "Maize", "2": "Soya Beans", "3": "Cattle",
                "4": "Pigs", "5": "Sunflower", "6": "Tobacco"
            }
            product = product_map.get(user_input[1])
            if not product:
                response = "END Invalid product selection. Please try again."
                return send_response(response)
            sessions[sessionId] = {"step": "depot", "product": product}
            return handle_delivery_registration(phoneNumber, farmer, ["2"], 1, sessionId)
    
    # Step 2: Select depot
    elif session["step"] == "depot":
        if level == 1:
            depots = get_depots()
            if not depots:
                response = "END No depots available. Please contact support."
                return send_response(response)
            
            menu = "CON Select depot. "
            for i, depot in enumerate(depots):
                menu += f"{i+1}. {depot['fields'].get('Depot Name', 'Depot')}. "
            menu += "0. Back"
            sessions[sessionId] = {"step": "depot", "product": session["product"]}
            return send_response(menu)
        else:
            depot_index = int(user_input[1]) - 1
            depots = get_depots()
            if depot_index < 0 or depot_index >= len(depots):
                response = "END Invalid depot selection."
                return send_response(response)
            
            selected_depot = depots[depot_index]
            sessions[sessionId] = {
                "step": "confirm",
                "product": session["product"],
                "depot_name": selected_depot['fields'].get('Depot Name', 'Depot'),
                "depot_code": selected_depot['fields'].get('Depot Code', 'DEP001')
            }
            
            response = f"CON Confirm delivery. Product: {session['product']}. Depot: {sessions[sessionId]['depot_name']}. 1. Confirm. 2. Cancel"
            return send_response(response)
    
    # Step 3: Confirm delivery
    elif session["step"] == "confirm":
        if level == 1:
            response = f"CON Confirm delivery. Product: {session['product']}. Depot: {session['depot_name']}. 1. Confirm. 2. Cancel"
            return send_response(response)
        else:
            if user_input[1] == "2":
                sessions.pop(sessionId, None)
                response = "END Delivery cancelled. Thank you."
                return send_response(response)
            elif user_input[1] == "1":
                import random
                delivery_ref = f"DLV-{random.randint(10000, 99999)}"
                create_delivery(delivery_ref, phoneNumber, farmer, session["product"], session["depot_name"], session["depot_code"])
                sessions.pop(sessionId, None)
                response = f"END Delivery registered. Ref: {delivery_ref}. Show this at the depot. You will receive an SMS when payment is ready."
                return send_response(response)
            else:
                response = "END Invalid option."
                return send_response(response)
    
    return send_response("END System error. Please try again.")

# ============================================================
# HANDLE MY PAYMENTS (Menu 2)
# ============================================================

def handle_my_payments(phoneNumber, farmer):
    if not farmer:
        response = "END You are not registered. Please contact AgriKwacha support."
        return send_response(response)
    
    # Get deliveries from Airtable
    deliveries = get_farmer_deliveries(farmer['id'])
    
    if not deliveries:
        response = f"END {farmer['fields'].get('Full Name', 'Farmer')}. No payments yet. Register a delivery to get started. Questions? Call 0977 123 456."
        return send_response(response)
    
    # Calculate total received
    total_received = 0
    last_amount = 0
    last_date = "Unknown"
    
    for delivery in deliveries[:5]:
        amount = delivery['fields'].get('Produce Value (ZMW)', 0)
        total_received += amount
        if last_amount == 0:
            last_amount = amount
            last_date = delivery['fields'].get('Date', 'Unknown')
    
    response = f"END {farmer['fields'].get('Full Name', 'Farmer')}. Last payment: ZMW {last_amount}. Date: {last_date}. Total received: ZMW {total_received}. Questions? Call 0977 123 456."
    return send_response(response)

# ============================================================
# HANDLE CONFIRM DELIVERY (Menu 3)
# ============================================================

def handle_confirm_delivery(phoneNumber, farmer, user_input, level, sessionId):
    if not farmer:
        response = "END You are not registered. Please contact AgriKwacha support."
        return send_response(response)
    
    session = sessions.get(sessionId, {"step": "enter_ref"})
    
    if session["step"] == "enter_ref":
        if level == 1:
            response = "CON Enter your delivery reference number. Example DLV-12345. 0. Back"
            sessions[sessionId] = {"step": "enter_ref"}
            return send_response(response)
        else:
            delivery_ref = user_input[1].upper()
            if delivery_ref == "0":
                sessions.pop(sessionId, None)
                response = "CON Welcome to AgriKwacha. 1. Register Delivery. 2. My Payments. 3. Confirm Delivery. 4. Help. 0. Exit"
                return send_response(response)
            
            # Find pending delivery
            pending = get_pending_delivery(delivery_ref, phoneNumber)
            if not pending:
                sessions.pop(sessionId, None)
                response = "END Delivery reference not found. Please check and try again."
                return send_response(response)
            
            sessions[sessionId] = {"step": "confirm", "delivery_ref": delivery_ref, "pending": pending}
            
            estimated_amount = estimate_amount(pending['fields'].get('Product', 'Maize'))
            response = f"CON Delivery {delivery_ref}. Product: {pending['fields'].get('Product', 'Unknown')}. You will receive: ZMW {estimated_amount}. 1. Confirm. 2. Dispute"
            return send_response(response)
    
    elif session["step"] == "confirm":
        if level == 1:
            pending = session["pending"]
            estimated_amount = estimate_amount(pending['fields'].get('Product', 'Maize'))
            response = f"CON Delivery {session['delivery_ref']}. Product: {pending['fields'].get('Product', 'Unknown')}. You will receive: ZMW {estimated_amount}. 1. Confirm. 2. Dispute"
            return send_response(response)
        else:
            if user_input[1] == "2":
                mark_delivery_disputed(session["delivery_ref"])
                sessions.pop(sessionId, None)
                response = "END Thank you. Your dispute has been recorded. We will contact you within 24 hours."
                return send_response(response)
            elif user_input[1] == "1":
                confirm_delivery(session["delivery_ref"], farmer, session["pending"])
                sessions.pop(sessionId, None)
                response = f"END Thank you. Your payment is being processed today. You will receive an SMS when complete."
                return send_response(response)
            else:
                response = "END Invalid option."
                return send_response(response)
    
    return send_response("END System error. Please try again.")

# ============================================================
# AIRTABLE API FUNCTIONS
# ============================================================

def call_airtable(endpoint, method="GET", data=None):
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
        print("ERROR: Airtable credentials not configured")
        return None
    
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{endpoint}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        elif method == "PATCH":
            response = requests.patch(url, headers=headers, json=data)
        else:
            return None
        
        return response.json()
    except Exception as e:
        print(f"Airtable API error: {e}")
        return None

def get_farmer_by_phone(phoneNumber):
    # Remove any spaces from the phone number
    phoneNumber = phoneNumber.strip()
    filter_formula = f'{{Phone (MSISDN)}} = "{phoneNumber}"'
    result = call_airtable(f"Farmers?filterByFormula={filter_formula}")
    
    if result and result.get('records'):
        return result['records'][0]
    return None

def get_depots():
    result = call_airtable("Depots")
    return result.get('records', []) if result else []

def get_farmer_deliveries(farmer_id):
    filter_formula = f'{{Farmer ID}} = "{farmer_id}"'
    result = call_airtable(f"Deliveries?filterByFormula={filter_formula}&sort[0][field]=Date&sort[0][direction]=desc")
    return result.get('records', []) if result else []

def get_pending_delivery(delivery_ref, phoneNumber):
    phoneNumber = phoneNumber.strip()
    filter_formula = f'AND({{Delivery Ref}} = "{delivery_ref}", {{Phone}} = "{phoneNumber}", {{Status}} = "Pending")'
    result = call_airtable(f"Deliveries?filterByFormula={filter_formula}")
    
    if result and result.get('records'):
        return result['records'][0]
    return None

def create_delivery(delivery_ref, phoneNumber, farmer, product, depot_name, depot_code):
    import random
    from datetime import datetime
    
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    data = {
        "records": [{
            "fields": {
                "Delivery Ref": delivery_ref,
                "Date": current_date,
                "Farmer ID": farmer['id'],
                "Farmer Name (lookup)": farmer['fields'].get('Full Name', ''),
                "Depot Code": depot_code,
                "Product": product,
                "Status": "Pending",
                "Farmer Confirmed?": "Pending",
                "Phone": phoneNumber
            }
        }]
    }
    
    result = call_airtable("Deliveries", "POST", data)
    return delivery_ref

def mark_delivery_disputed(delivery_ref):
    filter_formula = f'{{Delivery Ref}} = "{delivery_ref}"'
    result = call_airtable(f"Deliveries?filterByFormula={filter_formula}")
    
    if result and result.get('records'):
        record_id = result['records'][0]['id']
        data = {
            "records": [{
                "id": record_id,
                "fields": {
                    "Status": "Disputed",
                    "Farmer Confirmed?": "Disputed"
                }
            }]
        }
        call_airtable("Deliveries", "PATCH", data)

def confirm_delivery(delivery_ref, farmer, pending):
    from datetime import datetime
    
    filter_formula = f'{{Delivery Ref}} = "{delivery_ref}"'
    result = call_airtable(f"Deliveries?filterByFormula={filter_formula}")
    
    if result and result.get('records'):
        record_id = result['records'][0]['id']
        current_date = datetime.now().strftime('%Y-%m-%d')
        data = {
            "records": [{
                "id": record_id,
                "fields": {
                    "Status": "Confirmed",
                    "Farmer Confirmed?": "Yes",
                    "Farmer Payment Date": current_date
                }
            }]
        }
        call_airtable("Deliveries", "PATCH", data)

def estimate_amount(product):
    estimates = {
        "Maize": 5000,
        "Soya Beans": 6000,
        "Cattle": 11250,
        "Pigs": 2000,
        "Sunflower": 4000,
        "Tobacco": 6000
    }
    return estimates.get(product, 5000)

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def send_response(message):
    resp = Response(message, status=200)
    resp.headers['Content-Type'] = 'text/plain'
    return resp

@app.route('/', methods=['GET'])
def home():
    return "AgriKwacha USSD Service is running.", 200

# ============================================================
# DEBUGGING ENDPOINTS (Remove in production if desired)
# ============================================================

@app.route('/debug', methods=['GET'])
def debug_all():
    """Run all debug tests"""
    results = {}
    
    results["env_vars"] = {
        "AIRTABLE_API_KEY_set": "Yes" if AIRTABLE_API_KEY else "No",
        "AIRTABLE_BASE_ID_set": "Yes" if AIRTABLE_BASE_ID else "No",
    }
    
    if AIRTABLE_API_KEY and AIRTABLE_BASE_ID:
        url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Farmers?maxRecords=1"
        headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
        try:
            response = requests.get(url, headers=headers)
            results["airtable_connection"] = {
                "status": response.status_code,
                "success": response.status_code == 200
            }
        except Exception as e:
            results["airtable_connection"] = {"status": "error", "message": str(e)}
    
    return results

@app.route('/debug/test-ussd', methods=['GET'])
def debug_test_ussd():
    """Test if a phone number would be found"""
    phone = request.args.get("phone", "+260973355333")
    farmer = get_farmer_by_phone(phone)
    
    return {
        "phone_tested": phone,
        "farmer_found": farmer is not None,
        "farmer_name": farmer['fields'].get('Full Name') if farmer else None
    }

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)