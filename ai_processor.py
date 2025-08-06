import google.generativeai as genai
import json
import re
from config import GEMINI_API_KEY
from utils import DateUtils, CategoryUtils

class AIProcessor:
    def __init__(self, sheets_manager=None):
        if not GEMINI_API_KEY:
            print("❌ GEMINI_API_KEY not found!")
            return
        
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.sheets_manager = sheets_manager
        print("✅ Gemini AI initialized with gemini-1.5-flash")
    
    def _get_available_categories(self):
        """Get current available categories from sheet"""
        if self.sheets_manager:
            return self.sheets_manager.get_categories()
        else:
            # Fallback if no sheets manager available
            return ['Food & Dining', 'Transportation', 'Shopping & Retail', 'Utilities & Bills',
                    'Health & Medical', 'Entertainment & Recreation', 'Education & Learning',
                    'Personal Care & Beauty', 'Housing & Rent', 'Others']

    def parse_expense_text(self, text, message_date=None, user_name=None):
        """Parse expense text with dynamic categories"""
        if not hasattr(self, 'model'):
            return {'error': 'Gemini API not initialized'}

        try:
            # Get current categories from sheet
            available_categories = self._get_available_categories()
            categories_str = ", ".join(available_categories)
            
            processed_text = self._preprocess_date_context(text, message_date)

            prompt = f"""
Extract expense information from this Indonesian text: "{text}"

Context: Message sent on {message_date.strftime('%A, %Y-%m-%d') if message_date else 'unknown date'}

Return JSON format:
{{
    "description": "brief description (capitalize first letter)",
    "amount": numeric_amount,
    "location": "store/place name (capitalize first letter)",
    "category": "one of: {categories_str}",
    "date": "YYYY-MM-DD format if specific date mentioned, otherwise null"
}}

IMPORTANT: The category MUST be exactly one of these options: {categories_str}

Date extraction rules:
- "kemarin" = yesterday from context date
- "hari ini" or "tadi" = context date
- "senin", "selasa", etc. = most recent occurrence of that weekday
- "15/8" = 15th August current year
- "tanggal 20" = 20th of current month
- If no date mentioned, return null

Rules:
- Description and location MUST start with uppercase letter
- Amount should be numeric only (convert "ribu"->*1000, "k"->*1000)
- Category must be one of the available categories listed above

Examples:
- "kemarin beli ayam 25ribu" → {{"category": "Food & Dining"}}
- "bensin motor 50rb" → {{"category": "Transportation"}}
- "bayar listrik 200k" → {{"category": "Utilities & Bills"}}
"""

            response = self.model.generate_content(prompt)
            
            # Parse JSON from response
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                expense_data = json.loads(json_match.group())
                
                # Validate category against available categories
                if expense_data.get('category') not in available_categories:
                    expense_data['category'] = self._smart_categorize_fallback(
                        text, expense_data.get('location', ''), available_categories
                    )
                
                # Ensure proper capitalization
                if expense_data.get('description'):
                    expense_data['description'] = expense_data['description'].capitalize()
                if expense_data.get('location'):
                    expense_data['location'] = expense_data['location'].capitalize()

                # Enhanced transaction date logic
                transaction_date = self._determine_transaction_date(
                    ai_extracted_date=expense_data.get('date'),
                    message_date=message_date,
                    text=text
                )
                
                expense_data['transaction_date'] = transaction_date
                expense_data['input_by'] = user_name or 'Unknown'
                
                print(f"✅ Parsed expense with dynamic category: {expense_data}")
                return expense_data
            else:
                return self._fallback_parse(text, message_date, user_name)

        except Exception as e:
            print(f"❌ Gemini API error: {e}")
            return self._fallback_parse(text, message_date, user_name)
    
    def _smart_categorize_fallback(self, text, location, available_categories):
        """Use CategoryUtils for smart categorization"""
        return CategoryUtils.match_category_by_keywords(text, location, available_categories)
    
    def _determine_transaction_date(self, ai_extracted_date, message_date, text):
        """Use DateUtils for enhanced date parsing"""
        if ai_extracted_date and ai_extracted_date != "null":
            return ai_extracted_date
        
        return DateUtils.parse_indonesian_date(text, message_date)
    
    def _preprocess_date_context(self, text, message_date):
        """Add helpful context for AI date understanding"""
        if not message_date:
            return text
        
        context_info = f"[Context: Today is {message_date.strftime('%A, %B %d, %Y')}] "
        return context_info + text
    
    def _fallback_parse(self, text, message_date, user_name):
        """Enhanced fallback with same date logic"""
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
        
        # Category detection
        category = 'Other'
        if any(word in text.lower() for word in ['makan', 'beli', 'food', 'goreng']):
            category = 'Food'
        elif any(word in text.lower() for word in ['bensin', 'grab', 'gojek']):
            category = 'Transport'
        
        # Use the same enhanced date logic
        transaction_date = self._determine_transaction_date(None, message_date, text)
        
        return {
            'description': text[:50].capitalize(),
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
