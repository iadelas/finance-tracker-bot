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
        """Parse receipt text into structured expense data"""
        
        # Initialize result with user context
        receipt_data = {
            'description': 'Receipt purchase',
            'amount': 0,
            'location': 'Unknown',
            'category': 'Other',
            'transaction_date': self._normalize_datetime(message_date).strftime('%Y-%m-%d'),
            'input_by': user_name,
            'source': 'Vision API'
        }
        
        lines = full_text.split('\n')
        non_empty_lines = [line.strip() for line in lines if line.strip()]
        
        # Extract merchant/store name (usually first meaningful line)
        if non_empty_lines:
            for line in non_empty_lines[:3]:  # Check first 3 lines
                if len(line) > 3 and not re.search(r'^\d+[/-]\d+', line) and not re.search(r'\d{4,}', line):
                    receipt_data['location'] = line.title()
                    break
        
        # Extract total amount with Indonesian patterns
        amount_patterns = [
            r'(?:total|subtotal|jumlah|amount)[:.]?\s*rp?\.?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',
            r'rp\.?\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)',
            r'(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)\s*rp',
            r'(\d{1,3}(?:[.,]\d{3})+)',  # Indonesian thousands separator
            r'(\d{4,})'  # Fallback for any large number
        ]
        
        amounts = []
        text_lower = full_text.lower()
        
        for pattern in amount_patterns:
            matches = re.findall(pattern, text_lower)
            for match in matches:
                try:
                    # Handle Indonesian number formatting
                    clean_amount = match.replace(',', '').replace('.', '')
                    
                    # Skip if too small (likely not a total)
                    if len(clean_amount) >= 3:
                        amounts.append(float(clean_amount))
                except ValueError:
                    continue
        
        if amounts:
            # Take the largest amount (most likely the total)
            receipt_data['amount'] = max(amounts)
        
        # Extract date from receipt
        receipt_date = self._extract_receipt_date(full_text, message_date)
        if receipt_date:
            receipt_data['transaction_date'] = receipt_date
        
        # Auto-categorize based on merchant or content
        receipt_data['category'] = self._categorize_receipt(receipt_data['location'], full_text)
        
        # Create meaningful description
        if receipt_data['location'] != 'Unknown':
            receipt_data['description'] = f"Purchase at {receipt_data['location']}"
        else:
            # Try to extract main items from receipt
            item_lines = [line for line in non_empty_lines[1:5] 
                         if not re.search(r'^\d+[/-]\d+', line) and len(line) > 3]
            if item_lines:
                receipt_data['description'] = item_lines[0].title()[:50]
        
        # Ensure proper capitalization
        receipt_data['description'] = receipt_data['description'].capitalize()
        receipt_data['location'] = receipt_data['location'].capitalize()
        
        return receipt_data
    
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
