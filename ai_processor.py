import requests
import json
import re
from config import GEMINI_API_KEY

class AIProcessor:
    def __init__(self):
        self.gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    
    def parse_expense_text(self, text):
        """Parse Indonesian expense text using Gemini AI"""
        prompt = f"""
        Analisis teks pengeluaran dalam bahasa Indonesia berikut dan ekstrak informasi dalam format JSON:
        Teks: "{text}"
        
        Ekstrak:
        1. Deskripsi item yang dibeli
        2. Jumlah uang (konversi ke angka, hapus 'ribu', 'rb', 'k')
        3. Lokasi pembelian (toko, tempat)
        4. Kategori (makanan, transportasi, kesehatan, belanja, dll)
        
        Format output JSON:
        {{
            "description": "deskripsi lengkap",
            "amount": 50000,
            "location": "nama toko/tempat",
            "category": "kategori pengeluaran"
        }}
        
        Jika tidak bisa dianalisis, return {{"error": "tidak dapat dianalisis"}}
        """
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }]
        }
        
        try:
            response = requests.post(self.gemini_url, json=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            ai_text = result['candidates'][0]['content']['parts'][0]['text']
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', ai_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return {"error": "Could not parse AI response"}
                
        except Exception as e:
            print(f"AI processing error: {e}")
            return self._fallback_parse(text)
    
    def _fallback_parse(self, text):
        """Fallback regex parsing for common Indonesian patterns"""
        # Extract amount using regex
        amount_patterns = [
            r'(\d+)\s*(?:ribu|rb|k)',
            r'(\d+)\.?(\d{3})',
            r'(\d+)'
        ]
        
        amount = 0
        for pattern in amount_patterns:
            match = re.search(pattern, text.lower())
            if match:
                if 'ribu' in text.lower() or 'rb' in text.lower() or 'k' in text.lower():
                    amount = int(match.group(1)) * 1000
                else:
                    amount = int(match.group(1))
                break
        
        return {
            "description": text,
            "amount": amount,
            "location": "Unknown",
            "category": "Other"
        }
