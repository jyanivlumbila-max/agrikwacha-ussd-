from flask import Flask, request, Response
import requests
import json
import os
from datetime import datetime
import random

app = Flask(__name__)

# ============================================================
# AIRTABLE CONFIGURATION
# ============================================================

AIRTABLE_API_KEY = os.environ.get("AIRTABLE_API_KEY", "")
AIRTABLE_BASE_ID = os.environ.get("AIRTABLE_BASE_ID", "")

# Table names
TABLE_FARMERS = "Farmers"
TABLE_DEPOTS = "Depots"
TABLE_DELIVERIES = "Deliveries"

# In-memory session storage
sessions = {}

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

# ============================================================
# FARMER FUNCTIONS
# ============================================================

def get_farmer_by_phone(phoneNumber):
    """Find farmer by phone number in Airtable"""
    phoneNumber = phoneNumber.strip()
    print(f"Looking up phone: '{phoneNumber}'")
    
    result = call_airtable(f"{TABLE_FARMERS}?maxRecords=100")
    
    if result and result.get('records'):
        for record in result['records']:
            fields = record.get('fields', {})
            # Try to find phone field (handles line break in field name)
            phone_value = None
            for key in fields.keys():
                if 'Phone' in key or 'MSISDN' in key:
                    phone_value = fields[key]
                    break
            
            if phone_value and str(phone_value).strip() == phoneNumber:
                print(f"Found farmer: {fields.get('Full Name', 'Unknown')}")
                return record
    
    print("No farmer found")
    return None

def get_farmer_deliveries(farmer_id):
    """Get all deliveries for a farmer"""
    print(f"Getting deliveries for farmer_id: {farmer_id}")
    
    filter_formula = f'{{Farmer ID}} = "{farmer_id}"'
    result = call_airtable(f"{TABLE_DELIVERIES}?filterByFormula={filter_formula}&sort[0][field]=Date&sort[0][direction]=desc")
    
    if result and result.get('records'):
        print(f"Found {len(result['records'])} deliveries")
        return result['records']
    return []

def get_pending_delivery_by_ref(delivery_ref, farmer_id):
    """Find a pending delivery by reference"""
    filter_formula = f'AND({{Delivery Ref}} = "{delivery_ref}", {{Farmer ID}} = "{farmer_id}", {{Status}} = "Pending")'
    result = call_airtable(f"{TABLE_DELIVERIES}?filterByFormula={filter_formula}")
    
    if result and result.get('records'):
        return result['records'][0]
    return None

def confirm_delivery(delivery_ref, farmer_id):
    """Update delivery status to Confirmed"""
    filter_formula = f'{{Delivery Ref}} = "{delivery_ref}"'
    result = call_airtable(f"{TABLE_DELIVERIES}?filterByFormula={filter_formula}")
    
    if result and result.get('records'):
        record_id = result['records'][0]['id']
        current_date = datetime.now().strftime('%Y-%m-%d')
        
        data = {
            "records": [{
                "id": record_id,
                "fields": {
                    "Status": "Confirmed",
                    "Farmer Confirmed?": "Yes",
                    "Farmer Paid Date": current_date
                }
            }]
        }
        call_airtable(TABLE_DELIVERIES, "PATCH", data)
        print(f"Delivery {delivery_ref} confirmed")
        return True
    return False

def create_delivery(delivery_ref, farmer, product, depot_code, quantity_kg, produce_value):
    """Create a new delivery record"""
    current_date = datetime.now().strftime('%Y-%m-%d')
    farmer_id = farmer['fields'].get('Farmer ID', '')
    farmer_name = farmer['fields'].get('Full Name', '')
    
    data = {
        "records": [{
            "fields": {
                "Delivery Ref": delivery_ref,
                "Date": current_date,
                "Farmer ID": farmer_id,
                "Farmer Name": farmer_name,
                "Depot Code": depot_code,
                "Product": product,
                "Quantity (kg)": quantity_kg,
                "Produce Value ZMW": produce_value,
                "Status": "Pending",
                "Farmer Confirmed?": "Pending"
            }
        }]
    }
    
    call_airtable(TABLE_DELIVERIES, "POST", data)
    print(f"Delivery created: {delivery_ref}")
    return delivery_ref

# ============================================================
# DEPOT FUNCTIONS
# ============================================================

def get_all_depots():
    """Get all depots from Airtable"""
    result = call_airtable(f"{TABLE_DEPOTS}?maxRecords=50")
    
    depots = []
    if result and result.get('records'):
        for record in result['records']:
            fields = record.get('fields', {})
            depots.append({
                "id": record.get('id'),
                "code": fields.get('Depot Code', ''),
                "name": fields.get('Depot Name', 'Unknown Depot'),
                "status": fields.get('Status', 'Active')
            })
    
    print(f"Found {len(depots)} depots in Airtable")
    return depots

# ============================================================
# PRODUCT FUNCTIONS
# ============================================================

def get_products():
    """Return list of available products"""
    return [
        {"code": "1", "name": "Maize"},
        {"code": "2", "name": "Soya Beans"},
        {"code": "3", "name": "Cattle"},
        {"code": "4", "name": "Pigs"},
        {"code": "5", "name": "Sunflower"},
        {"code": "6", "name": "Tobacco"}
    ]

def calculate_produce_value(product, quantity_kg):
    """Calculate produce value based on product and quantity"""
    prices = {
        "Maize": 5.00,
        "Soya Beans": 6.00,
        "Cattle": 25.00,
        "Pigs": 20.00,
        "Sunflower": 8.00,
        "Tobacco": 20.00
    }
    price_per_kg = prices.get(product, 5.00)
    return price_per_kg * quantity_kg

# ============================================================
# USSD HANDLER
# ============================================================

@app.route('/ussd', methods=['POST', 'GET'])
def ussd():
    phoneNumber = request.values.get("phoneNumber", "").strip()
    text = request.values.get("text", "")
    sessionId = request.values.get("sessionId", "")
    
    print(f"Phone: '{phoneNumber}'")
    print(f"Text: '{text}'")
    
    user_input = text.split('*') if text else []
    level = len(user_input)
    
    farmer = get_farmer_by_phone(phoneNumber)
    
    # Main menu - VERTICAL FORMAT
    if text == "":
        response = "CON Welcome to AgriKwacha. Your farming payment platform.\n"
        response += "1. Register Delivery\n"
        response += "2. My Payments\n"
        response += "3. Confirm Delivery\n"
        response += "4. Help\n"
        response += "0. Exit"
        return send_response(response)
    
    main_option = user_input[0]
    
    # ========== OPTION 1: Register Delivery ==========
    if main_option == "1":
        if not farmer:
            response = "END You are not registered. Please contact AgriKwacha support."
            return send_response(response)
        
        # Level 1: Show products - VERTICAL FORMAT
        if level == 1:
            response = "CON Select product:\n"
            response += "1. Maize\n"
            response += "2. Soya Beans\n"
            response += "3. Cattle\n"
            response += "4. Pigs\n"
            response += "5. Sunflower\n"
            response += "6. Tobacco\n"
            response += "0. Back"
            return send_response(response)
        
        # Level 2: Product selected
        elif level == 2:
            product_map = {"1": "Maize", "2": "Soya Beans", "3": "Cattle", "4": "Pigs", "5": "Sunflower", "6": "Tobacco"}
            product = product_map.get(user_input[1], "Unknown")
            
            if product == "Unknown":
                response = "END Invalid product selection."
                return send_response(response)
            
            sessions[sessionId] = {"product": product}
            response = f"CON Enter quantity in kg for {product}.\n0. Back"
            return send_response(response)
        
        # Level 3: Quantity entered
        elif level == 3:
            try:
                quantity_kg = float(user_input[2])
                sessions[sessionId]["quantity"] = quantity_kg
                
                product = sessions[sessionId]["product"]
                estimated_value = calculate_produce_value(product, quantity_kg)
                sessions[sessionId]["estimated_value"] = estimated_value
                
                # Get depots from Airtable
                depots = get_all_depots()
                
                if depots:
                    response = "CON Select depot:\n"
                    for i, depot in enumerate(depots):
                        response += f"{i+1}. {depot['name']}\n"
                    response += "0. Back"
                else:
                    response = "END No depots available. Please contact support."
                
                return send_response(response)
            except ValueError:
                response = "END Invalid quantity. Please enter a number."
                return send_response(response)
        
        # Level 4: Depot selected
        elif level == 4:
            depots = get_all_depots()
            depot_index = int(user_input[3]) - 1
            
            if depots and 0 <= depot_index < len(depots):
                depot_name = depots[depot_index]['name']
                depot_code = depots[depot_index]['code']
            else:
                response = "END Invalid depot selection."
                return send_response(response)
            
            sessions[sessionId]["depot"] = depot_name
            sessions[sessionId]["depot_code"] = depot_code
            
            product = sessions[sessionId]["product"]
            quantity = sessions[sessionId]["quantity"]
            estimated_value = sessions[sessionId]["estimated_value"]
            
            response = f"CON Confirm delivery:\n"
            response += f"Product: {product}\n"
            response += f"Quantity: {quantity} kg\n"
            response += f"Depot: {depot_name}\n"
            response += f"Value: ZMW {estimated_value}\n"
            response += "1. Confirm\n"
            response += "2. Cancel"
            return send_response(response)
        
        # Level 5: Confirmation
        elif level == 5:
            if user_input[4] == "1":
                delivery_ref = f"DLV-{random.randint(10000, 99999)}"
                product = sessions[sessionId]["product"]
                quantity = sessions[sessionId]["quantity"]
                depot = sessions[sessionId]["depot"]
                depot_code = sessions[sessionId]["depot_code"]
                estimated_value = sessions[sessionId]["estimated_value"]
                
                create_delivery(delivery_ref, farmer, product, depot_code, quantity, estimated_value)
                
                response = f"END Delivery registered.\nRef: {delivery_ref}\nValue: ZMW {estimated_value}\nShow this ref at the depot."
            else:
                response = "END Delivery cancelled."
            
            sessions.pop(sessionId, None)
            return send_response(response)
    
    # ========== OPTION 2: My Payments ==========
    elif main_option == "2":
        if not farmer:
            response = "END You are not registered. Please contact AgriKwacha support."
            return send_response(response)
        
        farmer_name = farmer['fields'].get('Full Name', 'Farmer')
        farmer_id = farmer['fields'].get('Farmer ID', '')
        
        deliveries = get_farmer_deliveries(farmer_id)
        
        if not deliveries:
            response = f"END {farmer_name}. No deliveries found. Register a delivery using option 1."
            return send_response(response)
        
        # Get paid/confirmed deliveries
        paid_deliveries = [d for d in deliveries if d['fields'].get('Status', '') in ['Confirmed', 'Paid', 'Completed']]
        
        if not paid_deliveries:
            response = f"END {farmer_name}. No payments yet. Register a delivery using option 1."
            return send_response(response)
        
        total_received = 0
        for d in paid_deliveries:
            value = d['fields'].get('Produce Value ZMW', 0)
            if isinstance(value, (int, float)):
                total_received += value
        
        latest = paid_deliveries[0]
        latest_amount = latest['fields'].get('Produce Value ZMW', 0)
        latest_date = latest['fields'].get('Date', 'Unknown')
        latest_product = latest['fields'].get('Product', 'Unknown')
        
        response = f"END {farmer_name}.\n"
        response += f"Latest payment: ZMW {latest_amount} for {latest_product} on {latest_date}.\n"
        response += f"Total received: ZMW {total_received}.\n"
        response += "Questions? Call 0977 123 456."
        return send_response(response)
    
    # ========== OPTION 3: Confirm Delivery ==========
    elif main_option == "3":
        if not farmer:
            response = "END You are not registered. Please contact AgriKwacha support."
            return send_response(response)
        
        if level == 1:
            response = "CON Enter your delivery reference number.\nExample: DLV-12345\n0. Back"
            return send_response(response)
        
        elif level == 2:
            if user_input[1] == "0":
                response = "CON Welcome to AgriKwacha.\n1. Register Delivery\n2. My Payments\n3. Confirm Delivery\n4. Help\n0. Exit"
                return send_response(response)
            
            delivery_ref = user_input[1].upper()
            farmer_id = farmer['fields'].get('Farmer ID', '')
            pending = get_pending_delivery_by_ref(delivery_ref, farmer_id)
            
            if pending:
                product = pending['fields'].get('Product', 'Unknown')
                quantity = pending['fields'].get('Quantity (kg)', 0)
                value = pending['fields'].get('Produce Value ZMW', 0)
                
                response = f"CON Delivery {delivery_ref}:\n"
                response += f"Product: {product}\n"
                response += f"Quantity: {quantity} kg\n"
                response += f"Value: ZMW {value}\n"
                response += "1. Confirm\n"
                response += "2. Dispute"
                sessions[sessionId] = {"confirm_ref": delivery_ref}
            else:
                response = "END Delivery reference not found. Please check and try again."
            
            return send_response(response)
        
        elif level == 3:
            if user_input[2] == "1":
                confirm_ref = sessions.get(sessionId, {}).get("confirm_ref", "")
                if confirm_ref:
                    confirm_delivery(confirm_ref, farmer['fields'].get('Farmer ID', ''))
                    response = f"END Delivery {confirm_ref} confirmed.\nYour payment is being processed."
                else:
                    response = "END Confirmation failed. Please try again."
            elif user_input[2] == "2":
                response = "END Your dispute has been recorded.\nWe will contact you within 24 hours."
            else:
                response = "END Invalid option."
            
            sessions.pop(sessionId, None)
            return send_response(response)
    
    # ========== OPTION 4: Help ==========
    elif main_option == "4":
        response = "END AgriKwacha Help\nCall support: 0977 123 456"
        return send_response(response)
    
    # ========== OPTION 0: Exit ==========
    elif main_option == "0":
        response = "END Thank you for using AgriKwacha. Goodbye."
        return send_response(response)
    
    else:
        response = "END Invalid option. Please try again."
        return send_response(response)

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def send_response(message):
    """Send USSD response - preserves line breaks"""
    resp = Response(message, status=200)
    resp.headers['Content-Type'] = 'text/plain'
    return resp

@app.route('/', methods=['GET'])
def home():
    return "AgriKwacha USSD Service is running.", 200

@app.route('/health', methods=['GET'])
def health():
    return {
        "status": "healthy",
        "airtable_configured": bool(AIRTABLE_API_KEY and AIRTABLE_BASE_ID)
    }

# ============================================================
# START THE APP
# ============================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)