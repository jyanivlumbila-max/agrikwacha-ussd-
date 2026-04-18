from flask import Flask
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

app = Flask(__name__)

@app.route('/')
def home():
    return "AgriKwacha USSD Service is running."

@app.route('/test')
def test():
    # Get credentials from environment
    creds_json = os.environ.get("GOOGLE_SHEETS_CREDENTIALS", "")
    sheet_key = os.environ.get("GOOGLE_SHEET_KEY", "")
    
    if not creds_json:
        return {"error": "GOOGLE_SHEETS_CREDENTIALS not set"}
    
    if not sheet_key:
        return {"error": "GOOGLE_SHEET_KEY not set"}
    
    try:
        # Parse the JSON
        creds_dict = json.loads(creds_json)
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        gc = gspread.authorize(creds)
        
        # Open the sheet
        spreadsheet = gc.open_by_key(sheet_key)
        
        # Try to get the first worksheet
        worksheet = spreadsheet.get_worksheet(0)
        records = worksheet.get_all_records()
        
        return {
            "success": True,
            "sheet_title": spreadsheet.title,
            "total_records": len(records),
            "first_record": records[0] if records else None
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)