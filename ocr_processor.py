import requests
import base64
from config import OCR_API_KEY

class OCRProcessor:
    def __init__(self):
        self.ocr_url = "https://api.ocr.space/parse/image"
        self.api_key = OCR_API_KEY or "helloworld"  # Free tier fallback
    
    def extract_text_from_image(self, image_file):
        """Extract text from image using OCR.space API"""
        try:
            # Encode image to base64
            with open(image_file, 'rb') as f:
                image_data = base64.b64encode(f.read()).decode()
            
            payload = {
                'apikey': self.api_key,
                'language': 'eng',
                'isOverlayRequired': False,
                'base64Image': f'data:image/jpeg;base64,{image_data}'
            }
            
            response = requests.post(self.ocr_url, data=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('IsErroredOnProcessing', True):
                return "OCR processing failed"
            
            # Extract text from all regions
            text_results = []
            for parsed_result in result.get('ParsedResults', []):
                text_results.append(parsed_result.get('ParsedText', ''))
            
            return '\n'.join(text_results)
            
        except Exception as e:
            print(f"OCR error: {e}")
            return "Could not extract text from image"
