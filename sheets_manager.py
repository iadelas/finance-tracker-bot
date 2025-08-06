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
        """Add expense with correct sheet name"""
        if not self.service:
            print("❌ Google Sheets service not available")
            return False
        
        try:
            row_data = [
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                expense_data.get('description', ''),
                expense_data.get('amount', 0),
                expense_data.get('category', ''),
                expense_data.get('location', ''),
                expense_data.get('source', 'Telegram')
            ]
            
            request_body = {'values': [row_data]}
            
            print(f"🔄 Writing to sheet 'Catatan': {row_data}")
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range='Catatan!A:F',  # Changed from 'Sheet1!A:F' to 'Catatan!A:F'
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=request_body
            ).execute()
            
            print(f"✅ Added expense to Catatan: {expense_data.get('description')}")
            return True
            
        except Exception as e:
            print(f"❌ Error adding to sheet: {e}")
            return False

    def get_monthly_summary(self):
        """Get current month expense summary from Catatan sheet"""
        if not self.service:
            return "Google Sheets not available"
        
        try:
            # Get all data from Catatan sheet
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range='Catatan!A:F'  # Changed from 'Sheet1!A:F'
            ).execute()
            
            rows = result.get('values', [])
            if len(rows) <= 1:
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

    def test_direct_write(self):
        """Test direct write to verify permissions"""
        try:
            # Simple test write
            test_data = [['TEST', datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'API_TEST']]
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range='Sheet1!A:C',
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': test_data}
            ).execute()
            
            print(f"✅ Direct test successful: {result.get('updates', {})}")
            return True
            
        except Exception as e:
            print(f"❌ Direct test failed: {e}")
            return False
