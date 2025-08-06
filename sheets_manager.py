import json
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from config import GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE

class SheetsManager:
    def __init__(self):
        self.sheet_id = GOOGLE_SHEET_ID
        self.service = self._get_service()
    
    def _get_service(self):
        """Initialize Google Sheets service"""
        try:
            # Use the broader spreadsheets scope
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive.file'  # Add drive access
            ]
            
            credentials = Credentials.from_service_account_file(
                GOOGLE_CREDENTIALS_FILE,
                scopes=scopes
            )
            return build('sheets', 'v4', credentials=credentials)
        except Exception as e:
            print(f"Sheets service error: {e}")
            return None
    
    def add_expense(self, expense_data):
        """Add expense to Google Sheet"""
        if not self.service:
            return False
        
        try:
            # Prepare row data
            row_data = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                expense_data.get('description', ''),
                expense_data.get('amount', 0),
                expense_data.get('category', ''),
                expense_data.get('location', ''),
                expense_data.get('source', 'Telegram')
            ]
            
            # Append to sheet
            request_body = {
                'values': [row_data]
            }
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range='Sheet1!A:F',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=request_body
            ).execute()
            
            return True
            
        except Exception as e:
            print(f"Error adding to sheet: {e}")
            return False
    
    def get_monthly_summary(self):
        """Get current month expense summary"""
        if not self.service:
            return "Google Sheets not available"
        
        try:
            # Get all data
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range='Sheet1!A:F'
            ).execute()
            
            rows = result.get('values', [])
            if len(rows) <= 1:  # Only headers
                return "No expenses recorded yet"
            
            # Calculate current month total
            current_month = datetime.now().strftime("%Y-%m")
            total_amount = 0
            count = 0
            
            for row in rows[1:]:  # Skip headers
                if len(row) >= 3 and row[0].startswith(current_month):
                    try:
                        amount = float(row[2])
                        total_amount += amount
                        count += 1
                    except ValueError:
                        continue
            
            return f"📊 **Ringkasan Bulan Ini:**\n💰 Total: Rp {total_amount:,.0f}\n📝 Transaksi: {count}"
            
        except Exception as e:
            print(f"Error getting summary: {e}")
            return "Error getting summary"
