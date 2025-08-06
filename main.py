import logging
import os
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from ai_processor import AIProcessor
from ocr_processor import OCRProcessor
from sheets_manager import SheetsManager
from config import TELEGRAM_BOT_TOKEN

# Simple health check handler
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Bot is running')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress HTTP server logs

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize processors
ai_processor = AIProcessor()
ocr_processor = OCRProcessor()
sheets_manager = SheetsManager()

# Your existing handler functions (start, help_command, etc.)
async def start(update: Update, context: CallbackContext):
    """Start command handler"""
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

**Contoh valid:**
• ✅ "beli sayur 15ribu di pasar"
• ✅ "bensin 20k shell"  
• ✅ "lunch 35000 mall"

**Commands:**
• /start - Mulai bot
• /summary - Ringkasan bulanan
• /help - Bantuan ini

**Foto struk:** Kirim foto receipt/struk untuk parsing otomatis
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def summary_command(update: Update, context: CallbackContext):
    summary = sheets_manager.get_monthly_summary()
    await update.message.reply_text(summary, parse_mode='Markdown')

async def handle_text(update: Update, context: CallbackContext):
    user_text = update.message.text
    processing_msg = await update.message.reply_text("🔄 Memproses pengeluaran...")
    
    try:
        expense_data = ai_processor.parse_expense_text(user_text)
        
        if expense_data.get('error'):
            await processing_msg.edit_text(f"❌ Error: {expense_data['error']}")
            return
        
        success = sheets_manager.add_expense(expense_data)
        
        if success:
            response = f"""
✅ **Pengeluaran berhasil dicatat!**

📝 **Detail:**
• **Deskripsi:** {expense_data.get('description', 'N/A')}
• **Jumlah:** Rp {expense_data.get('amount', 0):,.0f}
• **Lokasi:** {expense_data.get('location', 'N/A')}
• **Kategori:** {expense_data.get('category', 'N/A')}

💾 Data tersimpan di Google Sheets
            """
        else:
            response = "❌ Gagal menyimpan ke Google Sheets"
        
        await processing_msg.edit_text(response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error processing text: {e}")
        await processing_msg.edit_text("❌ Terjadi kesalahan saat memproses")

async def handle_photo(update: Update, context: CallbackContext):
    processing_msg = await update.message.reply_text("📷 Memproses foto struk...")
    
    try:
        photo_file = await update.message.photo[-1].get_file()
        photo_path = "temp_receipt.jpg"
        await photo_file.download_to_drive(photo_path)
        
        ocr_text = ocr_processor.extract_text_from_image(photo_path)
        expense_data = ai_processor.parse_expense_text(ocr_text)
        expense_data['source'] = 'Photo Receipt'
        
        if os.path.exists(photo_path):
            os.remove(photo_path)
        
        if expense_data.get('error'):
            await processing_msg.edit_text(f"❌ Tidak dapat membaca struk: {expense_data['error']}")
            return
        
        success = sheets_manager.add_expense(expense_data)
        
        if success:
            response = f"""
✅ **Struk berhasil diproses!**

📝 **Detail dari foto:**
• **Deskripsi:** {expense_data.get('description', 'N/A')}
• **Jumlah:** Rp {expense_data.get('amount', 0):,.0f}
• **Lokasi:** {expense_data.get('location', 'N/A')}
• **Kategori:** {expense_data.get('category', 'N/A')}

📸 Sumber: Foto struk
💾 Data tersimpan di Google Sheets
            """
        else:
            response = "❌ Gagal menyimpan ke Google Sheets"
        
        await processing_msg.edit_text(response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error processing photo: {e}")
        await processing_msg.edit_text("❌ Gagal memproses foto struk")

def start_health_server():
    """Start HTTP server for Render health checks"""
    port = int(os.environ.get('PORT', 10000))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    logger.info(f"🌐 Health check server starting on port {port}")
    server.serve_forever()

def main():
    """Main function with health check server"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found!")
        return
    
    # Start health check server in background thread
    health_thread = Thread(target=start_health_server, daemon=True)
    health_thread.start()
    
    # Create Telegram application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("summary", summary_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    logger.info("🚀 Starting Finance Tracker Bot...")
    print("🤖 Bot starting - with health check endpoint")
    
    # Run bot polling
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True
    )

if __name__ == '__main__':
    main()
