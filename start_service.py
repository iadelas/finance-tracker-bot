# start_services.py - PROCESS MANAGER
import subprocess
import time
import os
import signal
import sys

def main():
    print("🚀 Starting Finance Tracker with separate keep-alive...")
    
    # Start bot process
    bot_process = subprocess.Popen([
        sys.executable, "main.py"
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    print(f"✅ Bot started with PID: {bot_process.pid}")
    
    # Wait for bot to initialize
    time.sleep(10)
    
    # Start keep-alive process (only if RENDER_EXTERNAL_URL exists)
    keepalive_process = None
    if os.environ.get('RENDER_EXTERNAL_URL'):
        keepalive_process = subprocess.Popen([
            sys.executable, "keepalive_service.py"
        ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        print(f"✅ Keep-alive started with PID: {keepalive_process.pid}")
    
    def cleanup(signum, frame):
        print("🛑 Shutting down services...")
        if bot_process:
            bot_process.terminate()
        if keepalive_process:
            keepalive_process.terminate()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    try:
        # Monitor processes
        while True:
            # Check bot process
            if bot_process.poll() is not None:
                print("❌ Bot process died, restarting...")
                bot_process = subprocess.Popen([
                    sys.executable, "main.py"
                ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            # Check keep-alive process
            if keepalive_process and keepalive_process.poll() is not None:
                print("❌ Keep-alive process died, restarting...")
                keepalive_process = subprocess.Popen([
                    sys.executable, "keepalive_service.py"
                ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            time.sleep(30)  # Check every 30 seconds
            
    except KeyboardInterrupt:
        cleanup(None, None)

if __name__ == '__main__':
    main()
