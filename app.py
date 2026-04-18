from flask import Flask, request, Response
import requests
import json
import os

# ============================================================
# CREATE FLASK APP
# ============================================================

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
    phoneNumber = request.values.get("phoneNumber", "").strip()
    text = request.values.get("text", "")
    sessionId = request.values.get("sessionId", "")
    
    print(f"Phone: '{phoneNumber}'")
    print(f"Text: '{text}'")
    print(f"Session: {sessionId}")
    
    # Parse user input
    user_input = text.split('*') if text else []
    level = len(user_input)
    
    # Get farmer from Airtable
    farmer = get_farmer_by_phone(phoneNumber)
    
    # Main menu (first visit or text is empty)
    if text == "":
        response = "CON Welcome to AgriKwacha. Your farming payment platform. "
        response += "1. Register Delivery. 2. My Payments. 3. Confirm Delivery. 4. Help. 0. Exit"
        return send_response(response)
    
    # Get the main menu option
    main_option = user_input[0]
    
    # ========== OPTION 1: Register Delivery ==========
    if main_option == "1":
        # Level 1: Show product menu
        if level == 1:
            response = "CON Select product. 1. Maize. 2. Soya Beans. 3. Cattle. 4. Pigs. 5. Sunflower. 6. Tobacco. 0. Back"
            return send_response(response)
        
        # Level 2: Product selected, show depot menu
        elif level == 2:
            product_map = {
                "1": "Maize", "2": "Soya Beans", "3": "Cattle",
                "4": "Pigs", "5": "Sunflower", "6": "Tobacco"
            }
            product = product_map.get(user_input[1], "Unknown")
            
            # Store selected product in session
            sessions[sessionId] = {"product": product}
            
            response = "CON Select depot. 1. Zambeef Lusaka. 2. AFGRI Mkushi. 3. Mwila Mills Ndola. 0. Back"
            return send_response(response)
        
        # Level 3: Depot selected, show confirmation
        elif level == 3:
            depot_map = {
                "1": "Zambeef Lusaka",
                "2": "AFGRI Mkushi", 
                "3": "Mwila Mills Ndola"
            }
            depot = depot_map.get(user_input[2], "Unknown")
            product = sessions.get(sessionId, {}).get("product", "Unknown")
            
            response = f"CON Confirm delivery. Product: {product}. Depot: {depot}. 1. Confirm. 2. Cancel"
            return send_response(response)
        
        # Level 4: Confirmation
        elif level == 4:
            if user_input[3] == "1":
                import random
                delivery_ref = f"DLV-{random.randint(10000, 99999)}"
                response = f"END Delivery registered. Ref: {delivery_ref}. Show this at the depot."
            else:
                response = "END Delivery cancelled."
            sessions.pop(sessionId, None)
            return send_response(response)
    
    # ========== OPTION 2: My Payments ==========
    elif main_option == "2":
        print(f"=== OPTION 2 DEBUG ===")
        print(f"Phone number: '{phoneNumber}'")
        
        # Check if farmer exists
        farmer = get_farmer_by_phone(phoneNumber)
        print(f"Farmer found: {farmer is not None}")
        
        if farmer:
            print(f"Farmer ID: {farmer.get('id')}")
            name = farmer['fields'].get('Full Name', 'Farmer')
            
            # Get deliveries from Airtable
            deliveries = get_farmer_deliveries(farmer['id'])
            print(f"Deliveries found: {len(deliveries) if deliveries else 0}")
            
            if deliveries and len(deliveries) > 0:
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
                
                response = f"END {name}. Last payment: ZMW {last_amount}. Date: {last_date}. Total received: ZMW {total_received}. Questions? Call 0977 123 456."
            else:
                response = f"END {name}. No payments yet. Register a delivery to get started. Questions? Call 0977 123 456."
        else:
            response = "END You are not registered. Please contact AgriKwacha support to register."
        
        print(f"Response: {response}")
        return send_response(response)
    
    # ========== OPTION 3: Confirm Delivery ==========
    elif main_option == "3":
        if level == 1:
            response = "CON Enter your delivery reference number. Example DLV-12345. 0. Back"
            return send_response(response)
        elif level == 2:
            if user_input[1] == "0":
                response = "CON Welcome to AgriKwacha. 1. Register Delivery. 2. My Payments. 3. Confirm Delivery. 4. Help. 0. Exit"
            else:
                response = f"END Delivery {user_input[1]} confirmed. Your payment is being processed."
            return send_response(response)
    
    # ========== OPTION 4: Help ==========
    elif main_option == "4":
        response = "END For help, call AgriKwacha support at 0977 123 456."
        return send_response(response)
    
    # ========== OPTION 0: Exit ==========
    elif main_option == "0":
        response = "END Thank you for using AgriKwacha. Goodbye."
        return send_response(response)
    
    # ========== Default ==========
    else:
        response = "END Invalid option. Please try again."
        return send_response(response)

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
    phoneNumber = phoneNumber.strip()
    print(f"Looking up phone: '{phoneNumber}'")
    
    filter_formula = f'{{Phone (MSISDN)}} = "{phoneNumber}"'
    result = call_airtable(f"Farmers?filterByFormula={filter_formula}")
    
    if result and result.get('records'):
        print(f"Farmer found: {result['records'][0].get('fields', {}).get('Full Name', 'Unknown')}")
        return result['records'][0]
    else:
        print("No farmer found")
        return None

def get_depots():
    result = call_airtable("Depots")
    return result.get('records', []) if result else []

def get_farmer_deliveries(farmer_id):
    print(f"=== get_farmer_deliveries DEBUG ===")
    print(f"Searching for farmer_id: '{farmer_id}'")
    
    filter_formula = f'{{Farmer ID}} = "{farmer_id}"'
    print(f"Filter: {filter_formula}")
    
    result = call_airtable(f"Deliveries?filterByFormula={filter_formula}&sort[0][field]=Date&sort[0][direction]=desc")
    
    if result and result.get('records'):
        print(f"Found {len(result.get('records'))} deliveries")
        return result['records']
    else:
        print("No deliveries found")
        return []

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
# DEBUGGING ENDPOINTS
# ============================================================

@app.route('/debug', methods=['GET'])
def debug_all():
    results = {
        "status": "alive",
        "airtable_configured": bool(AIRTABLE_API_KEY and AIRTABLE_BASE_ID)
    }
    return results

@app.route('/debug/test-ussd', methods=['GET'])
def debug_test_ussd():
    phone = request.args.get("phone", "+260973355333")
    farmer = get_farmer_by_phone(phone)
    return {
        "phone_tested": phone,
        "farmer_found": farmer is not None,
        "farmer_name": farmer['fields'].get('Full Name') if farmer else None
    }

@app.route('/debug/deliveries', methods=['GET'])
def debug_deliveries():
    phone = request.args.get("phone", "+260973355333")
    farmer = get_farmer_by_phone(phone)
    if farmer:
        deliveries = get_farmer_deliveries(farmer['id'])
        return {
            "farmer_name": farmer['fields'].get('Full Name'),
            "deliveries_count": len(deliveries),
            "deliveries": deliveries[:10]
        }
    else:
        return {"error": "Farmer not found"}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)

@app.route('/debug/add-farmer', methods=['GET'])
def debug_add_farmer():
    phone = request.args.get("phone", "")
    name = request.args.get("name", "Test Farmer")
    
    if not phone:
        return {"error": "Please provide ?phone=+260XXXXXX"}
    
    data = {
        "records": [{
            "fields": {
                "Full Name": name,
                "Phone (MSISDN)": phone,
                "Farmer ID": f"AK-{hash(phone) % 10000}"
            }
        }]
    }
    
    result = call_airtable("Farmers", "POST", data)
    return {"result": result}