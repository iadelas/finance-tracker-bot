import google.generativeai as genai
import json
import re
from datetime import datetime
from config import GEMINI_API_KEY

class AIProcessor:
    def __init__(self):
        if not GEMINI_API_KEY:
            print("❌ GEMINI_API_KEY not found!")
            return
        
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        print("✅ Gemini AI initialized with gemini-1.5-flash")
    
    def parse_expense_text(self, text, message_date=None, user_name=None):
        """Parse expense text with date handling and proper capitalization"""
        if not hasattr(self, 'model'):
            return {'error': 'Gemini API not initialized'}
        
        try:
            prompt = f"""
            Extract expense information from this Indonesian text: "{text}"
            
            Return JSON format:
            {{
                "description": "brief description (capitalize first letter)",
                "amount": numeric_amount,
                "location": "store/place name (capitalize first letter)",
                "category": "Food/Transport/Utilities/Shopping/Health/Entertainment/Other",
                "date": "YYYY-MM-DD format if mentioned, otherwise null"
            }}
            
            Rules:
            - Description and location MUST start with uppercase letter
            - If date is mentioned in text (like "kemarin", "tadi pagi", specific date), extract it
            - Amount should be numeric only (convert "ribu"->*1000, "k"->*1000)
            - Categories in English: Food, Transport, Utilities, Shopping, Health, Entertainment, Other
            
            Examples:
            - "beli ayam goreng gofood 4ribu" → {{"description": "Ayam goreng", "amount": 4000, "location": "Gofood", "category": "Food", "date": null}}
            - "bensin kemarin 50k di shell" → {{"description": "Bensin", "amount": 50000, "location": "Shell", "category": "Transport", "date": "2025-08-05"}}
            """
            
            response = self.model.generate_content(prompt)
            
            # Parse JSON from response
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                expense_data = json.loads(json_match.group())
                
                # Ensure proper capitalization
                if expense_data.get('description'):
                    expense_data['description'] = expense_data['description'].capitalize()
                if expense_data.get('location'):
                    expense_data['location'] = expense_data['location'].capitalize()
                
                # Handle transaction date logic
                transaction_date = self._determine_transaction_date(
                    ai_extracted_date=expense_data.get('date'),
                    message_date=message_date,
                    text=text
                )
                expense_data['transaction_date'] = transaction_date
                expense_data['input_by'] = user_name or 'Unknown'
                
                print(f"✅ Parsed expense: {expense_data}")
                return expense_data
            else:
                return self._fallback_parse(text, message_date, user_name)
                
        except Exception as e:
            print(f"❌ Gemini API error: {e}")
            return self._fallback_parse(text, message_date, user_name)
    
    def _determine_transaction_date(self, ai_extracted_date, message_date, text):
        """Determine transaction date based on priority rules"""
        # 1. If AI extracted a specific date from text, use that
        if ai_extracted_date and ai_extracted_date != "null":
            return ai_extracted_date
        
        # 2. Check for relative date indicators in text
        text_lower = text.lower()
        if message_date:
            from datetime import timedelta
            
            if any(word in text_lower for word in ['kemarin', 'yesterday']):
                yesterday = message_date - timedelta(days=1)
                return yesterday.strftime('%Y-%m-%d')
            elif any(word in text_lower for word in ['lusa', 'besok']):
                tomorrow = message_date + timedelta(days=1)
                return tomorrow.strftime('%Y-%m-%d')
        
        # 3. Default to message date
        if message_date:
            return message_date.strftime('%Y-%m-%d')
        
        # 4. Fallback to current date
        return datetime.now().strftime('%Y-%m-%d')
    
    def _fallback_parse(self, text, message_date, user_name):
        """Fallback parsing without AI"""
        import re
        
        # Extract amount using regex
        amount_patterns = [
            r'(\d+)(?:ribu|rb)',  # "4ribu" → 4000
            r'(\d+)k',            # "20k" → 20000  
            r'(\d+)(?:000)',      # "25000" → 25000
            r'(\d+)'              # fallback to any number
        ]
        
        amount = 0
        for pattern in amount_patterns:
            match = re.search(pattern, text.lower())
            if match:
                num = int(match.group(1))
                if 'ribu' in text.lower() or 'rb' in text.lower():
                    amount = num * 1000
                elif 'k' in text.lower():
                    amount = num * 1000
                else:
                    amount = num
                break
        
        # Simple category detection
        category = 'Other'
        if any(word in text.lower() for word in ['makan', 'beli', 'food', 'goreng']):
            category = 'Food'
        elif any(word in text.lower() for word in ['bensin', 'grab', 'gojek']):
            category = 'Transport'
        
        transaction_date = self._determine_transaction_date(None, message_date, text)
        
        return {
            'description': text[:50].capitalize(),  # First 50 chars, capitalized
            'amount': amount,
            'location': 'Unknown',
            'category': category,
            'transaction_date': transaction_date,
            'input_by': user_name or 'Unknown'
        }
    
    def parse_receipt_data(self, ocr_text, receipt_date, user_name):
        """Special parsing for receipt images with date priority"""
        expense_data = self.parse_expense_text(ocr_text, receipt_date, user_name)
        
        # For receipts, always use receipt date if available
        if receipt_date:
            expense_data['transaction_date'] = receipt_date.strftime('%Y-%m-%d')
        
        expense_data['source'] = 'Receipt OCR'
        return expense_data
