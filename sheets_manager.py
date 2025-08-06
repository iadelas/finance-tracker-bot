from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from config import GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE

class SheetsManager:
    def __init__(self):
        self.sheet_id = GOOGLE_SHEET_ID
        self.service = self._get_service()
        
        if self.service:
            self.test_sheet_permissions()
    
    def _get_service(self):
        """Initialize Google Sheets service"""
        try:
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
            return False
    
    def add_expense(self, expense_data):
        """Add expense with new column structure"""
        if not self.service:
            print("❌ Google Sheets service not available")
            return False
        
        try:
            # Updated row structure: Date, Description, Amount, Category, Location, Input By
            row_data = [
                expense_data.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),  # Transaction Date
                expense_data.get('description', ''),                                        # Description
                expense_data.get('amount', 0),                                             # Amount
                expense_data.get('category', 'Other'),                                     # Category
                expense_data.get('location', 'Unknown'),                                   # Location/Merchant
                expense_data.get('input_by', 'Unknown')                                    # Input By
            ]
            
            request_body = {'values': [row_data]}
            
            print(f"🔄 Writing to sheet 'Catatan': {row_data}")
            
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range='Catatan!A:F',  # A=Date, B=Description, C=Amount, D=Category, E=Location, F=InputBy
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=request_body
            ).execute()
            
            print(f"✅ Added expense to Catatan: {expense_data.get('description')}")
            return True
            
        except Exception as e:
            print(f"❌ Error adding to sheet: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def get_monthly_summary(self):
        """Get current month expense summary"""
        if not self.service:
            return "Google Sheets not available"
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range='Catatan!A:F'
            ).execute()
            
            rows = result.get('values', [])
            if len(rows) <= 1:
                return "📊 **Ringkasan Bulan Ini:**\nBelum ada data pengeluaran"
            
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
