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
    phoneNumber = phoneNumber.strip()
    print(f"Looking up phone: '{phoneNumber}'")
    
    result = call_airtable(f"{TABLE_FARMERS}?maxRecords=100")
    
    if result and result.get('records'):
        for record in result['records']:
            fields = record.get('fields', {})
            phone_value = fields.get('Phone (MSISDN)', '')
            if str(phone_value).strip() == phoneNumber:
                print(f"Found farmer: {fields.get('Full Name', 'Unknown')}")
                return record
    
    print("No farmer found")
    return None

def get_farmer_deliveries(farmer_id):
    print(f"Getting deliveries for farmer_id: {farmer_id}")
    
    filter_formula = f'{{Farmer ID}} = "{farmer_id}"'
    result = call_airtable(f"{TABLE_DELIVERIES}?filterByFormula={filter_formula}&sort[0][field]=Date&sort[0][direction]=desc")
    
    if result and result.get('records'):
        print(f"Found {len(result['records'])} deliveries")
        return result['records']
    return []

def get_pending_delivery_by_ref(delivery_ref, farmer_id):
    filter_formula = f'AND({{Delivery Ref}} = "{delivery_ref}", {{Farmer ID}} = "{farmer_id}", {{Status}} = "Pending")'
    result = call_airtable(f"{TABLE_DELIVERIES}?filterByFormula={filter_formula}")
    
    if result and result.get('records'):
        return result['records'][0]
    return None

def confirm_delivery(delivery_ref, farmer_id):
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

def calculate_produce_value(product, quantity_kg):
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
    
    if text == "":
        response = "CON Welcome to AgriKwacha. 1. Register Delivery. 2. My Payments. 3. Confirm Delivery. 4. Help. 0. Exit"
        return send_response(response)
    
    main_option = user_input[0]
    
    # OPTION 1: Register Delivery
    if main_option == "1":
        if not farmer:
            response = "END You are not registered. Please contact AgriKwacha support."
            return send_response(response)
        
        if level == 1:
            response = "CON Select product. 1. Maize. 2. Soya Beans. 3. Cattle. 4. Pigs. 5. Sunflower. 6. Tobacco. 0. Back"
            return send_response(response)
        
        elif level == 2:
            product_map = {"1": "Maize", "2": "Soya Beans", "3": "Cattle", "4": "Pigs", "5": "Sunflower", "6": "Tobacco"}
            product = product_map.get(user_input[1], "Unknown")
            
            if product == "Unknown":
                response = "END Invalid product selection."
                return send_response(response)
            
            sessions[sessionId] = {"product": product}
            response = f"CON Enter quantity in kg for {product}. 0. Back"
            return send_response(response)
        
        elif level == 3:
            try:
                quantity_kg = float(user_input[2])
                sessions[sessionId]["quantity"] = quantity_kg
                
                product = sessions[sessionId]["product"]
                estimated_value = calculate_produce_value(product, quantity_kg)
                sessions[sessionId]["estimated_value"] = estimated_value
                
                response = "CON Select depot. 1. Zambeef Lusaka. 2. AFGRI Mkushi. 3. Mwila Mills Ndola. 0. Back"
                return send_response(response)
            except ValueError:
                response = "END Invalid quantity. Please enter a number."
                return send_response(response)
        
        elif level == 4:
            depot_map = {"1": "Zambeef Lusaka", "2": "AFGRI Mkushi", "3": "Mwila Mills Ndola"}
            depot = depot_map.get(user_input[3], "Selected Depot")
            sessions[sessionId]["depot"] = depot
            
            product = sessions[sessionId]["product"]
            quantity = sessions[sessionId]["quantity"]
            estimated_value = sessions[sessionId]["estimated_value"]
            
            response = f"CON Confirm delivery. Product: {product}. Quantity: {quantity} kg. Depot: {depot}. Value: ZMW {estimated_value}. 1. Confirm. 2. Cancel"
            return send_response(response)
        
        elif level == 5:
            if user_input[4] == "1":
                delivery_ref = f"DLV-{random.randint(10000, 99999)}"
                product = sessions[sessionId]["product"]
                quantity = sessions[sessionId]["quantity"]
                depot = sessions[sessionId]["depot"]
                estimated_value = sessions[sessionId]["estimated_value"]
                
                create_delivery(delivery_ref, farmer, product, depot, quantity, estimated_value)
                
                response = f"END Delivery registered. Ref: {delivery_ref}. Value: ZMW {estimated_value}. Show this ref at the depot."
            else:
                response = "END Delivery cancelled."
            
            sessions.pop(sessionId, None)
            return send_response(response)
    
    # OPTION 2: My Payments
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
        
        response = f"END {farmer_name}. Latest payment: ZMW {latest_amount} for {latest_product} on {latest_date}. Total received: ZMW {total_received}. Call 0977 123 456 for questions."
        return send_response(response)
    
    # OPTION 3: Confirm Delivery
    elif main_option == "3":
        if not farmer:
            response = "END You are not registered. Please contact AgriKwacha support."
            return send_response(response)
        
        if level == 1:
            response = "CON Enter your delivery reference number. Example DLV-12345. 0. Back"
            return send_response(response)
        
        elif level == 2:
            if user_input[1] == "0":
                response = "CON Welcome to AgriKwacha. 1. Register Delivery. 2. My Payments. 3. Confirm Delivery. 4. Help. 0. Exit"
                return send_response(response)
            
            delivery_ref = user_input[1].upper()
            farmer_id = farmer['fields'].get('Farmer ID', '')
            pending = get_pending_delivery_by_ref(delivery_ref, farmer_id)
            
            if pending:
                product = pending['fields'].get('Product', 'Unknown')
                quantity = pending['fields'].get('Quantity (kg)', 0)
                value = pending['fields'].get('Produce Value ZMW', 0)
                
                response = f"CON Delivery {delivery_ref}. Product: {product}. Quantity: {quantity} kg. Value: ZMW {value}. 1. Confirm. 2. Dispute"
                sessions[sessionId] = {"confirm_ref": delivery_ref}
            else:
                response = "END Delivery reference not found. Please check and try again."
            
            return send_response(response)
        
        elif level == 3:
            if user_input[2] == "1":
                confirm_ref = sessions.get(sessionId, {}).get("confirm_ref", "")
                if confirm_ref:
                    confirm_delivery(confirm_ref, farmer['fields'].get('Farmer ID', ''))
                    response = f"END Delivery {confirm_ref} confirmed. Your payment is being processed."
                else:
                    response = "END Confirmation failed. Please try again."
            elif user_input[2] == "2":
                response = "END Your dispute has been recorded. We will contact you within 24 hours."
            else:
                response = "END Invalid option."
            
            sessions.pop(sessionId, None)
            return send_response(response)
    
    # OPTION 4: Help
    elif main_option == "4":
        response = "END AgriKwacha Help. Call support: 0977 123 456"
        return send_response(response)
    
    # OPTION 0: Exit
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
    # Clean the message - remove any line breaks
    clean_message = message.replace('\n', ' ').strip()
    resp = Response(clean_message, status=200)
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