import os
import json
import re
from datetime import datetime
from google.cloud import vision
from google.oauth2.service_account import Credentials
import google.generativeai as genai
from config import GOOGLE_CREDENTIALS_FILE, GEMINI_API_KEY
from utils import AmountUtils

class VisionProcessor:
    def __init__(self,  sheets_manager=None):

        # Store sheets_manager reference
        self.sheets_manager = sheets_manager

        """Initialize Google Vision API and Gemini AI clients"""
        # Initialize Vision API
        try:
            credentials = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE)
            self.vision_client = vision.ImageAnnotatorClient(credentials=credentials)
            print("✅ Google Vision API initialized")
        except Exception as e:
            print(f"❌ Vision API initialization failed: {e}")
            self.vision_client = None
        
        # Initialize Gemini AI
        try:
            if GEMINI_API_KEY:
                genai.configure(api_key=GEMINI_API_KEY)
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash')
                print("✅ Gemini AI initialized for receipt parsing")
            else:
                self.gemini_model = None
                print("⚠️ Gemini API key not found")
        except Exception as e:
            print(f"❌ Gemini AI initialization failed: {e}")
            self.gemini_model = None

    def extract_receipt_data(self, image_path, message_date, user_name):
        """Extract and parse receipt data using Vision API + Gemini AI"""
        if not self.vision_client:
            return {'error': 'Vision API not available'}
        
        try:
            # Extract text using Vision API
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            response = self.vision_client.document_text_detection(image=image)
            
            if response.error.message:
                raise Exception(f'Vision API error: {response.error.message}')
            
            raw_text = response.full_text_annotation.text if response.full_text_annotation else ""
            
            if not raw_text.strip():
                return {'error': 'No text found in receipt'}
            
            # Parse with Gemini AI (preferred method)
            if self.gemini_model:
                receipt_data = self._parse_with_gemini(raw_text, message_date, user_name)
                if not receipt_data.get('error'):
                    return receipt_data
            
            # Fallback to regex parsing
            return self._parse_with_regex(raw_text, message_date, user_name)
            
        except Exception as e:
            print(f"❌ Receipt processing error: {e}")
            return {'error': f'Failed to process receipt: {str(e)}'}

    def _parse_with_gemini(self, ocr_text, message_date, user_name):
        """Use Gemini AI to intelligently parse receipt OCR text"""
        try:
            # ✅ GET DYNAMIC CATEGORIES
            available_categories = self._get_available_categories()
            categories_str = "|".join(available_categories)
            
            prompt = f"""
    Analyze this Indonesian receipt OCR text and extract the correct information:

    OCR TEXT:
    {ocr_text}

    PARSING RULES:
    1. MERCHANT: Find the business/store name (usually at the top, ignore address/phone)
    2. TOTAL AMOUNT: Find the final amount paid (look for "TOTAL", "JUMLAH", "GRAND TOTAL", or largest amount at bottom)
    3. DATE: Extract transaction date (DD/MM/YYYY, DD-MM-YYYY, or "DD Month YYYY" format)
    4. IGNORE: Phone numbers, reference codes, item codes, tax IDs
    5. CATEGORY: Classify based on merchant type

    Return ONLY valid JSON:
    {{
    "merchant": "Business Name",
    "amount": numeric_amount_only,
    "date": "YYYY-MM-DD",
    "category": "one of: {categories_str}"
    }}

    IMPORTANT: The category MUST be exactly one of these options: {categories_str}

    EXAMPLES:
    - "TOTAL: 25,200" → amount: 25200
    - "ALFAMART CILANDAK" → merchant: "Alfamart Cilandak"
    - "18-03-2022" → date: "2022-03-18"
    - "BreadTalk" → category: "Food & Dining"

    Focus on accuracy. If unsure about any field, use reasonable defaults.
    """

            response = self.gemini_model.generate_content(prompt)
            
            # Extract JSON from response
            json_match = re.search(r'\{[^}]*\}', response.text, re.DOTALL)
            if not json_match:
                return {'error': 'No valid JSON in AI response'}

            ai_result = json.loads(json_match.group())
            
            # ✅ VALIDATE CATEGORY against available categories
            category = ai_result.get('category', 'Others')
            if category not in available_categories:
                # Use CategoryUtils for fallback categorization
                from utils import CategoryUtils
                category = CategoryUtils.match_category_by_keywords(
                    ocr_text, ai_result.get('merchant', ''), available_categories
                )

            # Build structured response
            receipt_data = {
                'description': f"Purchase at {ai_result.get('merchant', 'Unknown')}",
                'amount': self._clean_amount(ai_result.get('amount', 0)),
                'location': ai_result.get('merchant', 'Unknown'),
                'category': category,  # ✅ USE VALIDATED CATEGORY
                'transaction_date': ai_result.get('date') or self._normalize_datetime(message_date).strftime('%Y-%m-%d'),
                'input_by': user_name,
                'source': 'Vision API + Gemini AI'
            }

            # Ensure proper formatting
            receipt_data['description'] = receipt_data['description'].capitalize()
            receipt_data['location'] = receipt_data['location'].title()
            
            return receipt_data

        except json.JSONDecodeError as e:
            return {'error': 'Invalid AI response format'}
        except Exception as e:
            return {'error': f'AI parsing failed: {str(e)}'}


    def _parse_with_regex(self, raw_text, message_date, user_name):
        """Fallback regex-based parsing"""
        receipt_data = {
            'description': 'Receipt purchase',
            'amount': 0,
            'location': 'Unknown',
            'category': 'Other',
            'transaction_date': self._normalize_datetime(message_date).strftime('%Y-%m-%d'),
            'input_by': user_name,
            'source': 'Vision API (regex)'
        }
        
        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
        
        # Extract merchant (first meaningful line)
        for line in lines[:5]:
            if (len(line) > 3 and 
                not re.match(r'^[\d\s\-/:.,]+$', line) and
                not any(skip in line.lower() for skip in ['receipt', 'struk', 'bon', 'total'])):
                receipt_data['location'] = line.title()
                break
        
        # Extract amount (prioritize lines with total keywords)
        amounts = []
        for line in lines:
            if any(keyword in line.lower() for keyword in ['total', 'jumlah', 'grand total']):
                numbers = re.findall(r'\d{1,3}(?:[.,]\d{3})*', line)
                for num in numbers:
                    amount = self._parse_indonesian_number(num)
                    if amount and amount >= 1000:
                        amounts.append(amount)
        
        # Fallback: look for large numbers in bottom area
        if not amounts:
            bottom_lines = lines[-5:] if len(lines) > 5 else lines
            for line in bottom_lines:
                numbers = re.findall(r'\d{1,3}(?:[.,]\d{3})*', line)
                for num in numbers:
                    amount = self._parse_indonesian_number(num)
                    if amount and 1000 <= amount <= 10000000:
                        amounts.append(amount)
        
        if amounts:
            receipt_data['amount'] = max(amounts)
        
        # Basic categorization
        receipt_data['category'] = self._categorize_merchant(receipt_data['location'])
        receipt_data['description'] = f"Purchase at {receipt_data['location']}"
        
        return receipt_data

    def _clean_amount(self, amount):
        """Use AmountUtils for amount cleaning"""
        return AmountUtils.parse_indonesian_amount(str(amount))

    def _parse_indonesian_number(self, number_str):
        """Parse Indonesian number format"""
        try:
            clean_number = re.sub(r'[.,]', '', str(number_str))
            return float(clean_number)
        except (ValueError, TypeError):
            return None

    def _categorize_merchant(self, merchant_name):
        """Categorize based on merchant name using dynamic categories"""
        if self.sheets_manager:
            # Use dynamic categories from Google Sheet
            available_categories = self._get_available_categories()
            from utils import CategoryUtils
            return CategoryUtils.match_category_by_keywords(
                merchant_name, merchant_name, available_categories
            )
        else:
            # Fallback to hardcoded logic if no sheets manager
            merchant_lower = merchant_name.lower()
            
            # Food & Dining
            if any(word in merchant_lower for word in [
                'restaurant', 'resto', 'cafe', 'food', 'makan', 'warung',
                'kfc', 'mcd', 'pizza', 'bakery', 'bread', 'cake', 'starbucks',
                'dunkin', 'breadtalk', 'hokben', 'ayam', 'sate', 'nasi', 'warteg',
                'padang', 'sop', 'bakso', 'mie', 'gado', 'rendang', 'soto'
            ]):
                return 'Food & Dining'
            
            # Shopping & Retail  
            elif any(word in merchant_lower for word in [
                'mart', 'market', 'grocery', 'supermarket', 'indomaret',
                'alfamart', 'shop', 'store', 'mall', 'plaza', 'hypermart',
                'carrefour', 'giant', 'lottemart', 'ranch', 'hero', 'ace',
                'electronic', 'gramedia', 'periplus', 'uniqlo', 'zara', 'h&m'
            ]):
                return 'Shopping & Retail'
            
            # Transportation
            elif any(word in merchant_lower for word in [
                'shell', 'pertamina', 'spbu', 'gas', 'petrol', 'bensin',
                'grab', 'gojek', 'blue bird', 'silver bird', 'taxi',
                'parkir', 'parking', 'tol', 'toll', 'busway', 'transjakarta'
            ]):
                return 'Transportation'
            
            # Health & Medical
            elif any(word in merchant_lower for word in [
                'apotek', 'pharmacy', 'clinic', 'hospital', 'dokter', 'rs ',
                'rumah sakit', 'kimia farma', 'guardian', 'century',
                'klinik', 'medical', 'kesehatan', 'lab', 'laboratorium'
            ]):
                return 'Health & Medical'
            
            # Personal Care & Beauty
            elif any(word in merchant_lower for word in [
                'salon', 'barbershop', 'spa', 'massage', 'pijet', 'reflexi',
                'nail', 'facial', 'watsons', 'guardian', 'kosmetik', 'parfum',
                'kecantikan', 'perawatan', 'potong rambut', 'hair'
            ]):
                return 'Personal Care & Beauty'
            
            # Utilities & Bills
            elif any(word in merchant_lower for word in [
                'pln', 'listrik', 'telkom', 'internet', 'water', 'air',
                'indihome', 'xl', 'telkomsel', 'indosat', 'tri', 'smartfren',
                'pulsa', 'token', 'pdam', 'wifi', 'bayar', 'tagihan'
            ]):
                return 'Utilities & Bills'
            
            # Entertainment & Recreation
            elif any(word in merchant_lower for word in [
                'cinema', 'bioskop', 'xxi', 'cgv', 'karaoke', 'gym', 'fitness',
                'netflix', 'spotify', 'game', 'playstation', 'billiard',
                'bowling', 'timezone', 'amazone', 'waterboom', 'ancol'
            ]):
                return 'Entertainment & Recreation'
            
            # Education & Learning
            elif any(word in merchant_lower for word in [
                'sekolah', 'university', 'universitas', 'kampus', 'course',
                'kursus', 'les', 'bimbel', 'training', 'seminar', 'workshop',
                'gramedia', 'toko buku', 'bookstore', 'perpustakaan'
            ]):
                return 'Education & Learning'
            
            # Housing & Rent
            elif any(word in merchant_lower for word in [
                'kost', 'rental', 'sewa', 'apartment', 'apartemen', 'hotel',
                'penginapan', 'villa', 'airbnb', 'oyo', 'reddoorz', 'airy'
            ]):
                return 'Housing & Rent'
            
            # Default fallback
            else:
                return 'Others'

    def _normalize_datetime(self, dt):
        """Convert datetime to timezone-naive for consistent operations"""
        if dt is None:
            return datetime.now()
        
        if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        
        return dt
    
    def _get_available_categories(self):
        """Get current available categories from sheet"""
        if self.sheets_manager:
            return self.sheets_manager.get_categories()
        else:
            # Fallback categories if no sheets manager available
            return ['Food & Dining', 'Transportation', 'Shopping & Retail', 'Utilities & Bills',
                    'Health & Medical', 'Entertainment & Recreation', 'Education & Learning',
                    'Personal Care & Beauty', 'Housing & Rent', 'Others']
