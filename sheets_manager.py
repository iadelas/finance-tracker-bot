import json
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from config import GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE

class SheetsManager:
    def __init__(self):
        self.sheet_id = GOOGLE_SHEET_ID
        self.service = self._get_service()
        
        # Test permissions on startup
        if self.service:
            self.test_sheet_permissions()
    
    def _get_service(self):
        """Initialize Google Sheets service with proper scopes"""
        try:
            # Use comprehensive scopes
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive.file'
            ]
            
            credentials = Credentials.from_service_account_file(
                GOOGLE_CREDENTIALS_FILE,
                scopes=scopes
            )
            
            service = build('sheets', 'v4', credentials=credentials)
            print("✅ Google Sheets service initialized")
            return service
            
        except FileNotFoundError:
            print(f"❌ Credentials file not found: {GOOGLE_CREDENTIALS_FILE}")
            return None
        except Exception as e:
            print(f"❌ Sheets service error: {e}")
            return None
    
    def test_sheet_permissions(self):
        """Test sheet access permissions"""
        try:
            sheet_metadata = self.service.spreadsheets().get(
                spreadsheetId=self.sheet_id
            ).execute()
            
            title = sheet_metadata.get('properties', {}).get('title', 'Unknown')
            print(f"✅ Sheet access successful: {title}")
            return True
            
        except Exception as e:
            print(f"❌ Sheet permissions test failed: {e}")
            print("💡 Make sure to share your Google Sheet with the service account email")
            return False
    
    def add_expense(self, expense_data):
        """Add expense to Google Sheet with better error handling"""
        if not self.service:
            print("❌ Google Sheets service not available")
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
            
            print(f"✅ Added expense to sheet: {expense_data.get('description')}")
            return True
            
        except Exception as e:
            print(f"❌ Error adding to sheet: {e}")
            print(f"📊 Attempted data: {row_data}")
            return False
    
    def get_monthly_summary(self):
        """Get current month expense summary"""
        if not self.service:
            return "Google Sheets not available"
        
        try:
            # Get all data from Sheet1
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range='Sheet1!A:F'
            ).execute()
            
            rows = result.get('values', [])
            if len(rows) <= 1:  # Only headers or empty
                return "📊 **Ringkasan Bulan Ini:**\nBelum ada data pengeluaran"
            
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
                    except (ValueError, IndexError):
                        continue
            
            return f"📊 **Ringkasan Bulan Ini:**\n💰 Total: Rp {total_amount:,.0f}\n📝 Transaksi: {count}"
            
        except Exception as e:
            print(f"❌ Error getting summary: {e}")
            return f"❌ Error getting summary: {str(e)}"
