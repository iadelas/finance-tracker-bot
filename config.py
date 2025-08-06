import os
from dotenv import load_dotenv

load_dotenv()

# Telegram Configuration
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# AI Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# OCR Configuration
OCR_API_KEY = os.getenv('OCR_API_KEY')

# Google Sheets Configuration
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE', 'credentials.json')

# Validate required environment variables
required_vars = [
    'TELEGRAM_BOT_TOKEN',
    'GEMINI_API_KEY', 
    'GOOGLE_SHEET_ID'
]

for var in required_vars:
    if not os.getenv(var):
        raise ValueError(f"Missing required environment variable: {var}")
