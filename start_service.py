# start_services.py
import asyncio
import threading
import time
from main import main as run_bot
from keep_alive import keep_alive

def run_bot_thread():
    """Run the bot in a separate thread"""
    try:
        run_bot()
    except Exception as e:
        print(f"❌ Bot thread error: {e}")

async def run_keepalive_async():
    """Run keep-alive service"""
    try:
        await keep_alive()
    except Exception as e:
        print(f"❌ Keep-alive error: {e}")

def main():
    """Start both bot and keep-alive services"""
    print("🚀 Starting Finance Tracker with separate keep-alive...")
    
    # Start bot in separate thread
    bot_thread = threading.Thread(target=run_bot_thread, daemon=True)
    bot_thread.start()
    
    # Wait a bit for bot to initialize
    time.sleep(10)
    
    # Start keep-alive in main thread
    asyncio.run(run_keepalive_async())

if __name__ == '__main__':
    main()
