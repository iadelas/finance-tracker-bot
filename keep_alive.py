# keep_alive.py
import asyncio
import aiohttp
import os
from datetime import datetime, time as time_obj
import pytz
import logging

logger = logging.getLogger(__name__)

class TimeBasedKeepAliveWithPrewarming:
    def __init__(self):
        self.render_url = os.environ.get('RENDER_EXTERNAL_URL')
        self.timezone = pytz.timezone('Asia/Jakarta')  # Adjust to your timezone
        self.start_time = time_obj(6, 0)   # 06:00
        self.end_time = time_obj(23, 59)   # 23:59
        self.session = None
        
    def is_active_hours(self):
        """Check if current time is within active hours (06:00-24:00)"""
        now = datetime.now(self.timezone).time()
        return self.start_time <= now <= self.end_time
    
    def get_next_active_time(self):
        """Calculate seconds until next active period starts"""
        from datetime import timedelta
        
        now = datetime.now(self.timezone)
        current_time = now.time()
        
        if self.is_active_hours():
            return 0  # Already in active hours
        
        # Calculate next 06:00
        if current_time < self.start_time:
            # Before 06:00 today
            next_active = now.replace(
                hour=self.start_time.hour, 
                minute=self.start_time.minute, 
                second=0, 
                microsecond=0
            )
        else:
            # After 24:00, wait until 06:00 tomorrow
            next_active = (now.replace(
                hour=self.start_time.hour, 
                minute=self.start_time.minute, 
                second=0, 
                microsecond=0
            ) + timedelta(days=1))
        
        return int((next_active - now).total_seconds())

    async def pre_warm_services(self):
        """Simple pre-warming with basic connectivity"""
        if not self.render_url:
            logger.warning("Cannot pre-warm: missing URL")
            return
            
        logger.info("🔥 Starting pre-warming sequence...")
        
        # Just ping the service 3 times to wake it up
        for i in range(3):
            await self.ping_health_endpoint()
            await asyncio.sleep(2)
            
            # Additional warm-up: simulate service initialization
            await self.warm_up_initialization()
    
    async def warm_up_initialization(self):
        """Warm up using webhook endpoint"""
        logger.info("🔧 Warming up service initialization...")

    async def ping_health_endpoint(self):
        """Regular health check ping with better error handling"""
        if not self.render_url:
            return False
            
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Just hit the base domain without any path - this will keep service awake
                base_url = self.render_url.rstrip('/')  # Remove trailing slash if any
                async with session.get(base_url) as response:
                    # Any response (even 404) means service is alive
                    current_time = datetime.now(self.timezone).strftime('%H:%M:%S')
                    logger.info(f"✅ Keep-alive ping successful at {current_time} (status: {response.status})")
                    return True
        except Exception as e:
            logger.error(f"❌ Keep-alive ping failed: {e}")
            return False

    async def wake_up_sequence(self):
        """Execute comprehensive wake-up sequence at 06:00"""
        logger.info("🌅 Executing wake-up sequence...")
        
        # Step 1: Pre-warm services
        await self.pre_warm_services()
        
        # Step 2: Wait for services to stabilize
        await asyncio.sleep(30)
        
        # Step 3: Final health check
        if await self.ping_health_endpoint():
            logger.info("✅ Wake-up sequence completed successfully")
        else:
            logger.warning("⚠️ Wake-up sequence completed with warnings")
    
    async def keep_alive_scheduled(self):
        """Enhanced keep-alive with comprehensive pre-warming"""
        logger.info(f"🕐 Keep-alive service started (Active: {self.start_time}-{self.end_time})")
        
        while True:
            if self.is_active_hours():
                current_time = datetime.now(self.timezone).time()
                
                # Execute wake-up sequence at start of active hours (06:00-06:15)
                if (current_time.hour == 6 and current_time.minute < 15):
                    await self.wake_up_sequence()
                else:
                    # Regular ping during active hours
                    await self.ping_health_endpoint()
                
                # Wait 14 minutes (840 seconds)
                await asyncio.sleep(840)
            else:
                # Sleep until next active period
                sleep_seconds = self.get_next_active_time()
                sleep_hours = sleep_seconds / 3600
                logger.info(f"😴 Outside active hours. Sleeping for {sleep_hours:.1f} hours until 06:00")
                await asyncio.sleep(sleep_seconds)

# Main function for integration
async def keep_alive():
    """Export function for main.py integration"""
    keeper = TimeBasedKeepAliveWithPrewarming()  # Remove async with
    await keeper.keep_alive_scheduled()
