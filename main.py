import logging
import os
import sys
import traceback
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from ai_processor import AIProcessor
from ocr_processor import OCRProcessor
from sheets_manager import SheetsManager
from config import TELEGRAM_BOT_TOKEN

# Enable detailed logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Initialize processors with error handling
try:
    logger.info("🔧 Initializing AI processor...")
    ai_processor = AIProcessor()
    logger.info("✅ AI processor initialized")
except Exception as e:
    logger.error(f"❌ AI processor failed: {e}")
    ai_processor = None

try:
    logger.info("🔧 Initializing OCR processor...")
    ocr_processor = OCRProcessor()
    logger.info("✅ OCR processor initialized")
except Exception as e:
    logger.error(f"❌ OCR processor failed: {e}")
    ocr_processor = None

try:
    logger.info("🔧 Initializing Sheets manager...")
    sheets_manager = SheetsManager()
    logger.info("✅ Sheets manager initialized")
except Exception as e:
    logger.error(f"❌ Sheets manager failed: {e}")
    sheets_manager = None

# Your existing handler functions
async def start(update: Update, context: CallbackContext):
    welcome_message = """
🤖 **Selamat datang di Finance Tracker Bot!**

📝 **Cara menggunakan:**
• Kirim teks: "Beli telur 2 kotak di alfamart 50ribu"
• Kirim foto struk/receipt
• /summary - Lihat ringkasan bulan ini
• /help - Bantuan

💡 **Contoh:**
• "ke salon johny 40 ribu"
• "bayar iuran warga 35000"
• "makan siang 25k di warteg"

Mulai catat pengeluaran Anda! 💰
    """
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def help_command(update: Update, context: CallbackContext):
    help_text = """
🔧 **Bantuan Finance Tracker Bot**

**Format teks yang didukung:**
• "beli [item] di [tempat] [jumlah]"
• "bayar [deskripsi] [jumlah]"
• "[aktivitas] [jumlah] [tempat]"

**Commands:**
• /start - Mulai bot
• /summary - Ringkasan bulanan
• /help - Bantuan ini
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def summary_command(update: Update, context: CallbackContext):
    if sheets_manager:
        summary = sheets_manager.get_monthly_summary()
        await update.message.reply_text(summary, parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Sheets manager not available")

async def handle_text(update: Update, context: CallbackContext):
    user_text = update.message.text
    processing_msg = await update.message.reply_text("🔄 Memproses pengeluaran...")
    
    try:
        # Try AI processing first
        if ai_processor:
            expense_data = ai_processor.parse_expense_text(user_text)
        else:
            expense_data = {'error': 'AI processor not available'}
        
        # If AI fails, use fallback parsing
        if expense_data.get('error'):
            expense_data = parse_expense_fallback(user_text)
            expense_data['source'] = 'Fallback Parser'
        else:
            expense_data['source'] = 'Gemini AI'
        
        # Try to save to sheets
        if sheets_manager:
            success = sheets_manager.add_expense(expense_data)
        else:
            success = False
        
        if success:
            response = f"""
✅ **Pengeluaran berhasil dicatat!**

📝 **Detail:**
• **Deskripsi:** {expense_data.get('description', 'N/A')}
• **Jumlah:** Rp {expense_data.get('amount', 0):,.0f}
• **Lokasi:** {expense_data.get('location', 'N/A')}
• **Kategori:** {expense_data.get('category', 'N/A')}
• **Parser:** {expense_data.get('source', 'Unknown')}

💾 Data tersimpan di Google Sheets
            """
        else:
            response = f"""
⚠️ **Data diproses tapi gagal menyimpan**

📝 **Detail yang diparsing:**
• **Deskripsi:** {expense_data.get('description', 'N/A')}
• **Jumlah:** Rp {expense_data.get('amount', 0):,.0f}

❌ Masalah koneksi Google Sheets
            """
        
        await processing_msg.edit_text(response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error processing text: {e}")
        await processing_msg.edit_text("❌ Terjadi kesalahan saat memproses")

def parse_expense_fallback(text):
    """Simple regex-based expense parser as fallback"""
    import re
    
    # Extract amount
    amount = 0
    amount_patterns = [
        r'(\d+)(?:ribu|rb)',
        r'(\d+)k', 
        r'(\d+)(?:000)',
        r'(\d+)'
    ]
    
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
    
    # Simple category detection
    category = 'other'
    if any(word in text.lower() for word in ['makan', 'beli', 'food', 'goreng']):
        category = 'food'
    elif any(word in text.lower() for word in ['bensin', 'grab', 'gojek']):
        category = 'transport'
    
    return {
        'description': text[:50],
        'amount': amount,
        'location': 'Unknown',
        'category': category
    }


def main():
    """Main function with comprehensive error handling"""
    logger.info("🚀 Starting Finance Tracker Bot main function...")
    
    try:
        # Check critical environment variables
        if not TELEGRAM_BOT_TOKEN:
            logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
            sys.exit(1)
        logger.info("✅ Telegram bot token found")
        
        # Get port and webhook info
        port = int(os.environ.get('PORT', 8000))
        render_url = os.environ.get('RENDER_EXTERNAL_URL')
        
        logger.info(f"📍 Port: {port}")
        logger.info(f"📍 Render URL: {render_url}")
        
        # Create Telegram application
        logger.info("🔧 Creating Telegram application...")
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        logger.info("✅ Telegram application created")
        
        # Add handlers
        logger.info("🔧 Adding handlers...")
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("summary", summary_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
        application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
        logger.info("✅ Handlers added")
        
        # Determine run mode
        if render_url:
            # Webhook mode for production
            webhook_full_url = f"{render_url}/webhook"
            logger.info(f"🌐 Webhook mode - URL: {webhook_full_url}")
            
            logger.info("🔧 Starting webhook server...")
            application.run_webhook(
                listen="0.0.0.0",
                port=port,
                webhook_url=webhook_full_url,
                url_path="/webhook",
                drop_pending_updates=True
            )
        else:
            # Polling mode for development
            logger.info("💻 Polling mode")
            application.run_polling(allowed_updates=Update.ALL_TYPES)
            
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        logger.error("Full traceback:")
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error in main(): {e}")
        logger.error("Full traceback:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Critical error: {e}")
        traceback.print_exc()
        sys.exit(1)
