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
        """Advanced pre-warming with multiple endpoints"""
        if not self.render_url or not self.session:
            logger.warning("Cannot pre-warm: missing URL or session")
            return
            
        endpoints = [
            f"{self.render_url}/health",
            f"{self.render_url}/webhook",  # Warm webhook endpoint
        ]
        
        logger.info("🔥 Starting pre-warming sequence...")
        
        # Create session for pre-warming
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for endpoint in endpoints:
                try:
                    async with session.get(endpoint) as response:
                        logger.info(f"✅ Pre-warmed: {endpoint} ({response.status})")
                        await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"⚠️ Pre-warm failed for {endpoint}: {e}")
        
        # Additional warm-up: simulate service initialization
        await self.warm_up_initialization()
    
    async def warm_up_initialization(self):
        """Simulate service initialization to pre-load components"""
        logger.info("🔧 Warming up service initialization...")
        
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for i in range(3):
                try:
                    async with session.get(f"{self.render_url}/health") as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('status') == 'healthy':
                                logger.info(f"✅ Initialization check {i+1}/3: Healthy")
                                break
                        else:
                            logger.info(f"⏳ Initialization check {i+1}/3: Status {response.status}")
                except Exception as e:
                    logger.warning(f"⚠️ Initialization check {i+1}/3 failed: {e}")
                
                await asyncio.sleep(5)

    async def ping_health_endpoint(self):
        """Regular health check ping with better error handling"""
        if not self.render_url:
            return False
            
        try:
            # Create fresh session for each request to avoid SSL context issues
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{self.render_url}/health") as response:
                    if response.status == 200:
                        current_time = datetime.now(self.timezone).strftime('%H:%M:%S')
                        logger.info(f"✅ Keep-alive ping successful at {current_time}")
                        return True
                    else:
                        logger.warning(f"⚠️ Keep-alive ping returned {response.status}")
                        return False
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
