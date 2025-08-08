import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Required environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GOOGLE_SHEET_ID = os.getenv('GOOGLE_SHEET_ID')
GOOGLE_CREDENTIALS_FILE = os.getenv('GOOGLE_CREDENTIALS_FILE')
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', '')  # Optional webhook security token


def validate_environment():
    """Validate that all required environment variables are set"""
    required_vars = {
        'TELEGRAM_BOT_TOKEN': TELEGRAM_BOT_TOKEN,
        'GEMINI_API_KEY': GEMINI_API_KEY,
        'GOOGLE_SHEET_ID': GOOGLE_SHEET_ID,
        'GOOGLE_CREDENTIALS_FILE': GOOGLE_CREDENTIALS_FILE,
        'WEBHOOK_SECRET': WEBHOOK_SECRET,
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n💡 Please copy .env.example to .env and fill in your values")
        raise ValueError(f"Missing environment variables: {missing_vars}")
    
    print("✅ All environment variables loaded successfully")

# Validate on import
if __name__ != "__main__":
    validate_environment()
