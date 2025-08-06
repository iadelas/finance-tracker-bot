import google.generativeai as genai
import json
import re
from datetime import datetime, timedelta
from config import GEMINI_API_KEY

class AIProcessor:
    def __init__(self):
        if not GEMINI_API_KEY:
            print("❌ GEMINI_API_KEY not found!")
            return
        
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
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
        """Smart categorization fallback using keyword matching"""
        text_lower = text.lower()
        location_lower = location.lower()
        combined = f"{text_lower} {location_lower}"
        
        # Category mapping with keywords
        category_keywords = {
            'Food & Dining': ['makan', 'food', 'nasi', 'ayam', 'sate', 'warteg', 'resto', 'cafe', 'kfc', 'mcd'],
            'Transportation': ['bensin', 'grab', 'gojek', 'ojek', 'bus', 'taxi', 'motor', 'mobil', 'pertamina'],
            'Shopping & Retail': ['beli', 'belanja', 'shop', 'mall', 'alfamart', 'indomaret', 'toko'],
            'Utilities & Bills': ['listrik', 'air', 'internet', 'pulsa', 'token', 'pln', 'telkom'],
            'Health & Medical': ['dokter', 'obat', 'sakit', 'rumah sakit', 'apotek', 'klinik'],
            'Entertainment & Recreation': ['bioskop', 'film', 'game', 'nonton', 'karaoke', 'gym'],
            'Education & Learning': ['sekolah', 'kursus', 'les', 'buku', 'kuliah'],
            'Personal Care & Beauty': ['salon', 'potong rambut', 'spa', 'kosmetik'],
            'Housing & Rent': ['sewa', 'kost', 'kontrakan', 'rumah', 'apartemen']
        }
        
        for category, keywords in category_keywords.items():
            if category in available_categories:
                if any(keyword in combined for keyword in keywords):
                    return category
        
        # Default to last category (usually Others)
        return available_categories[-1] if available_categories else 'Others'
    
    def _determine_transaction_date(self, ai_extracted_date, message_date, text):
        """Enhanced transaction date determination with Indonesian language support"""
        
        # 1. If AI extracted a specific date, use that
        if ai_extracted_date and ai_extracted_date != "null":
            return ai_extracted_date
        
        # 2. Enhanced relative date parsing for Indonesian
        if message_date and message_date.tzinfo:
            message_date = message_date.replace(tzinfo=None)
        elif not message_date:
            message_date = datetime.now()
        
        # 3. Enhanced relative date parsing for Indonesian
        text_lower = text.lower().strip()
        
        # Indonesian relative date patterns
        date_patterns = {
            # Yesterday variations
            'yesterday': ['kemarin', 'kmrn', 'yesterday', 'tadi malam'],
            
            # Today variations  
            'today': ['hari ini', 'today', 'tadi', 'barusan', 'sekarang'],
            
            # Day before yesterday
            'day_before_yesterday': ['kemarin dulu', 'lusa kemarin', 'kemarin lusa'],
            
            # Tomorrow
            'tomorrow': ['besok', 'tomorrow'],
            
            # Days of week (Indonesian)
            'monday': ['senin', 'monday'],
            'tuesday': ['selasa', 'tuesday'], 
            'wednesday': ['rabu', 'wednesday'],
            'thursday': ['kamis', 'thursday'],
            'friday': ['jumat', 'friday'],
            'saturday': ['sabtu', 'saturday'],
            'sunday': ['minggu', 'sunday'],
            
            # Time-based patterns
            'morning': ['pagi', 'morning', 'tadi pagi'],
            'afternoon': ['siang', 'afternoon', 'tadi siang'],
            'evening': ['sore', 'evening', 'tadi sore'],
            'night': ['malam', 'night', 'tadi malam']
        }
        
        # Check for explicit relative dates
        if any(word in text_lower for word in date_patterns['yesterday']):
            return (message_date - timedelta(days=1)).strftime('%Y-%m-%d')
        
        if any(word in text_lower for word in date_patterns['day_before_yesterday']):
            return (message_date - timedelta(days=2)).strftime('%Y-%m-%d')
        
        if any(word in text_lower for word in date_patterns['tomorrow']):
            return (message_date + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Check for specific days of the week
        current_weekday = message_date.weekday()  # Monday = 0, Sunday = 6
        
        for day, keywords in date_patterns.items():
            if day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
                if any(keyword in text_lower for keyword in keywords):
                    target_weekday = {
                        'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                        'friday': 4, 'saturday': 5, 'sunday': 6
                    }[day]
                    
                    # Calculate days back to reach that weekday
                    days_back = (current_weekday - target_weekday) % 7
                    if days_back == 0:  # Same day - assume they mean today
                        return message_date.strftime('%Y-%m-%d')
                    else:  # Previous occurrence of that day
                        target_date = message_date - timedelta(days=days_back)
                        return target_date.strftime('%Y-%m-%d')
        
        # Check for specific date formats in text
        date_regex_patterns = [
            # DD/MM or DD-MM (current year assumed)
            (r'\b(\d{1,2})[/-](\d{1,2})\b', '%d/%m'),
            
            # DD/MM/YY or DD/MM/YYYY
            (r'\b(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\b', '%d/%m/%Y'),
            
            # Indonesian date: "tanggal 15", "tgl 20"
            (r'(?:tanggal|tgl)\s+(\d{1,2})', 'day_only'),
            
            # Numbers with context: "15 kemarin", "20 lalu"
            (r'(\d{1,2})\s+(?:kemarin|lalu|yang lalu)', 'days_ago'),
        ]
        
        for pattern, format_type in date_regex_patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    if format_type == 'day_only':
                        # Extract day, assume current month/year
                        day = int(match.group(1))
                        if 1 <= day <= 31:
                            target_date = message_date.replace(day=day)
                            # If the day is in the future, assume previous month
                            if target_date > message_date:
                                target_date = target_date.replace(month=target_date.month-1)
                            return target_date.strftime('%Y-%m-%d')
                    
                    elif format_type == 'days_ago':
                        days_ago = int(match.group(1))
                        if days_ago <= 31:  # Reasonable range
                            target_date = message_date - timedelta(days=days_ago)
                            return target_date.strftime('%Y-%m-%d')
                    
                    elif format_type == '%d/%m':
                        day, month = int(match.group(1)), int(match.group(2))
                        if 1 <= day <= 31 and 1 <= month <= 12:
                            target_date = message_date.replace(month=month, day=day)
                            # If future date, assume previous year
                            if target_date > message_date:
                                target_date = target_date.replace(year=target_date.year-1)
                            return target_date.strftime('%Y-%m-%d')
                    
                    elif format_type == '%d/%m/%Y':
                        day, month = int(match.group(1)), int(match.group(2))
                        year = int(match.group(3))
                        
                        # Handle 2-digit years
                        if year < 100:
                            year += 2000 if year < 50 else 1900
                        
                        if 1 <= day <= 31 and 1 <= month <= 12 and 2020 <= year <= 2030:
                            return f"{year:04d}-{month:02d}-{day:02d}"
                            
                except (ValueError, AttributeError):
                    continue
        
        # 3. Time-context hints (same day but different time reference)
        time_context_same_day = ['pagi', 'siang', 'sore', 'malam', 'tadi', 'barusan']
        if any(word in text_lower for word in time_context_same_day):
            return message_date.strftime('%Y-%m-%d')
        
        # 4. Default to message date
        return message_date.strftime('%Y-%m-%d')
    
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
