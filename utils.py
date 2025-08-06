import re
from datetime import datetime, timedelta
from typing import Optional, Union, List

class DateUtils:
    """Indonesian date processing utilities"""
    
    @staticmethod
    def parse_indonesian_date(text: str, reference_date: datetime = None) -> Optional[str]:
        """Parse Indonesian date expressions to YYYY-MM-DD format"""
        if not reference_date:
            reference_date = datetime.now()
            
        # Remove timezone if present
        if hasattr(reference_date, 'tzinfo') and reference_date.tzinfo:
            reference_date = reference_date.replace(tzinfo=None)
            
        text_lower = text.lower().strip()
        
        # Relative date patterns
        relative_patterns = {
            'yesterday': ['kemarin', 'kmrn', 'yesterday'],
            'today': ['hari ini', 'today', 'tadi', 'barusan'],
            'tomorrow': ['besok', 'tomorrow'],
            'day_before_yesterday': ['kemarin dulu', 'lusa kemarin']
        }
        
        # Check relative dates
        for period, keywords in relative_patterns.items():
            if any(word in text_lower for word in keywords):
                if period == 'yesterday':
                    return (reference_date - timedelta(days=1)).strftime('%Y-%m-%d')
                elif period == 'today':
                    return reference_date.strftime('%Y-%m-%d')
                elif period == 'tomorrow':
                    return (reference_date + timedelta(days=1)).strftime('%Y-%m-%d')
                elif period == 'day_before_yesterday':
                    return (reference_date - timedelta(days=2)).strftime('%Y-%m-%d')
        
        # Check day of week
        weekdays = {
            'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
            'friday': 4, 'saturday': 5, 'sunday': 6,
            'senin': 0, 'selasa': 1, 'rabu': 2, 'kamis': 3,
            'jumat': 4, 'sabtu': 5, 'minggu': 6
        }
        
        for day_name, target_weekday in weekdays.items():
            if day_name in text_lower:
                current_weekday = reference_date.weekday()
                days_back = (current_weekday - target_weekday) % 7
                if days_back == 0:
                    return reference_date.strftime('%Y-%m-%d')
                else:
                    target_date = reference_date - timedelta(days=days_back)
                    return target_date.strftime('%Y-%m-%d')
        
        # Default to reference date
        return reference_date.strftime('%Y-%m-%d')

class AmountUtils:
    """Indonesian currency and amount processing utilities"""
    
    @staticmethod
    def parse_indonesian_amount(text: str) -> float:
        """Parse Indonesian amount expressions to numeric value"""
        text_lower = text.lower().strip()
        
        # Amount patterns (in priority order)
        patterns = [
            (r'(\d+)\s*(?:ribu|rb)', lambda x: int(x) * 1000),    # "25ribu" -> 25000
            (r'(\d+)\s*k(?:\s|$)', lambda x: int(x) * 1000),     # "25k" -> 25000  
            (r'(\d+)\s*jt|juta', lambda x: int(x) * 1000000),    # "2jt" -> 2000000
            (r'(\d+)(?:[.,]\d{3})*', lambda x: int(re.sub(r'[.,]', '', x))),  # "25,000" -> 25000
            (r'(\d+)', lambda x: int(x))                          # "25000" -> 25000
        ]
        
        for pattern, converter in patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    return float(converter(match.group(1)))
                except (ValueError, TypeError):
                    continue
        
        return 0.0
    
    @staticmethod
    def format_rupiah(amount: Union[int, float]) -> str:
        """Format number as Indonesian Rupiah"""
        return f"Rp {amount:,.0f}"

class TextUtils:
    """Text processing and formatting utilities"""
    
    @staticmethod
    def capitalize_properly(text: str) -> str:
        """Capitalize first letter of each word properly"""
        if not text:
            return ""
        return text.strip().title()
    
    @staticmethod
    def clean_description(text: str, max_length: int = 100) -> str:
        """Clean and format expense description"""
        if not text:
            return "Unknown expense"
            
        # Remove extra spaces and normalize
        cleaned = ' '.join(text.strip().split())
        
        # Capitalize first letter
        cleaned = cleaned.capitalize()
        
        # Truncate if too long
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length-3] + "..."
            
        return cleaned
    
    @staticmethod
    def extract_location_from_text(text: str) -> str:
        """Extract location/merchant from expense text"""
        # Common Indonesian location indicators
        location_patterns = [
            r'di\s+([^0-9]+?)(?:\s+\d|$)',           # "di alfamart"
            r'ke\s+([^0-9]+?)(?:\s+\d|$)',           # "ke salon"  
            r'dari\s+([^0-9]+?)(?:\s+\d|$)',         # "dari toko"
            r'@\s*([^0-9\s]+)',                      # "@alfamart"
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, text.lower())
            if match:
                location = match.group(1).strip()
                return TextUtils.capitalize_properly(location)
        
        return "Unknown"

class ValidationUtils:
    """Input validation utilities"""
    
    @staticmethod
    def is_valid_amount(amount: Union[int, float]) -> bool:
        """Check if amount is within reasonable range"""
        try:
            amount_float = float(amount)
            return 1 <= amount_float <= 100_000_000  # 1 Rp to 100 million Rp
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def is_valid_date(date_str: str) -> bool:
        """Check if date string is valid YYYY-MM-DD format"""
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except (ValueError, TypeError):
            return False
    
    @staticmethod
    def sanitize_user_input(text: str) -> str:
        """Sanitize user input for security"""
        if not text:
            return ""
        
        # Remove potentially dangerous characters
        sanitized = re.sub(r'[<>"\';]', '', text)
        
        # Limit length
        return sanitized[:500].strip()

class CategoryUtils:
    """Category matching and processing utilities"""
    
    @staticmethod
    def match_category_by_keywords(text: str, location: str, available_categories: List[str]) -> str:
        """Match category based on keywords in text and location"""
        combined_text = f"{text.lower()} {location.lower()}"
        
        # Enhanced keyword mapping
        category_keywords = {
            'Food & Dining': [
                'makan', 'food', 'nasi', 'ayam', 'sate', 'warteg', 'resto', 'cafe', 
                'kfc', 'mcd', 'pizza', 'bakery', 'bread', 'cake', 'goreng', 'sop', 'bakso'
            ],
            'Transportation': [
                'bensin', 'grab', 'gojek', 'ojek', 'bus', 'taxi', 'motor', 'mobil', 
                'pertamina', 'shell', 'spbu', 'parkir', 'tol'
            ],
            'Shopping & Retail': [
                'beli', 'belanja', 'shop', 'mall', 'alfamart', 'indomaret', 'toko',
                'hypermart', 'carrefour', 'giant', 'supermarket'
            ],
            'Personal Care & Beauty': [
                'salon', 'potong rambut', 'spa', 'massage', 'kosmetik', 'pijet',
                'barbershop', 'facial', 'manicure', 'pedicure'
            ],
            'Utilities & Bills': [
                'listrik', 'air', 'internet', 'pulsa', 'token', 'pln', 'telkom',
                'indihome', 'wifi', 'bayar tagihan'
            ],
            'Health & Medical': [
                'dokter', 'obat', 'sakit', 'rumah sakit', 'apotek', 'klinik',
                'medical', 'hospital', 'periksa'
            ],
            'Entertainment & Recreation': [
                'bioskop', 'film', 'game', 'nonton', 'karaoke', 'gym', 'fitness',
                'cinema', 'netflix', 'spotify', 'main'
            ]
        }
        
        # Score each category
        best_category = None
        best_score = 0
        
        for category, keywords in category_keywords.items():
            if category in available_categories:
                score = sum(1 for keyword in keywords if keyword in combined_text)
                if score > best_score:
                    best_score = score
                    best_category = category
        
        # Return best match or default
        return best_category if best_category else (available_categories[-1] if available_categories else 'Others')

class ResponseFormatter:
    """Format bot responses consistently"""
    
    @staticmethod
    def format_expense_confirmation(expense_data: dict) -> str:
        """Format expense confirmation message"""
        return f"""✅ **Pengeluaran berhasil dicatat!**

📝 **Detail:**
• **Tanggal:** {expense_data.get('transaction_date', 'N/A')}
• **Deskripsi:** {expense_data.get('description', 'N/A')}
• **Jumlah:** {AmountUtils.format_rupiah(expense_data.get('amount', 0))}
• **Lokasi:** {expense_data.get('location', 'N/A')}
• **Kategori:** {expense_data.get('category', 'N/A')}
• **Input oleh:** {expense_data.get('input_by', 'N/A')}

💾 Data tersimpan di Google Sheets"""
    
    @staticmethod
    def format_error_message(error: str, context: str = "") -> str:
        """Format error messages consistently"""
        if context:
            return f"❌ {context}: {error}"
        return f"❌ {error}"
