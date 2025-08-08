# keepalive_service.py - SEPARATE KEEP-ALIVE PROCESS
import asyncio
import aiohttp
import os
from datetime import datetime, time as time_obj
import pytz
import logging
import signal
import sys

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class StandaloneKeepAlive:
    def __init__(self):
        self.render_url = os.environ.get('RENDER_EXTERNAL_URL')
        self.timezone = pytz.timezone('Asia/Jakarta')
        self.start_time = time_obj(6, 0)
        self.end_time = time_obj(23, 59)
        self.running = True
        
        # Handle shutdown signals
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        logger.info(f"🛑 Received signal {signum}, shutting down...")
        self.running = False
    
    def is_active_hours(self):
        now = datetime.now(self.timezone).time()
        return self.start_time <= now <= self.end_time
    
    def get_next_active_time(self):
        from datetime import timedelta
        now = datetime.now(self.timezone)
        current_time = now.time()
        
        if self.is_active_hours():
            return 0
        
        if current_time < self.start_time:
            next_active = now.replace(
                hour=self.start_time.hour,
                minute=self.start_time.minute,
                second=0,
                microsecond=0
            )
        else:
            next_active = (now.replace(
                hour=self.start_time.hour,
                minute=self.start_time.minute,
                second=0,
                microsecond=0
            ) + timedelta(days=1))
        
        return int((next_active - now).total_seconds())

    async def ping_service(self):
        if not self.render_url:
            return False
            
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                base_url = self.render_url.rstrip('/')
                async with session.get(base_url) as response:
                    current_time = datetime.now(self.timezone).strftime('%H:%M:%S')
                    logger.info(f"✅ Keep-alive ping at {current_time} (status: {response.status})")
                    return True
        except Exception as e:
            logger.error(f"❌ Keep-alive ping failed: {e}")
            return False

    async def pre_warm(self):
        logger.info("🔥 Pre-warming service...")
        for i in range(3):
            await self.ping_service()
            await asyncio.sleep(2)
        logger.info("✅ Pre-warming completed")

    async def wake_up_sequence(self):
        logger.info("🌅 Wake-up sequence starting...")
        await self.pre_warm()
        await asyncio.sleep(10)
        await self.ping_service()
        logger.info("✅ Wake-up sequence completed")

    async def run(self):
        logger.info(f"🕐 Keep-alive service started (Active: {self.start_time}-{self.end_time})")
        
        while self.running:
            try:
                if self.is_active_hours():
                    current_time = datetime.now(self.timezone).time()
                    
                    # Wake-up sequence at 06:00-06:15
                    if current_time.hour == 6 and current_time.minute < 15:
                        await self.wake_up_sequence()
                    else:
                        await self.ping_service()
                    
                    # Wait 14 minutes
                    for _ in range(840):  # 840 seconds = 14 minutes
                        if not self.running:
                            break
                        await asyncio.sleep(1)
                else:
                    # Sleep until active hours
                    sleep_seconds = self.get_next_active_time()
                    sleep_hours = sleep_seconds / 3600
                    logger.info(f"😴 Sleeping for {sleep_hours:.1f} hours until 06:00")
                    
                    # Sleep in chunks to allow graceful shutdown
                    while sleep_seconds > 0 and self.running:
                        chunk = min(60, sleep_seconds)  # Sleep in 1-minute chunks
                        await asyncio.sleep(chunk)
                        sleep_seconds -= chunk
                        
            except Exception as e:
                logger.error(f"❌ Keep-alive error: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

async def main():
    keep_alive = StandaloneKeepAlive()
    await keep_alive.run()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Keep-alive service stopped")
    except Exception as e:
        logger.error(f"❌ Keep-alive service failed: {e}")
        sys.exit(1)
