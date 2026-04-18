from flask import Flask, request, Response
import requests
import json
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import random

app = Flask(__name__)

# ============================================================
# GOOGLE SHEETS CONFIGURATION
# ============================================================

GOOGLE_SHEETS_CREDENTIALS = os.environ.get("GOOGLE_SHEETS_CREDENTIALS", "")
GOOGLE_SHEET_KEY = os.environ.get("GOOGLE_SHEET_KEY", "")

TAB_FARMERS = "Farmers"
TAB_DEPOTS = "Depots"
TAB_DELIVERIES = "Deliveries"

gc = None
sheet_farmers = None
sheet_depots = None
sheet_deliveries = None
sessions = {}

# ============================================================
# INITIALIZE GOOGLE SHEETS
# ============================================================

def init_google_sheets():
    global gc, sheet_farmers, sheet_depots, sheet_deliveries
    
    if not GOOGLE_SHEETS_CREDENTIALS:
        print("ERROR: GOOGLE_SHEETS_CREDENTIALS not set")
        return False
    
    if not GOOGLE_SHEET_KEY:
        print("ERROR: GOOGLE_SHEET_KEY not set")
        return False
    
    try:
        creds_dict = json.loads(GOOGLE_SHEETS_CREDENTIALS)
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        gc = gspread.authorize(creds)
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_KEY)
        
        try:
            sheet_farmers = spreadsheet.worksheet(TAB_FARMERS)
            print(f"✅ Found tab: {TAB_FARMERS}")
        except:
            print(f"❌ Tab '{TAB_FARMERS}' not found")
        
        try:
            sheet_depots = spreadsheet.worksheet(TAB_DEPOTS)
            print(f"✅ Found tab: {TAB_DEPOTS}")
        except:
            print(f"❌ Tab '{TAB_DEPOTS}' not found")
        
        try:
            sheet_deliveries = spreadsheet.worksheet(TAB_DELIVERIES)
            print(f"✅ Found tab: {TAB_DELIVERIES}")
        except:
            print(f"❌ Tab '{TAB_DELIVERIES}' not found")
        
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

# ============================================================
# FARMER FUNCTIONS
# ============================================================

def get_farmer_by_phone(phoneNumber):
    if not sheet_farmers:
        return None
    
    phoneNumber = phoneNumber.strip()
    print(f"DEBUG get_farmer_by_phone: Looking for '{phoneNumber}'")
    
    try:
        records = sheet_farmers.get_all_records()
        print(f"DEBUG: Total farmers in sheet: {len(records)}")
        
        for idx, row in enumerate(records, start=2):
            sheet_phone = str(row.get('Phone (MSISDN)', '')).strip()
            if sheet_phone == phoneNumber:
                print(f"DEBUG: Farmer found at row {idx}: {row.get('Full Name', 'Unknown')}")
                return {
                    "row_num": idx,
                    "id": row.get('Farmer ID', ''),
                    "fields": {
                        "Full Name": row.get('Full Name', ''),
                        "Phone (MSISDN)": row.get('Phone (MSISDN)', ''),
                        "Farmer ID": row.get('Farmer ID', '')
                    }
                }
        
        print(f"DEBUG: No farmer found for phone '{phoneNumber}'")
        return None
    except Exception as e:
        print(f"DEBUG: Error in get_farmer_by_phone: {e}")
        return None

def get_farmer_deliveries(farmer_id):
    if not sheet_deliveries:
        return []
    
    print(f"DEBUG get_farmer_deliveries: Looking for farmer_id '{farmer_id}'")
    
    try:
        records = sheet_deliveries.get_all_records()
        deliveries = []
        
        for idx, row in enumerate(records, start=2):
            if str(row.get('Farmer ID', '')).strip() == farmer_id:
                deliveries.append({
                    "row_num": idx,
                    "fields": {
                        "Delivery Ref": row.get('Delivery Ref', ''),
                        "Date": row.get('Date', ''),
                        "Product": row.get('Product', ''),
                        "Produce Value (ZMW)": row.get('Produce Value (ZMW)', 0),
                        "Status": row.get('Status', '')
                    }
                })
        
        deliveries.sort(key=lambda x: x['fields'].get('Date', ''), reverse=True)
        print(f"DEBUG: Found {len(deliveries)} deliveries for farmer {farmer_id}")
        return deliveries
    except Exception as e:
        print(f"DEBUG: Error in get_farmer_deliveries: {e}")
        return []

def create_delivery(delivery_ref, phoneNumber, farmer, product, depot_name, depot_code):
    if not sheet_deliveries:
        return delivery_ref
    
    try:
        current_date = datetime.now().strftime('%Y-%m-%d')
        farmer_id = farmer['fields'].get('Farmer ID', '')
        farmer_name = farmer['fields'].get('Full Name', '')
        
        new_row = [delivery_ref, current_date, farmer_id, farmer_name, "", depot_code, 
                   product, "", 0.10, 0, "", "", "", "", 5.00, 0, "", "", "Pending", "Pending", 
                   "", "", "", "", "", "", ""]
        
        sheet_deliveries.append_row(new_row)
        print(f"✅ Delivery created: {delivery_ref}")
        return delivery_ref
    except Exception as e:
        print(f"Error creating delivery: {e}")
        return delivery_ref

def get_all_depots():
    if not sheet_depots:
        return []
    
    try:
        records = sheet_depots.get_all_records()
        depots = []
        for row in records:
            depots.append({
                "fields": {
                    "Depot Code": row.get('Depot Code', ''),
                    "Depot Name": row.get('Depot Name', '')
                }
            })
        return depots
    except Exception as e:
        print(f"Error getting depots: {e}")
        return []

def estimate_product_value(product):
    estimates = {"Maize": 5000, "Soya Beans": 6000, "Cattle": 11250, 
                 "Pigs": 2000, "Sunflower": 4000, "Tobacco": 6000}
    return estimates.get(product, 5000)

# ============================================================
# USSD HANDLER
# ============================================================

@app.route('/ussd', methods=['POST', 'GET'])
def ussd():
    phoneNumber = request.values.get("phoneNumber", "").strip()
    text = request.values.get("text", "")
    sessionId = request.values.get("sessionId", "")
    
    print(f"=== USSD REQUEST ===")
    print(f"Phone: '{phoneNumber}'")
    print(f"Text: '{text}'")
    
    user_input = text.split('*') if text else []
    level = len(user_input)
    
    # Get farmer - THIS IS THE KEY LINE
    farmer = get_farmer_by_phone(phoneNumber)
    print(f"DEBUG: farmer variable after lookup = {farmer is not None}")
    
    # Main menu
    if text == "":
        response = "CON Welcome to AgriKwacha. Your farming payment platform. "
        response += "1. Register Delivery. 2. My Payments. 3. Confirm Delivery. 4. Help. 0. Exit"
        return send_response(response)
    
    main_option = user_input[0]
    print(f"DEBUG: main_option = {main_option}")
    
    # ========== OPTION 1: Register Delivery ==========
    if main_option == "1":
        print(f"DEBUG: Entering OPTION 1")
        if not farmer:
            response = "END You are not registered. Please contact AgriKwacha support to register."
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
            response = "CON Select depot. 1. Zambeef Lusaka. 2. AFGRI Mkushi. 3. Mwila Mills Ndola. 0. Back"
            return send_response(response)
        elif level == 3:
            depot_map = {"1": "Zambeef Lusaka", "2": "AFGRI Mkushi", "3": "Mwila Mills Ndola"}
            depot = depot_map.get(user_input[2], "Unknown")
            product = sessions.get(sessionId, {}).get("product", "Unknown")
            sessions[sessionId]["depot"] = depot
            response = f"CON Confirm delivery. Product: {product}. Depot: {depot}. 1. Confirm. 2. Cancel"
            return send_response(response)
        elif level == 4:
            if user_input[3] == "1":
                delivery_ref = f"DLV-{random.randint(10000, 99999)}"
                product = sessions.get(sessionId, {}).get("product", "Unknown")
                depot = sessions.get(sessionId, {}).get("depot", "Unknown")
                create_delivery(delivery_ref, phoneNumber, farmer, product, depot, "")
                response = f"END Delivery registered. Ref: {delivery_ref}. Show this at the depot."
            else:
                response = "END Delivery cancelled."
            sessions.pop(sessionId, None)
            return send_response(response)
    
    # ========== OPTION 2: My Payments ==========
    elif main_option == "2":
        print(f"DEBUG: Entering OPTION 2")
        print(f"DEBUG: farmer = {farmer}")
        
        # IMPORTANT: Re-fetch farmer to be absolutely sure
        if not farmer:
            # Try to fetch again just in case
            farmer = get_farmer_by_phone(phoneNumber)
            print(f"DEBUG: Re-fetched farmer = {farmer is not None}")
        
        if not farmer:
            print(f"DEBUG: Farmer NOT found - sending not registered message")
            response = "END You are not registered. Please contact AgriKwacha support to register."
            return send_response(response)
        
        print(f"DEBUG: Farmer FOUND - processing payments")
        farmer_name = farmer['fields'].get('Full Name', 'Farmer')
        farmer_id = farmer['fields'].get('Farmer ID', '')
        
        print(f"DEBUG: Farmer Name: {farmer_name}, ID: {farmer_id}")
        
        deliveries = get_farmer_deliveries(farmer_id)
        print(f"DEBUG: Deliveries count: {len(deliveries) if deliveries else 0}")
        
        if not deliveries or len(deliveries) == 0:
            response = f"END {farmer_name}. No deliveries found. Register a delivery using option 1."
            return send_response(response)
        
        # Filter pending payments
        pending = [d for d in deliveries if d['fields'].get('Status', '') in ['Pending', 'Confirmed', 'Processing']]
        print(f"DEBUG: Pending payments count: {len(pending)}")
        
        if not pending:
            response = f"END {farmer_name}. No pending payments. All deliveries have been paid."
            return send_response(response)
        
        total_pending = sum(d['fields'].get('Produce Value (ZMW)', 0) for d in pending)
        latest = pending[0]
        latest_amount = latest['fields'].get('Produce Value (ZMW)', 0)
        latest_date = latest['fields'].get('Date', 'Unknown')
        latest_product = latest['fields'].get('Product', 'Unknown')
        
        response = f"END {farmer_name}. You have {len(pending)} pending payment(s). "
        response += f"Latest: {latest_product} - ZMW {latest_amount} on {latest_date}. "
        response += f"Total pending: ZMW {total_pending}. Call 0977 123 456 for questions."
        
        print(f"DEBUG: Sending response: {response}")
        return send_response(response)
    
    # ========== OPTION 3: Confirm Delivery ==========
    elif main_option == "3":
        if not farmer:
            response = "END You are not registered. Please contact AgriKwacha support to register."
            return send_response(response)
        
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
        response = "END AgriKwacha Help. Call support: 0977 123 456."
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
        "sheets_connected": sheet_farmers is not None
    }

@app.route('/debug/farmer', methods=['GET'])
def debug_farmer():
    phone = request.args.get("phone", "")
    if not phone:
        return {"error": "Provide ?phone=+260XXXXXX"}
    
    farmer = get_farmer_by_phone(phone)
    if farmer:
        return {
            "found": True,
            "name": farmer['fields'].get('Full Name'),
            "farmer_id": farmer['fields'].get('Farmer ID'),
            "phone": farmer['fields'].get('Phone (MSISDN)')
        }
    return {"found": False, "phone": phone}

if __name__ == '__main__':
    init_google_sheets()
    app.run(host='0.0.0.0', port=8080)