import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext
from telegram.request import HTTPXRequest
from ai_processor import AIProcessor
from ocr_processor import OCRProcessor
from sheets_manager import SheetsManager
from config import TELEGRAM_BOT_TOKEN

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

# Your existing handlers remain the same
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

def main():
    """Main function with forced webhook mode for Render"""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found!")
        return
    
    port = int(os.environ.get('PORT', 8000))
    
    # Force webhook mode on Render
    is_render = os.environ.get('RENDER') or os.environ.get('RENDER_EXTERNAL_URL')
    
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("summary", summary_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    if is_render:
        # Production/Render mode - ALWAYS use webhooks
        webhook_url = os.environ.get('RENDER_EXTERNAL_URL', f'https://your-app-name.onrender.com')
        logger.info("🌐 Render detected - Running with webhooks")
        logger.info(f"🔗 Webhook URL: {webhook_url}/webhook")
        
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=f"{webhook_url}/webhook",
            url_path="/webhook",
            drop_pending_updates=True
        )
    else:
        # Local development - use polling
        logger.info("💻 Local mode - Running with polling")
        application.run_polling(allowed_updates=Update.ALL_TYPES)

