import google.generativeai as genai
from config import GEMINI_API_KEY

class AIProcessor:
    def __init__(self):
        if not GEMINI_API_KEY:
            print("❌ GEMINI_API_KEY not found!")
            return
        
        genai.configure(api_key=GEMINI_API_KEY)
        # Use the current model name
        self.model = genai.GenerativeModel('gemini-1.5-flash')  # Updated model
        print("✅ Gemini AI initialized with gemini-1.5-flash")
    
    def parse_expense_text(self, text):
        """Parse expense text using updated Gemini API"""
        if not hasattr(self, 'model'):
            return {'error': 'Gemini API not initialized'}
        
        try:
            prompt = f"""
            Extract expense information from this Indonesian text: "{text}"
            
            Return JSON format:
            {{
                "description": "brief description",
                "amount": numeric_amount,
                "location": "store/place name",
                "category": "food/transport/utilities/shopping/other"
            }}
            
            Examples:
            - "beli ayam goreng gofood 4ribu" → {{"description": "Ayam goreng", "amount": 4000, "location": "GoFood", "category": "food"}}
            - "bensin 20k shell" → {{"description": "Bensin", "amount": 20000, "location": "Shell", "category": "transport"}}
            """
            
            response = self.model.generate_content(prompt)
            
            # Parse JSON from response
            import json
            import re
            
            # Extract JSON from response text
            json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if json_match:
                expense_data = json.loads(json_match.group())
                print(f"✅ Parsed expense: {expense_data}")
                return expense_data
            else:
                # Fallback parsing if JSON extraction fails
                return self._fallback_parse(text)
                
        except Exception as e:
            print(f"❌ Gemini API error: {e}")
            return self._fallback_parse(text)
    
    def _fallback_parse(self, text):
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
        
        return {
            'description': text[:50],  # First 50 chars
            'amount': amount,
            'location': 'Unknown',
            'category': 'other'
        }
