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

# Get credentials from environment variables
GOOGLE_SHEETS_CREDENTIALS = os.environ.get("GOOGLE_SHEETS_CREDENTIALS", "")
GOOGLE_SHEET_KEY = os.environ.get("GOOGLE_SHEET_KEY", "")

# Sheet/Tab names (matching your Google Sheets tabs)
TAB_FARMERS = "Farmers"
TAB_DEPOTS = "Depots"
TAB_BUYERS = "Buyers"
TAB_DELIVERIES = "Deliveries"

# Global variables
gc = None
sheet_farmers = None
sheet_depots = None
sheet_buyers = None
sheet_deliveries = None

# In-memory session storage
sessions = {}

# ============================================================
# INITIALIZE GOOGLE SHEETS
# ============================================================

def init_google_sheets():
    global gc, sheet_farmers, sheet_depots, sheet_buyers, sheet_deliveries
    
    if not GOOGLE_SHEETS_CREDENTIALS:
        print("ERROR: GOOGLE_SHEETS_CREDENTIALS environment variable not set")
        return False
    
    if not GOOGLE_SHEET_KEY:
        print("ERROR: GOOGLE_SHEET_KEY environment variable not set")
        return False
    
    try:
        # Parse the JSON credentials
        creds_dict = json.loads(GOOGLE_SHEETS_CREDENTIALS)
        
        # Define scope
        scope = ['https://spreadsheets.google.com/feeds', 
                 'https://www.googleapis.com/auth/drive']
        
        # Authorize
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        gc = gspread.authorize(creds)
        
        # Open the spreadsheet
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_KEY)
        
        # Get worksheets (tabs)
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
            sheet_buyers = spreadsheet.worksheet(TAB_BUYERS)
            print(f"✅ Found tab: {TAB_BUYERS}")
        except:
            print(f"❌ Tab '{TAB_BUYERS}' not found")
        
        try:
            sheet_deliveries = spreadsheet.worksheet(TAB_DELIVERIES)
            print(f"✅ Found tab: {TAB_DELIVERIES}")
        except:
            print(f"❌ Tab '{TAB_DELIVERIES}' not found")
        
        print("✅ Google Sheets connected successfully!")
        return True
        
    except Exception as e:
        print(f"ERROR connecting to Google Sheets: {e}")
        return False

# ============================================================
# HELPER FUNCTIONS FOR GOOGLE SHEETS
# ============================================================

def get_column_letter(col_num):
    """Convert column number to letter (1=A, 2=B, etc.)"""
    result = ""
    while col_num > 0:
        col_num -= 1
        result = chr(65 + col_num % 26) + result
        col_num //= 26
    return result

def find_row_by_value(sheet, column_name, value, header_row=1):
    """Find row number where a column contains a specific value"""
    try:
        # Get all records
        records = sheet.get_all_records()
        
        for idx, row in enumerate(records, start=header_row + 1):
            if str(row.get(column_name, '')).strip() == value:
                return idx
        return None
    except Exception as e:
        print(f"Error finding row: {e}")
        return None

# ============================================================
# FARMER FUNCTIONS
# ============================================================

def get_farmer_by_phone(phoneNumber):
    """Find farmer by Phone (MSISDN) column in Farmers tab"""
    if not sheet_farmers:
        return None
    
    phoneNumber = phoneNumber.strip()
    print(f"Looking up phone: '{phoneNumber}'")
    
    try:
        records = sheet_farmers.get_all_records()
        
        for idx, row in enumerate(records, start=2):
            sheet_phone = str(row.get('Phone (MSISDN)', '')).strip()
            if sheet_phone == phoneNumber:
                print(f"Farmer found: {row.get('Full Name', 'Unknown')}")
                return {
                    "row_num": idx,
                    "id": row.get('Farmer ID', ''),
                    "fields": {
                        "Full Name": row.get('Full Name', ''),
                        "Phone (MSISDN)": row.get('Phone (MSISDN)', ''),
                        "Farmer ID": row.get('Farmer ID', ''),
                        "NRC Number": row.get('NRC Number', ''),
                        "Province": row.get('Province', ''),
                        "District": row.get('District', ''),
                        "Nearest Depot": row.get('Nearest Depot', ''),
                        "MoMo Provider": row.get('MoMo Provider', ''),
                        "MoMo Number": row.get('MoMo Number', ''),
                        "Status": row.get('Status', '')
                    }
                }
        print("No farmer found")
        return None
    except Exception as e:
        print(f"Error getting farmer: {e}")
        return None

# ============================================================
# DEPOT FUNCTIONS
# ============================================================

def get_all_depots():
    """Get all depots from Depots tab"""
    if not sheet_depots:
        return []
    
    try:
        records = sheet_depots.get_all_records()
        depots = []
        for row in records:
            depots.append({
                "fields": {
                    "Depot Code": row.get('Depot Code', ''),
                    "Depot Name": row.get('Depot Name', ''),
                    "Buyer": row.get('Buyer', ''),
                    "Province": row.get('Province', ''),
                    "District": row.get('District', ''),
                    "Status": row.get('Status', '')
                }
            })
        return depots
    except Exception as e:
        print(f"Error getting depots: {e}")
        return []

# ============================================================
# DELIVERY FUNCTIONS
# ============================================================

def get_farmer_deliveries(farmer_id):
    """Get all deliveries for a farmer from Deliveries tab"""
    if not sheet_deliveries:
        return []
    
    print(f"Getting deliveries for farmer_id: {farmer_id}")
    
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
                        "Farmer ID": row.get('Farmer ID', ''),
                        "Farmer Name": row.get('Farmer Name', ''),
                        "Buyer Code": row.get('Buyer Code', ''),
                        "Depot Code": row.get('Depot Code', ''),
                        "Product": row.get('Product', ''),
                        "Quantity (kg)": row.get('Quantity (kg)', 0),
                        "PDP Rate (ZMW/kg)": row.get('PDP Rate (ZMW/kg)', 0),
                        "PDP Total (ZMW)": row.get('PDP Total (ZMW)', 0),
                        "Produce Price/kg": row.get('Produce Price/kg', 0),
                        "Produce Value (ZMW)": row.get('Produce Value (ZMW)', 0),
                        "Status": row.get('Status', ''),
                        "Farmer Confirmed?": row.get('Farmer Confirmed?', '')
                    }
                })
        
        # Sort by date (newest first)
        deliveries.sort(key=lambda x: x['fields'].get('Date', ''), reverse=True)
        print(f"Found {len(deliveries)} deliveries")
        return deliveries
    except Exception as e:
        print(f"Error getting deliveries: {e}")
        return []

def create_delivery(delivery_ref, phoneNumber, farmer, product, depot_name, depot_code):
    """Create a new delivery record in Deliveries tab"""
    if not sheet_deliveries:
        return delivery_ref
    
    try:
        current_date = datetime.now().strftime('%Y-%m-%d')
        farmer_id = farmer['fields'].get('Farmer ID', '')
        farmer_name = farmer['fields'].get('Full Name', '')
        
        # Default values
        pdp_rate = 0.10
        pdp_total = 0
        produce_price = 5.00
        produce_value = 0
        status = "Pending"
        farmer_confirmed = "Pending"
        
        # Add new row
        new_row = [
            delivery_ref,           # Delivery Ref
            current_date,           # Date
            farmer_id,              # Farmer ID
            farmer_name,            # Farmer Name
            "",                     # Buyer Code
            depot_code,             # Depot Code
            product,                # Product
            "",                     # Quantity (kg)
            pdp_rate,               # PDP Rate (ZMW/kg)
            pdp_total,              # PDP Total (ZMW)
            "",                     # LP Share 60%
            "",                     # Platform 25%
            "",                     # PIF 14%
            "",                     # Settlement 1%
            produce_price,          # Produce Price/kg
            produce_value,          # Produce Value (ZMW)
            "",                     # Processing Fee 0.2%
            "",                     # Invoice Total (ZMW)
            status,                 # Status
            farmer_confirmed,       # Farmer Confirmed?
            "",                     # PDP Payment Date
            "",                     # Farmer Payment Date
            "",                     # Invoice Due (Day 60)
            "",                     # Invoice Settled Date
            "",                     # Processing Fee Received?
            "",                     # Days to Settlement
            ""                      # Notes
        ]
        
        sheet_deliveries.append_row(new_row)
        print(f"✅ Delivery created: {delivery_ref} for {farmer_name}")
        return delivery_ref
    except Exception as e:
        print(f"Error creating delivery: {e}")
        return delivery_ref

def update_delivery_status(delivery_ref, status, farmer_confirmed):
    """Update delivery status in Deliveries tab"""
    if not sheet_deliveries:
        return False
    
    try:
        records = sheet_deliveries.get_all_records()
        
        for idx, row in enumerate(records, start=2):
            if str(row.get('Delivery Ref', '')).strip() == delivery_ref:
                # Update Status column (column Q - 17th column)
                status_col = get_column_letter(17)
                sheet_deliveries.update(f"{status_col}{idx}", status)
                
                # Update Farmer Confirmed column (column R - 18th column)
                confirmed_col = get_column_letter(18)
                sheet_deliveries.update(f"{confirmed_col}{idx}", farmer_confirmed)
                
                print(f"✅ Delivery {delivery_ref} updated to {status}")
                return True
        return False
    except Exception as e:
        print(f"Error updating delivery: {e}")
        return False

def get_pending_delivery_by_ref(delivery_ref, phoneNumber):
    """Find a pending delivery by reference"""
    if not sheet_deliveries:
        return None
    
    try:
        records = sheet_deliveries.get_all_records()
        
        for idx, row in enumerate(records, start=2):
            if (str(row.get('Delivery Ref', '')).strip() == delivery_ref and 
                row.get('Status', '') == "Pending"):
                return {
                    "row_num": idx,
                    "fields": {
                        "Delivery Ref": row.get('Delivery Ref', ''),
                        "Product": row.get('Product', ''),
                        "Quantity (kg)": row.get('Quantity (kg)', 0)
                    }
                }
        return None
    except Exception as e:
        print(f"Error finding pending delivery: {e}")
        return None

def estimate_product_value(product):
    """Estimate produce value based on product type"""
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
# USSD MENU HANDLER
# ============================================================

@app.route('/ussd', methods=['POST', 'GET'])
def ussd():
    # Get parameters from Africa's Talking
    phoneNumber = request.values.get("phoneNumber", "").strip()
    text = request.values.get("text", "")
    sessionId = request.values.get("sessionId", "")
    
    print(f"=== USSD REQUEST ===")
    print(f"Phone: '{phoneNumber}'")
    print(f"Text: '{text}'")
    print(f"Session: {sessionId}")
    
    # Parse user input
    user_input = text.split('*') if text else []
    level = len(user_input)
    
    # Get farmer from Google Sheets
    farmer = get_farmer_by_phone(phoneNumber)
    
    # Main menu (first visit)
    if text == "":
        response = "CON Welcome to AgriKwacha. Your farming payment platform. "
        response += "1. Register Delivery. 2. My Payments. 3. Confirm Delivery. 4. Help. 0. Exit"
        return send_response(response)
    
    # Get main option
    main_option = user_input[0]
    
    # ========== OPTION 1: Register Delivery ==========
    if main_option == "1":
        # Check if farmer is registered
        if not farmer:
            response = "END You are not registered. Please contact AgriKwacha support to register."
            return send_response(response)
        
        # Level 1: Show product menu
        if level == 1:
            response = "CON Select product. 1. Maize. 2. Soya Beans. 3. Cattle. 4. Pigs. 5. Sunflower. 6. Tobacco. 0. Back"
            return send_response(response)
        
        # Level 2: Product selected
        elif level == 2:
            product_map = {
                "1": "Maize", "2": "Soya Beans", "3": "Cattle",
                "4": "Pigs", "5": "Sunflower", "6": "Tobacco"
            }
            product = product_map.get(user_input[1], "Unknown")
            
            if product == "Unknown":
                response = "END Invalid product selection. Please try again."
                return send_response(response)
            
            sessions[sessionId] = {"product": product}
            
            # Get depots from Google Sheets
            depots = get_all_depots()
            if depots:
                response = "CON Select depot. "
                for i, depot in enumerate(depots[:5]):
                    depot_name = depot['fields'].get('Depot Name', 'Depot')
                    response += f"{i+1}. {depot_name}. "
                response += "0. Back"
            else:
                response = "CON Select depot. 1. Zambeef Lusaka. 2. AFGRI Mkushi. 3. Mwila Mills Ndola. 0. Back"
            
            return send_response(response)
        
        # Level 3: Depot selected
        elif level == 3:
            # Get depots (either from sheet or default)
            depots = get_all_depots()
            if depots:
                try:
                    idx = int(user_input[2]) - 1
                    if 0 <= idx < len(depots):
                        depot_name = depots[idx]['fields'].get('Depot Name', 'Depot')
                        depot_code = depots[idx]['fields'].get('Depot Code', '')
                    else:
                        depot_name = "Selected Depot"
                        depot_code = ""
                except:
                    depot_name = "Selected Depot"
                    depot_code = ""
            else:
                depot_map = {
                    "1": "Zambeef Lusaka",
                    "2": "AFGRI Mkushi",
                    "3": "Mwila Mills Ndola"
                }
                depot_name = depot_map.get(user_input[2], "Unknown")
                depot_code = ""
            
            product = sessions.get(sessionId, {}).get("product", "Unknown")
            sessions[sessionId]["depot"] = depot_name
            sessions[sessionId]["depot_code"] = depot_code
            
            response = f"CON Confirm delivery. Product: {product}. Depot: {depot_name}. 1. Confirm. 2. Cancel"
            return send_response(response)
        
        # Level 4: Confirmation
        elif level == 4:
            if user_input[3] == "1":
                delivery_ref = f"DLV-{random.randint(10000, 99999)}"
                product = sessions.get(sessionId, {}).get("product", "Unknown")
                depot = sessions.get(sessionId, {}).get("depot", "Unknown")
                depot_code = sessions.get(sessionId, {}).get("depot_code", "")
                
                create_delivery(delivery_ref, phoneNumber, farmer, product, depot, depot_code)
                
                response = f"END Delivery registered. Ref: {delivery_ref}. Show this at the depot. You will receive an SMS when payment is ready."
            else:
                response = "END Delivery cancelled."
            
            sessions.pop(sessionId, None)
            return send_response(response)
    
    # ========== OPTION 2: My Payments ==========
    elif main_option == "2":
        print(f"=== OPTION 2: My Payments ===")
        
        if not farmer:
            response = "END You are not registered. Please contact AgriKwacha support to register."
            return send_response(response)
        
        farmer_name = farmer['fields'].get('Full Name', 'Farmer')
        farmer_id = farmer['fields'].get('Farmer ID', '')
        
        print(f"Farmer: {farmer_name}, ID: {farmer_id}")
        
        deliveries = get_farmer_deliveries(farmer_id)
        
        if not deliveries or len(deliveries) == 0:
            response = f"END {farmer_name}. No deliveries found. Register a delivery using option 1."
            return send_response(response)
        
        # Filter for pending payments
        pending = [d for d in deliveries if d['fields'].get('Status', '') in ['Pending', 'Confirmed', 'Processing']]
        
        if not pending:
            response = f"END {farmer_name}. No pending payments. All deliveries have been paid."
            return send_response(response)
        
        total_pending = 0
        for d in pending:
            value = d['fields'].get('Produce Value (ZMW)', 0)
            if isinstance(value, (int, float)):
                total_pending += value
        
        latest = pending[0]
        latest_amount = latest['fields'].get('Produce Value (ZMW)', 0)
        latest_date = latest['fields'].get('Date', 'Unknown')
        latest_product = latest['fields'].get('Product', 'Unknown')
        
        response = f"END {farmer_name}. You have {len(pending)} pending payment(s). "
        response += f"Latest: {latest_product} - ZMW {latest_amount} on {latest_date}. "
        response += f"Total pending: ZMW {total_pending}. Call 0977 123 456 for questions."
        
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
                delivery_ref = user_input[1].upper()
                pending = get_pending_delivery_by_ref(delivery_ref, phoneNumber)
                if pending:
                    estimated_value = estimate_product_value(pending['fields'].get('Product', 'Maize'))
                    response = f"CON Delivery {delivery_ref}. Product: {pending['fields'].get('Product', 'Unknown')}. You will receive approx ZMW {estimated_value}. 1. Confirm. 2. Dispute"
                    sessions[sessionId] = {"confirm_ref": delivery_ref}
                else:
                    response = "END Delivery reference not found. Please check and try again."
            return send_response(response)
        elif level == 3:
            if user_input[2] == "1":
                confirm_ref = sessions.get(sessionId, {}).get("confirm_ref", "")
                if confirm_ref:
                    update_delivery_status(confirm_ref, "Confirmed", "Yes")
                    response = f"END Delivery {confirm_ref} confirmed. Your payment is being processed. You will receive an SMS when complete."
                else:
                    response = "END Confirmation failed. Please try again."
            elif user_input[2] == "2":
                response = "END Your dispute has been recorded. We will contact you within 24 hours."
            else:
                response = "END Invalid option."
            sessions.pop(sessionId, None)
            return send_response(response)
    
    # ========== OPTION 4: Help ==========
    elif main_option == "4":
        response = "END AgriKwacha Help. 1. Register delivery to get instant payment. 2. Check payments. 3. Call support: 0977 123 456. More info: www.agrikwacha.com"
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
# UTILITY FUNCTIONS
# ============================================================

def send_response(message):
    resp = Response(message, status=200)
    resp.headers['Content-Type'] = 'text/plain'
    return resp

@app.route('/', methods=['GET'])
def home():
    return "AgriKwacha USSD Service is running with Google Sheets.", 200

@app.route('/health', methods=['GET'])
def health():
    return {
        "status": "healthy", 
        "google_sheets_configured": bool(GOOGLE_SHEETS_CREDENTIALS and GOOGLE_SHEET_KEY),
        "farmers_tab": sheet_farmers is not None,
        "depots_tab": sheet_depots is not None,
        "deliveries_tab": sheet_deliveries is not None
    }

# ============================================================
# DEBUG ENDPOINTS
# ============================================================

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

@app.route('/debug/deliveries', methods=['GET'])
def debug_deliveries():
    phone = request.args.get("phone", "")
    if not phone:
        return {"error": "Provide ?phone=+260XXXXXX"}
    
    farmer = get_farmer_by_phone(phone)
    if not farmer:
        return {"error": "Farmer not found"}
    
    farmer_id = farmer['fields'].get('Farmer ID', '')
    deliveries = get_farmer_deliveries(farmer_id)
    
    return {
        "farmer_name": farmer['fields'].get('Full Name'),
        "farmer_id": farmer_id,
        "total_deliveries": len(deliveries),
        "deliveries": [
            {
                "ref": d['fields'].get('Delivery Ref'),
                "date": d['fields'].get('Date'),
                "product": d['fields'].get('Product'),
                "value": d['fields'].get('Produce Value (ZMW)'),
                "status": d['fields'].get('Status')
            } for d in deliveries[:10]
        ]
    }

@app.route('/debug/tabs', methods=['GET'])
def debug_tabs():
    return {
        "farmers_tab_available": sheet_farmers is not None,
        "depots_tab_available": sheet_depots is not None,
        "buyers_tab_available": sheet_buyers is not None,
        "deliveries_tab_available": sheet_deliveries is not None
    }

# ============================================================
# START THE APP
# ============================================================

if __name__ == '__main__':
    # Initialize Google Sheets on startup
    init_google_sheets()
    app.run(host='0.0.0.0', port=8080)