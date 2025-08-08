# start_services.py - SIMPLIFIED VERSION
from main import main as run_bot_main

def main():
    """Simple single-process startup"""
    print("🚀 Starting Finance Tracker Bot...")
    
    # Just run the main bot function directly - no threading
    run_bot_main()

if __name__ == '__main__':
    main()
