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

    def _get_next_id(self):
        """Generate next incremental ID"""
        if not self.service:
            return 1

        try:
            # Get all existing data to find the highest ID
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range='Catatan!A:A'  # Only get ID column
            ).execute()
            
            rows = result.get('values', [])
            
            # If no data or only headers, start with ID 1
            if len(rows) <= 1:
                return 1
            
            # Find the highest existing ID
            max_id = 0
            for row in rows[1:]:  # Skip header row
                if row and len(row) > 0:
                    try:
                        current_id = int(row[0])
                        max_id = max(max_id, current_id)
                    except (ValueError, TypeError):
                        continue
            
            return max_id + 1
            
        except Exception as e:
            print(f"❌ Error getting next ID: {e}")
            return 1

    def add_expense(self, expense_data):
        """Add expense with new 7-column structure including ID"""
        if not self.service:
            print("❌ Google Sheets service not available")
            return False

        try:
            # Generate incremental ID
            next_id = self._get_next_id()
            
            # Updated row structure: ID, Transaction Date, Description, Amount, Category, Location, Input By
            row_data = [
                next_id,  # ID (auto-incremented)
                expense_data.get('transaction_date', datetime.now().strftime('%Y-%m-%d')),  # Transaction Date
                expense_data.get('description', ''),  # Description
                expense_data.get('amount', 0),  # Amount
                expense_data.get('category', 'Other'),  # Category
                expense_data.get('location', 'Unknown'),  # Location/Merchant
                expense_data.get('input_by', 'Unknown')  # Input By
            ]

            request_body = {'values': [row_data]}
            print(f"🔄 Writing to sheet 'Catatan': {row_data}")

            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range='Catatan!A:G',  # Updated range A=ID, B=Date, C=Description, D=Amount, E=Category, F=Location, G=InputBy
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body=request_body
            ).execute()

            print(f"✅ Added expense to Catatan with ID {next_id}: {expense_data.get('description')}")
            return True

        except Exception as e:
            print(f"❌ Error adding to sheet: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_monthly_summary(self):
        """Get current month expense summary with updated column structure"""
        if not self.service:
            return "Google Sheets not available"

        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range='Catatan!A:G'  # Updated range for 7 columns
            ).execute()

            rows = result.get('values', [])

            if len(rows) <= 1:
                return "📊 **Ringkasan Bulan Ini:**\nBelum ada data pengeluaran"

            current_month = datetime.now().strftime("%Y-%m")
            total_amount = 0
            count = 0

            for row in rows[1:]:  # Skip headers
                if len(row) >= 4:  # Need at least ID, Date, Description, Amount
                    try:
                        # Transaction date is now in column B (index 1)
                        transaction_date = row[1] if len(row) > 1 else ''
                        # Amount is now in column D (index 3)
                        amount = float(row[3]) if len(row) > 3 else 0
                        
                        if transaction_date.startswith(current_month):
                            total_amount += amount
                            count += 1
                    except (ValueError, IndexError):
                        continue

            return f"📊 **Ringkasan Bulan Ini:**\n💰 Total: Rp {total_amount:,.0f}\n📝 Transaksi: {count}"

        except Exception as e:
            print(f"❌ Error getting summary: {e}")
            return f"❌ Error getting summary: {str(e)}"

    def get_expense_by_id(self, expense_id):
        """Get specific expense by ID - useful for future features"""
        if not self.service:
            return None

        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range='Catatan!A:G'
            ).execute()

            rows = result.get('values', [])

            for row in rows[1:]:  # Skip headers
                if row and len(row) > 0:
                    try:
                        if int(row[0]) == expense_id:
                            return {
                                'id': int(row[0]),
                                'transaction_date': row[1] if len(row) > 1 else '',
                                'description': row[2] if len(row) > 2 else '',
                                'amount': float(row[3]) if len(row) > 3 else 0,
                                'category': row[4] if len(row) > 4 else '',
                                'location': row[5] if len(row) > 5 else '',
                                'input_by': row[6] if len(row) > 6 else ''
                            }
                    except (ValueError, TypeError, IndexError):
                        continue

            return None

        except Exception as e:
            print(f"❌ Error getting expense by ID: {e}")
            return None
        
    def get_categories(self):
        """Get available categories from m_category sheet"""
        if not self.service:
            # Fallback categories if sheet is unavailable
            return ['Food & Dining', 'Transportation', 'Shopping & Retail', 'Utilities & Bills', 
                    'Health & Medical', 'Entertainment & Recreation', 'Education & Learning',
                    'Personal Care & Beauty', 'Housing & Rent', 'Others']
        
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range='m_category!A:A'
            ).execute()
            
            rows = result.get('values', [])
            
            if len(rows) <= 1:
                print("⚠️ No categories found in m_category sheet, using defaults")
                return ['Food & Dining', 'Transportation', 'Shopping & Retail', 'Utilities & Bills',
                        'Health & Medical', 'Entertainment & Recreation', 'Education & Learning', 
                        'Personal Care & Beauty', 'Housing & Rent', 'Others']
            
            # Extract categories (skip header row)
            categories = [row[0] for row in rows[1:] if row and len(row) > 0]
            print(f"✅ Loaded {len(categories)} categories from m_category sheet")
            return categories
            
        except Exception as e:
            print(f"❌ Error getting categories: {e}")
            # Return fallback categories
            return ['Food & Dining', 'Transportation', 'Shopping & Retail', 'Utilities & Bills',
                    'Health & Medical', 'Entertainment & Recreation', 'Education & Learning',
                    'Personal Care & Beauty', 'Housing & Rent', 'Others']

