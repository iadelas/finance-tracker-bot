import os
import json
import re
from datetime import datetime, timedelta
from google.cloud import vision
from google.oauth2.service_account import Credentials
from config import GOOGLE_CREDENTIALS_FILE

class VisionProcessor:
    def __init__(self):
        """Initialize Google Vision API client using existing credentials"""
        try:
            # Reuse the same service account credentials
            credentials = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE)
            self.client = vision.ImageAnnotatorClient(credentials=credentials)
            print("✅ Google Vision API initialized")
        except Exception as e:
            print(f"❌ Vision API initialization failed: {e}")
            self.client = None
    
    def test_vision_permissions(self):
        """Test Vision API permissions with a valid minimal image"""
        if not self.client:
            print("❌ Vision API client not initialized")
            return False
        
        try:
            # Create a valid 1x1 pixel white PNG (corrected base64)
            import base64
            # This is a properly encoded 1x1 white PNG
            test_image_b64 = """
            iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==
            """.strip().replace('\n', '').replace(' ', '')
            
            test_image = base64.b64decode(test_image_b64)
            
            # Create Vision API image object
            image = vision.Image(content=test_image)
            
            # Use text_detection (simplest API call)
            response = self.client.text_detection(image=image)
            
            # Check for API errors in response
            if response.error and response.error.message:
                print(f"❌ Vision API error: {response.error.message}")
                return False
            
            print("✅ Vision API permissions test successful")
            return True
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ Vision API test failed: {error_msg}")
            
            # Provide specific solutions
            if "invalid argument" in error_msg.lower():
                print("💡 SOLUTION: Image data format issue")
                print("   Try using a different test image format")
            elif "403" in error_msg or "permission" in error_msg.lower():
                print("💡 SOLUTION: Enable Cloud Vision API in Google Cloud Console")
            elif "quota" in error_msg.lower():
                print("💡 SOLUTION: Check API quotas - may have exceeded free tier")
            else:
                print("💡 SOLUTION: Check Vision API setup and credentials")
            
            return False


    def extract_receipt_data(self, image_path, message_date, user_name):
        """Extract structured data from receipt image"""
        if not self.client:
            return {'error': 'Vision API not available'}
        
        try:
            # Read and process image
            with open(image_path, 'rb') as image_file:
                content = image_file.read()
            
            image = vision.Image(content=content)
            
            # Use document text detection for better receipt processing
            response = self.client.document_text_detection(image=image)
            
            if response.error.message:
                raise Exception(f'Vision API error: {response.error.message}')
            
            # Extract full text
            full_text = response.full_text_annotation.text if response.full_text_annotation else ""
            
            if not full_text.strip():
                return {'error': 'No text found in receipt'}
            
            # Parse receipt into structured data
            receipt_data = self._parse_receipt_structure(full_text, message_date, user_name)
            
            print(f"✅ Vision API extracted: {receipt_data}")
            return receipt_data
            
        except Exception as e:
            print(f"❌ Vision API error: {e}")
            return {'error': f'Failed to process receipt: {str(e)}'}
    
    def _parse_receipt_structure(self, full_text, message_date, user_name):
        """Smart Indonesian receipt parsing with context-aware extraction"""
        
        # Initialize result
        receipt_data = {
            'description': 'Receipt purchase',
            'amount': 0,
            'location': 'Unknown',
            'category': 'Other',
            'transaction_date': self._normalize_datetime(message_date).strftime('%Y-%m-%d'),
            'input_by': user_name,
            'source': 'Vision API'
        }
        
        lines = [line.strip() for line in full_text.split('\n') if line.strip()]
        text_lower = full_text.lower()
        
        print(f"🔍 RAW OCR TEXT:\n{full_text}")
        print(f"🔍 LINES: {lines}")
        
        # 1. SMART MERCHANT DETECTION - Look for business patterns
        merchant_found = self._extract_merchant_name(lines)
        if merchant_found:
            receipt_data['location'] = merchant_found
            print(f"🏪 MERCHANT: {merchant_found}")
        
        # 2. CONTEXT-AWARE TOTAL AMOUNT EXTRACTION
        total_amount = self._extract_total_amount(lines, full_text)
        if total_amount > 0:
            receipt_data['amount'] = total_amount
            print(f"💰 TOTAL AMOUNT: Rp {total_amount:,.0f}")
        
        # 3. SMART DATE EXTRACTION
        receipt_date = self._extract_receipt_date_smart(full_text, message_date)
        if receipt_date:
            receipt_data['transaction_date'] = receipt_date
            print(f"📅 DATE: {receipt_date}")
        
        # 4. CATEGORY BASED ON MERCHANT
        receipt_data['category'] = self._categorize_receipt_enhanced(receipt_data['location'], full_text)
        
        # 5. DESCRIPTION
        if receipt_data['location'] != 'Unknown':
            receipt_data['description'] = f"Purchase at {receipt_data['location']}"
        
        # Proper capitalization
        receipt_data['description'] = receipt_data['description'].capitalize()
        receipt_data['location'] = receipt_data['location'].capitalize()
        
        print(f"✅ FINAL RESULT: {receipt_data}")
        return receipt_data

    def _extract_merchant_name(self, lines):
        """Extract merchant name using business logic"""
        
        # Skip patterns that are definitely NOT merchant names
        skip_patterns = [
            r'^\d+$',                    # Pure numbers
            r'^[\d\s\-/:.,]+$',         # Dates/times/numbers only
            r'^\d{10,}$',               # Phone numbers (10+ digits)
            r'^(receipt|struk|bon)$',   # Receipt headers
            r'kasir|cashier',           # Cashier info
            r'^(total|subtotal|tax)$',  # Financial terms
            r'^\d{2,4}[-/]\d{1,2}[-/]\d{1,4}$',  # Dates
            r'^\d{1,2}:\d{2}',          # Times
            r'^[A-Z]{2,3}\d+$',         # Reference codes like TX123
        ]
        
        # Look for merchant in first 5 lines (header area)
        for i, line in enumerate(lines[:5]):
            line_clean = line.strip()
            
            # Skip if line matches any skip pattern
            if any(re.match(pattern, line_clean, re.IGNORECASE) for pattern in skip_patterns):
                continue
            
            # Skip very short lines (less than 3 chars)
            if len(line_clean) < 3:
                continue
            
            # Prefer longer, meaningful business names
            if len(line_clean) >= 4:
                # Check if it looks like a business name
                if re.search(r'[a-zA-Z]{3,}', line_clean):  # At least 3 letters
                    print(f"🏪 MERCHANT CANDIDATE: '{line_clean}' (line {i})")
                    return line_clean.title()
        
        return "Unknown"

    def _extract_total_amount(self, lines, full_text):
        """Smart total amount extraction with context awareness"""
        
        amounts = []
        
        # Strategy 1: Look for explicit TOTAL lines with context
        total_indicators = ['total', 'grand total', 'subtotal', 'jumlah', 'amount due']
        
        for i, line in enumerate(lines):
            line_lower = line.lower()
            
            # Check if line contains total indicator
            for indicator in total_indicators:
                if indicator in line_lower:
                    # Extract number from this line
                    amount_match = re.search(r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)', line)
                    if amount_match:
                        amount_str = amount_match.group(1)
                        amount_val = self._parse_indonesian_number(amount_str)
                        if amount_val and amount_val >= 100:  # Reasonable minimum
                            amounts.append(('total_line', amount_val, line))
                            print(f"💰 TOTAL LINE: '{line}' → {amount_val}")
        
        # Strategy 2: Look for amounts at the END of receipt (bottom lines)
        # Total is usually in the last 3-5 lines
        for i, line in enumerate(lines[-5:], len(lines)-5):
            line_lower = line.lower()
            
            # Skip if line has obvious non-total indicators
            if any(word in line_lower for word in ['phone', 'hp', 'tel', 'wa', 'whatsapp', 'contact']):
                print(f"📞 SKIP PHONE LINE: '{line}'")
                continue
            
            if any(word in line_lower for word in ['ref', 'invoice', 'receipt', 'cashier', 'kasir']):
                continue
            
            # Look for standalone numbers (likely totals)
            amount_matches = re.findall(r'(\d{1,3}(?:[.,]\d{3})*)', line)
            for amount_str in amount_matches:
                amount_val = self._parse_indonesian_number(amount_str)
                if amount_val and amount_val >= 100:  # Filter small numbers
                    amounts.append(('bottom_line', amount_val, line))
                    print(f"💰 BOTTOM LINE: '{line}' → {amount_val}")
        
        # Strategy 3: Look for Rp prefix patterns
        rp_patterns = [
            r'rp\.?\s*(\d{1,3}(?:[.,]\d{3})*)',
            r'(\d{1,3}(?:[.,]\d{3})*)\s*rp',
        ]
        
        for pattern in rp_patterns:
            matches = re.findall(pattern, full_text.lower())
            for amount_str in matches:
                amount_val = self._parse_indonesian_number(amount_str)
                if amount_val and amount_val >= 100:
                    amounts.append(('rp_pattern', amount_val, f"Rp {amount_str}"))
                    print(f"💰 RP PATTERN: Rp {amount_str} → {amount_val}")
        
        if not amounts:
            print("⚠️ NO AMOUNTS FOUND")
            return 0
        
        # SMART SELECTION: Prioritize by context and value
        print(f"🔍 ALL AMOUNTS FOUND: {amounts}")
        
        # Priority 1: Explicit total lines
        total_line_amounts = [amt for source, amt, line in amounts if source == 'total_line']
        if total_line_amounts:
            selected = max(total_line_amounts)
            print(f"✅ SELECTED (total line): {selected}")
            return selected
        
        # Priority 2: Bottom line amounts (but filter out obvious phone numbers)
        bottom_amounts = []
        for source, amt, line in amounts:
            if source == 'bottom_line':
                # Filter out phone number patterns
                if not re.search(r'\b\d{10,}\b', line):  # Not 10+ digit sequences
                    bottom_amounts.append(amt)
        
        if bottom_amounts:
            selected = max(bottom_amounts)
            print(f"✅ SELECTED (bottom line): {selected}")
            return selected
        
        # Priority 3: Rp patterns
        rp_amounts = [amt for source, amt, line in amounts if source == 'rp_pattern']
        if rp_amounts:
            selected = max(rp_amounts)
            print(f"✅ SELECTED (rp pattern): {selected}")
            return selected
        
        # Fallback: Largest reasonable amount
        all_amounts = [amt for source, amt, line in amounts if 100 <= amt <= 10000000]  # Reasonable range
        if all_amounts:
            selected = max(all_amounts)
            print(f"✅ SELECTED (largest): {selected}")
            return selected
        
        print("❌ NO VALID AMOUNT FOUND")
        return 0

    def _parse_indonesian_number(self, number_str):
        """Parse Indonesian number format (handles both . and , as thousands separator)"""
        try:
            # Remove all separators and convert to float
            clean_number = re.sub(r'[.,]', '', number_str)
            return float(clean_number)
        except (ValueError, AttributeError):
            return None

    def _extract_receipt_date_smart(self, text, fallback_date):
        """Smart date extraction with better pattern recognition"""
        
        date_patterns = [
            # Indonesian receipt formats
            (r'(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember)\s+(\d{2,4})', 'month_name'),
            
            # Standard date formats
            (r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})', 'dmy'),
            (r'(\d{2,4})[/-](\d{1,2})[/-](\d{1,2})', 'ymd'),
            
            # Date with time context
            (r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s+\d{1,2}:\d{2}', 'datetime'),
        ]
        
        for pattern, format_type in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if format_type == 'month_name':
                        day, month, year = match.groups()
                        month_map = {
                            'jan': 1, 'januari': 1, 'feb': 2, 'februari': 2, 'mar': 3, 'maret': 3,
                            'apr': 4, 'april': 4, 'may': 5, 'mei': 5, 'jun': 6, 'juni': 6,
                            'jul': 7, 'juli': 7, 'aug': 8, 'agustus': 8, 'sep': 9, 'september': 9,
                            'oct': 10, 'oktober': 10, 'nov': 11, 'november': 11, 'dec': 12, 'desember': 12
                        }
                        
                        if month.lower() in month_map:
                            month_num = month_map[month.lower()]
                            day_num = int(day)
                            year_num = int(year)
                            
                            if year_num < 100:
                                year_num += 2000 if year_num < 50 else 1900
                            
                            if 1 <= day_num <= 31 and 1 <= month_num <= 12 and 2000 <= year_num <= 2030:
                                date_found = f"{year_num:04d}-{month_num:02d}-{day_num:02d}"
                                print(f"📅 DATE PATTERN FOUND: '{match.group()}' → {date_found}")
                                return date_found
                    
                    elif format_type in ['dmy', 'ymd', 'datetime']:
                        # Handle numeric date formats
                        if format_type == 'datetime':
                            date_part = match.group(1)
                            parts = re.split(r'[/-]', date_part)
                        else:
                            parts = match.groups()
                        
                        if len(parts) == 3:
                            if format_type == 'ymd':
                                year, month, day = map(int, parts)
                            else:  # dmy format (more common in Indonesia)
                                day, month, year = map(int, parts)
                            
                            if year < 100:
                                year += 2000 if year < 50 else 1900
                            
                            if 1 <= day <= 31 and 1 <= month <= 12 and 2000 <= year <= 2030:
                                date_found = f"{year:04d}-{month:02d}-{day:02d}"
                                print(f"📅 DATE PATTERN FOUND: '{match.group()}' → {date_found}")
                                return date_found
                                
                except (ValueError, IndexError):
                    continue
        
        # Return fallback date if no valid date found
        fallback_naive = self._normalize_datetime(fallback_date)
        fallback_str = fallback_naive.strftime('%Y-%m-%d')
        print(f"📅 USING FALLBACK DATE: {fallback_str}")
        return fallback_str

    def _extract_receipt_date_enhanced(self, text, fallback_date):
        """Enhanced date extraction for Indonesian receipts"""
        
        date_patterns = [
            # DD/MM/YY or DD/MM/YYYY
            r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})',
            
            # DD Month YYYY (Indonesian months)
            r'(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember)\s+(\d{2,4})',
            
            # Time with date: 10 May 19 16:32:47
            r'(\d{1,2})\s+(\w{3,})\s+(\d{2,4})\s+\d{2}:\d{2}',
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if len(match.groups()) == 3:
                        day, month, year = match.groups()
                        
                        # Handle month names
                        month_map = {
                            'jan': 1, 'januari': 1,
                            'feb': 2, 'februari': 2, 
                            'mar': 3, 'maret': 3,
                            'apr': 4, 'april': 4,
                            'may': 5, 'mei': 5,
                            'jun': 6, 'juni': 6,
                            'jul': 7, 'juli': 7,
                            'aug': 8, 'agustus': 8,
                            'sep': 9, 'september': 9,
                            'oct': 10, 'oktober': 10,
                            'nov': 11, 'november': 11,
                            'dec': 12, 'desember': 12
                        }
                        
                        if month.lower() in month_map:
                            month = month_map[month.lower()]
                        else:
                            month = int(month)
                        
                        day = int(day)
                        year = int(year)
                        
                        # Handle 2-digit years
                        if year < 100:
                            year += 2000 if year < 50 else 1900
                        
                        if 1 <= day <= 31 and 1 <= month <= 12 and 2010 <= year <= 2030:
                            return f"{year:04d}-{month:02d}-{day:02d}"
                except (ValueError, KeyError):
                    continue
        
        # Return fallback date
        fallback_naive = self._normalize_datetime(fallback_date)
        return fallback_naive.strftime('%Y-%m-%d')

    def _categorize_receipt_enhanced(self, location, full_text):
        """Enhanced categorization for Indonesian businesses"""
        location_lower = location.lower()
        text_lower = full_text.lower()
        
        # Food & Bakery (BreadTalk specific)
        if any(word in location_lower for word in [
            'breadtalk', 'bread talk', 'bakery', 'cake', 'pastry',
            'restaurant', 'resto', 'cafe', 'food', 'makan', 'warung', 
            'rumah makan', 'kfc', 'mcd', 'pizza', 'bakso', 'nasi'
        ]):
            return 'Food'
        
        # Shopping & Retail
        elif any(word in location_lower for word in [
            'market', 'mart', 'grocery', 'supermarket', 'indomaret', 
            'alfamart', 'shop', 'store', 'mall', 'plaza'
        ]):
            return 'Shopping'
        
        # Transport & Fuel
        elif any(word in location_lower for word in [
            'gas', 'petrol', 'shell', 'pertamina', 'bensin', 'spbu'
        ]):
            return 'Transport'
        
        # Health & Pharmacy
        elif any(word in text_lower for word in [
            'pharmacy', 'apotek', 'medicine', 'obat', 'dokter', 'clinic'
        ]):
            return 'Health'
        
        return 'Other'

    def _normalize_datetime(self, dt):
            """Convert any datetime to timezone-naive for consistent operations"""
            if dt is None:
                return datetime.now()
            
            # If timezone-aware, convert to naive
            if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
                return dt.replace(tzinfo=None)
            
            return dt
        
    def _extract_receipt_date(self, text, fallback_date):
            """Extract date from receipt text with timezone handling"""
            date_patterns = [
                r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',  # DD/MM/YYYY or MM/DD/YYYY
                r'(\d{2,4}[/-]\d{1,2}[/-]\d{1,2})',  # YYYY/MM/DD
                r'(\d{1,2}\s+\w{3,}\s+\d{2,4})'     # DD Month YYYY
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    date_str = match.group(1)
                    # Try multiple date formats
                    for fmt in ['%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d', '%d-%m-%Y', '%Y-%m-%d']:
                        try:
                            parsed_date = datetime.strptime(date_str, fmt)
                            
                            # CRITICAL FIX: Handle timezone comparison
                            # Convert both dates to naive for comparison
                            fallback_naive = self._normalize_datetime(fallback_date)
                            
                            # Validate date is reasonable (not future, not too old)
                            if (fallback_naive - timedelta(days=30)) <= parsed_date <= fallback_naive:
                                return parsed_date.strftime('%Y-%m-%d')
                        except ValueError:
                            continue
            
            # Return fallback date (handle timezone)
            fallback_naive = self._normalize_datetime(fallback_date)
            return fallback_naive.strftime('%Y-%m-%d')
        
    def _categorize_receipt(self, location, full_text):
            """Auto-categorize based on merchant and content"""
            location_lower = location.lower()
            text_lower = full_text.lower()
            
            # Food & Restaurant
            if any(word in location_lower for word in [
                'restaurant', 'resto', 'cafe', 'food', 'makan', 'warung', 'rumah makan',
                'kfc', 'mcd', 'pizza', 'bakso', 'nasi', 'ayam', 'burger'
            ]):
                return 'Food'
            
            # Transport & Fuel
            elif any(word in location_lower for word in [
                'gas', 'petrol', 'shell', 'pertamina', 'bensin', 'spbu'
            ]):
                return 'Transport'
            
            # Shopping & Retail
            elif any(word in location_lower for word in [
                'market', 'mart', 'grocery', 'supermarket', 'indomaret', 'alfamart',
                'shop', 'store', 'mall', 'plaza'
            ]):
                return 'Shopping'
            
            # Health & Pharmacy
            elif any(word in text_lower for word in [
                'pharmacy', 'apotek', 'medicine', 'obat', 'dokter', 'clinic'
            ]):
                return 'Health'
            
            # Utilities
            elif any(word in text_lower for word in [
                'listrik', 'pln', 'water', 'air', 'internet', 'telkom'
            ]):
                return 'Utilities'
            
            return 'Other'

    def extract_text_only(self, image_path):
            """Fallback method - just extract text like old OCR"""
            if not self.client:
                return "Vision API not available"
            
            try:
                with open(image_path, 'rb') as image_file:
                    content = image_file.read()
                
                image = vision.Image(content=content)
                response = self.client.text_detection(image=image)
                
                if response.text_annotations:
                    return response.text_annotations[0].description
                return "No text found"
                
            except Exception as e:
                print(f"❌ Text extraction error: {e}")
                return f"Error: {str(e)}"
