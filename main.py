import logging
import os
import sys
import asyncio
import threading
import re

from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from flask import Flask, jsonify
from ai_processor import AIProcessor
from vision_processor import VisionProcessor
from sheets_manager import SheetsManager
from config import TELEGRAM_BOT_TOKEN
from utils import ResponseFormatter

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize processors
try:
    logger.info("🔧 Initializing Sheets manager...")
    sheets_manager = SheetsManager()
    logger.info("✅ Sheets manager initialized")
except Exception as e:
    logger.error(f"❌ Sheets manager failed: {e}")
    sheets_manager = None

try:
    logger.info("🔧 Initializing AI processor...")
    ai_processor = AIProcessor(sheets_manager=sheets_manager)
    logger.info("✅ AI processor initialized")
except Exception as e:
    logger.error(f"❌ AI processor failed: {e}")
    ai_processor = None

try:
    logger.info("🔧 Initializing Vision processor...")
    vision_processor = VisionProcessor()
    vision_processor = VisionProcessor(sheets_manager=sheets_manager)
    
    if hasattr(vision_processor, 'vision_client') and vision_processor.vision_client:
        logger.info("✅ Vision processor initialized")
    else:
        logger.warning("⚠️ Vision processor initialized but Vision API client unavailable")
        
except Exception as e:
    logger.error(f"❌ Vision processor failed: {e}")
    vision_processor = None

# Global service state tracking
class ServiceState:
    def __init__(self):
        self.sheets_ready = False
        self.ai_ready = False
        self.vision_ready = False
        self.bot_ready = False
        self.initialization_start = datetime.now()
        self.flask_app = None
    
    def all_ready(self):
        return self.sheets_ready and self.ai_ready and self.vision_ready and self.bot_ready
    
    def get_status(self):
        return {
            'status': 'healthy' if self.all_ready() else 'initializing',
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': (datetime.now() - self.initialization_start).total_seconds(),
            'services': {
                'sheets': self.sheets_ready,
                'ai': self.ai_ready,
                'vision': self.vision_ready,
                'bot': self.bot_ready
            }
        }

# Global instances
service_state = ServiceState()
sheets_manager = None
ai_processor = None
vision_processor = None

def initialize_services_background():
    """Initialize heavy services in background thread"""
    global sheets_manager, ai_processor, vision_processor, service_state
    
    try:
        logger.info("🔧 Background initialization starting...")
        
        # Initialize Sheets manager
        logger.info("Initializing Sheets manager...")
        sheets_manager = SheetsManager()
        service_state.sheets_ready = True
        logger.info("✅ Sheets manager ready")
        
        # Initialize AI processor
        logger.info("Initializing AI processor...")
        ai_processor = AIProcessor(sheets_manager=sheets_manager)
        service_state.ai_ready = True
        logger.info("✅ AI processor ready")
        
        # Initialize Vision processor
        logger.info("Initializing Vision processor...")
        vision_processor = VisionProcessor(sheets_manager=sheets_manager)
        service_state.vision_ready = True
        logger.info("✅ Vision processor ready")
        
        service_state.bot_ready = True
        init_time = (datetime.now() - service_state.initialization_start).total_seconds()
        logger.info(f"🚀 All services ready in {init_time:.2f}s")
        
    except Exception as e:
        logger.error(f"❌ Background initialization failed: {e}")

def create_flask_app():
    """Create Flask app for health checks - NO PORT CONFLICTS"""
    app = Flask(__name__)
    
    @app.route('/health')
    def health_check():
        """Detailed health check with service status"""
        status_data = service_state.get_status()
        return jsonify(status_data), 200 if service_state.all_ready() else 202
    
    @app.route('/webhook', methods=['POST'])
    def webhook():
        """Webhook endpoint - always responds quickly"""
        return "OK", 200
    
    @app.route('/')
    def root():
        """Root endpoint"""
        return jsonify({
            'service': 'Finance Tracker Bot',
            'status': 'running',
            'timestamp': datetime.now().isoformat()
        })
    
    service_state.flask_app = app
    return app

# Service-ready command handlers
async def handle_start_with_check(update: Update, context: CallbackContext):
    """Start command with service readiness check"""
    if not service_state.all_ready():
        elapsed = (datetime.now() - service_state.initialization_start).total_seconds()
        await update.message.reply_text(
            "🔄 **Bot is starting up...**\n"
            f"⏱️ Elapsed: {elapsed:.0f}s\n"
            "🤖 Services loading, please wait!"
        )
        return
    
    await start(update, context)

async def handle_text_with_check(update: Update, context: CallbackContext):
    """Text handler with graceful service checking"""
    if not service_state.all_ready():
        services_status = "".join([
            f"{'✅' if service_state.sheets_ready else '⏳'} Sheets  ",
            f"{'✅' if service_state.ai_ready else '⏳'} AI  ",
            f"{'✅' if service_state.vision_ready else '⏳'} Vision"
        ])
        
        await update.message.reply_text(
            "⏳ **Services still loading...**\n"
            f"{services_status}\n"
            "📱 Please try again in a moment"
        )
        return
    
    await handle_text(update, context)

async def handle_photo_with_check(update: Update, context: CallbackContext):
    """Photo handler with vision service check"""
    if not service_state.vision_ready:
        await update.message.reply_text(
            "📷 **Vision API loading...**\n"
            "⏱️ Please wait and try again\n"
            "🔄 Google Vision initializing..."
        )
        return
    
    await handle_photo(update, context)

async def handle_summary_with_check(update: Update, context: CallbackContext):
    """Summary with sheets check"""
    if not service_state.sheets_ready:
        await update.message.reply_text(
            "📊 **Google Sheets connecting...**\n"
            "⏳ Please try again in a moment"
        )
        return
    
    await summary_command(update, context)

async def handle_categories_with_check(update: Update, context: CallbackContext):
    """Categories with sheets check"""
    if not service_state.sheets_ready:
        await update.message.reply_text(
            "📋 **Loading categories...**\n"
            "⏳ Please try again in a moment"
        )
        return
    
    await categories_command(update, context)

# Command handlers
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
• /categories - Lihat kategori yang tersedia
• /help - Bantuan ini

**Foto struk:** Kirim foto receipt untuk parsing otomatis dengan AI
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def summary_command(update: Update, context: CallbackContext):
    if sheets_manager:
        summary = sheets_manager.get_monthly_summary()
        await update.message.reply_text(summary, parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Sheets manager not available")

async def categories_command(update: Update, context: CallbackContext):
    """Show available categories"""
    if sheets_manager:
        categories = sheets_manager.get_categories()
        category_list = "\n".join([f"• {cat}" for cat in categories])
        response = f"📋 **Available Categories:**\n{category_list}"
        await update.message.reply_text(response, parse_mode='Markdown')
    else:
        await update.message.reply_text("❌ Sheets manager not available")

# Message handlers
async def handle_text(update: Update, context: CallbackContext):
    """Handle text expense input"""
    user_text = update.message.text
    message_date = update.message.date
    user_name = update.message.from_user.username or update.message.from_user.first_name
    
    processing_msg = await update.message.reply_text("🔄 Memproses pengeluaran...")
    
    try:
        # Parse with AI processor
        if ai_processor:
            expense_data = ai_processor.parse_expense_text(user_text, message_date, user_name)
        else:
            expense_data = {'error': 'AI processor not available'}
        
        # Use fallback if AI fails
        if expense_data.get('error'):
            expense_data = _fallback_parse(user_text, message_date, user_name)
            expense_data['source'] = 'Fallback Parser'
        else:
            expense_data['source'] = 'Gemini AI'
        
        # Save to Google Sheets
        success = sheets_manager.add_expense(expense_data) if sheets_manager else False
        
        if success:
            response = ResponseFormatter.format_expense_confirmation(expense_data)
        else:
            response = ResponseFormatter.format_error_message("Gagal menyimpan ke Google Sheets")
        
        await processing_msg.edit_text(response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error processing text: {e}")
        await processing_msg.edit_text("❌ Terjadi kesalahan saat memproses")

async def handle_photo(update: Update, context: CallbackContext):
    """Handle receipt photo processing with Google Vision API"""
    user_name = update.message.from_user.username or update.message.from_user.first_name
    message_date = update.message.date
    processing_msg = await update.message.reply_text("📷 Analyzing receipt with Google Vision AI...")
    
    try:
        # Download photo
        photo_file = await update.message.photo[-1].get_file()
        photo_path = "temp_receipt.jpg"
        await photo_file.download_to_drive(photo_path)
        
        logger.info(f"📸 Photo downloaded: {photo_path}")
        
        # Process with Vision API
        if vision_processor:
            receipt_data = vision_processor.extract_receipt_data(photo_path, message_date, user_name)
        else:
            await processing_msg.edit_text("❌ Vision processor not available")
            return
        
        # Clean up temp file
        if os.path.exists(photo_path):
            os.remove(photo_path)
            logger.info("🧹 Temp photo file cleaned up")
        
        # Handle errors
        if receipt_data.get('error'):
            await processing_msg.edit_text(f"❌ Receipt analysis failed: {receipt_data['error']}")
            return
        
        # Save to Google Sheets
        success = sheets_manager.add_expense(receipt_data) if sheets_manager else False
        
        if success:
            response = f"""
✅ **Receipt successfully processed!**

📝 **Extracted details:**
• **Date:** {receipt_data.get('transaction_date')}
• **Description:** {receipt_data.get('description', 'N/A')}
• **Amount:** Rp {receipt_data.get('amount', 0):,.0f}
• **Merchant:** {receipt_data.get('location', 'N/A')}
• **Category:** {receipt_data.get('category', 'N/A')}
• **Processed by:** {user_name}

📸 **Source:** Google Vision API
💾 **Status:** Saved to Google Sheets
            """
        else:
            response = f"""
⚠️ **Receipt processed but failed to save**

📝 **Extracted details:**
• **Amount:** Rp {receipt_data.get('amount', 0):,.0f}
• **Merchant:** {receipt_data.get('location', 'N/A')}

❌ Google Sheets connection issue
            """
        
        await processing_msg.edit_text(response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ Error processing receipt: {e}")
        
        # Cleanup
        if os.path.exists("temp_receipt.jpg"):
            os.remove("temp_receipt.jpg")
        
        await processing_msg.edit_text("❌ Failed to process receipt image")

def _fallback_parse(text, message_date, user_name):
    """Simple regex-based expense parser as fallback"""
    
    # Extract amount
    amount = 0
    amount_patterns = [
        r'(\d+)(?:ribu|rb)',  # "4ribu" → 4000
        r'(\d+)k',            # "20k" → 20000  
        r'(\d+)(?:000)',      # "25000" → 25000
        r'(\d+)'              # fallback to any number
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
    category = 'Other'
    if any(word in text.lower() for word in ['makan', 'beli', 'food', 'goreng']):
        category = 'Food'
    elif any(word in text.lower() for word in ['bensin', 'grab', 'gojek']):
        category = 'Transport'
    
    return {
        'description': text[:50].capitalize(),
        'amount': amount,
        'location': 'Unknown',
        'category': category,
        'transaction_date': message_date.strftime('%Y-%m-%d') if message_date else datetime.now().strftime('%Y-%m-%d'),
        'input_by': user_name or 'Unknown'
    }

async def run_bot_sync():
    """Run bot with pre-warming keep-alive service"""
    logger.info("🚀 Starting bot with pre-warming keep-alive...")
    
    """Synchronous bot runner for Render deployment"""
    logger.info("🚀 Starting bot with pre-warming keep-alive...")
    
    # Get deployment configuration
    port = int(os.environ.get('PORT', 8000))
    render_url = os.environ.get('RENDER_EXTERNAL_URL')
    
    logger.info(f"📍 Port: {port}")
    logger.info(f"📍 Render URL: {render_url}")

    # Create Telegram application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers with service-ready checks
    application.add_handler(CommandHandler("start", handle_start_with_check))
    application.add_handler(CommandHandler("help", help_command))  # Always available
    application.add_handler(CommandHandler("summary", handle_summary_with_check))
    application.add_handler(CommandHandler("categories", handle_categories_with_check))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_with_check))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo_with_check))
    
    logger.info("✅ Handlers registered with service checks")

    # Start keep-alive as background task within bot's event loop
    if render_url:
        from keep_alive import keep_alive
        
        async def start_keepalive():
            asyncio.create_task(keep_alive())
        
        application.post_init = start_keepalive
    
    if render_url:
        # Production webhook mode
        webhook_url = f"{render_url}/webhook"
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=webhook_url,
            url_path="/webhook",
            drop_pending_updates=True,
            secret_token=os.getenv('WEBHOOK_SECRET', ''),
            max_connections=100,
            allowed_updates=['message', 'callback_query']
        )
    else:
        application.run_polling()

def main():
    """Main function with comprehensive error handling"""
    logger.info("🚀 Starting Finance Tracker Bot with Pre-warming...")
    
    try:
        # Validate environment
        if not TELEGRAM_BOT_TOKEN:
            logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
            sys.exit(1)

        # Start background initialization immediately
        init_thread = threading.Thread(target=initialize_services_background, daemon=True)
        init_thread.start()
        logger.info("🔧 Background service initialization started")

        # Run the async bot_sync
        run_bot_sync()

    except Exception as e:
        logger.error(f"❌ Bot startup failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
