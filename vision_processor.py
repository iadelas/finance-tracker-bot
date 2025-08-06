import os
import json
import re
from datetime import datetime, timedelta
from google.cloud import vision
from google.oauth2.service_account import Credentials
import google.generativeai as genai
from config import GOOGLE_CREDENTIALS_FILE, GEMINI_API_KEY

class VisionProcessor:
    def __init__(self):
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
            # Step 1: Extract text using Vision API
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            response = self.vision_client.document_text_detection(image=image)
            
            if response.error.message:
                raise Exception(f'Vision API error: {response.error.message}')
            
            raw_text = response.full_text_annotation.text if response.full_text_annotation else ""
            
            if not raw_text.strip():
                return {'error': 'No text found in receipt'}
            
            print(f"📄 OCR extracted {len(raw_text)} characters")
            
            # Step 2: Parse with Gemini AI (preferred method)
            if self.gemini_model:
                receipt_data = self._parse_with_gemini(raw_text, message_date, user_name)
                if not receipt_data.get('error'):
                    return receipt_data
                print("⚠️ Gemini parsing failed, using fallback")
            
            # Step 3: Fallback to regex parsing
            return self._parse_with_regex(raw_text, message_date, user_name)
            
        except Exception as e:
            print(f"❌ Receipt processing error: {e}")
            return {'error': f'Failed to process receipt: {str(e)}'}

    def _parse_with_gemini(self, ocr_text, message_date, user_name):
        """Use Gemini AI to intelligently parse receipt OCR text"""
        try:
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
                "category": "Food|Shopping|Transport|Health|Entertainment|Utilities|Other"
            }}

            EXAMPLES:
            - "TOTAL: 25,200" → amount: 25200
            - "ALFAMART CILANDAK" → merchant: "Alfamart Cilandak"
            - "18-03-2022" → date: "2022-03-18"
            - "BreadTalk" → category: "Food"
            
            Focus on accuracy. If unsure about any field, use reasonable defaults.
            """
            
            response = self.gemini_model.generate_content(prompt)
            
            # Extract JSON from response
            json_match = re.search(r'\{[^}]*\}', response.text, re.DOTALL)
            if not json_match:
                return {'error': 'No valid JSON in AI response'}
            
            ai_result = json.loads(json_match.group())
            
            # Build structured response
            receipt_data = {
                'description': f"Purchase at {ai_result.get('merchant', 'Unknown')}",
                'amount': self._clean_amount(ai_result.get('amount', 0)),
                'location': ai_result.get('merchant', 'Unknown'),
                'category': ai_result.get('category', 'Other'),
                'transaction_date': ai_result.get('date') or self._normalize_datetime(message_date).strftime('%Y-%m-%d'),
                'input_by': user_name,
                'source': 'Vision API + Gemini AI'
            }
            
            # Ensure proper formatting
            receipt_data['description'] = receipt_data['description'].capitalize()
            receipt_data['location'] = receipt_data['location'].title()
            
            print(f"🤖 Gemini parsed: {ai_result.get('merchant')} - Rp {receipt_data['amount']:,.0f}")
            return receipt_data
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error: {e}")
            return {'error': 'Invalid AI response format'}
        except Exception as e:
            print(f"❌ Gemini parsing error: {e}")
            return {'error': f'AI parsing failed: {str(e)}'}

    def _parse_with_regex(self, raw_text, message_date, user_name):
        """Fallback regex-based parsing for when Gemini fails"""
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
        """Clean and validate amount value"""
        try:
            if isinstance(amount, str):
                # Handle string amounts
                clean = re.sub(r'[^\d]', '', amount)
                return float(clean) if clean else 0
            elif isinstance(amount, (int, float)):
                return float(amount)
            else:
                return 0
        except (ValueError, TypeError):
            return 0

    def _parse_indonesian_number(self, number_str):
        """Parse Indonesian number format"""
        try:
            clean_number = re.sub(r'[.,]', '', str(number_str))
            return float(clean_number)
        except (ValueError, TypeError):
            return None

    def _categorize_merchant(self, merchant_name):
        """Categorize based on merchant name"""
        merchant_lower = merchant_name.lower()
        
        # Food & Restaurant
        if any(word in merchant_lower for word in [
            'restaurant', 'resto', 'cafe', 'food', 'makan', 'warung',
            'kfc', 'mcd', 'pizza', 'bakery', 'bread', 'cake'
        ]):
            return 'Food'
        
        # Shopping & Retail
        elif any(word in merchant_lower for word in [
            'mart', 'market', 'grocery', 'supermarket', 'indomaret', 
            'alfamart', 'shop', 'store', 'mall', 'plaza'
        ]):
            return 'Shopping'
        
        # Transport & Fuel
        elif any(word in merchant_lower for word in [
            'shell', 'pertamina', 'spbu', 'gas', 'petrol'
        ]):
            return 'Transport'
        
        # Health & Pharmacy
        elif any(word in merchant_lower for word in [
            'apotek', 'pharmacy', 'clinic', 'hospital', 'dokter'
        ]):
            return 'Health'
        
        # Utilities
        elif any(word in merchant_lower for word in [
            'pln', 'listrik', 'telkom', 'internet', 'water'
        ]):
            return 'Utilities'
        
        return 'Other'

    def _normalize_datetime(self, dt):
        """Convert datetime to timezone-naive for consistent operations"""
        if dt is None:
            return datetime.now()
        
        if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
            return dt.replace(tzinfo=None)
        
        return dt
