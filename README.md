Finance Tracker Bot
A Telegram bot for automated expense tracking with AI-powered parsing. Send text expenses like "beli telur 2 kotak di alfamart 50ribu" or upload receipt photos for automatic processing using Google Vision API. The bot uses Gemini AI for intelligent text parsing, categorization, and stores all data in Google Sheets for easy tracking and analysis. Features include monthly summaries, category management, and graceful service initialization with external keep-alive system optimized for Render's free tier deployment.

Key Features: Text & photo expense input - AI-powered parsing (Gemini + Google Vision) - Google Sheets integration - Monthly summaries - External cron-based keep-alive - Zero cold-start during active hours (6 AM - 11 PM)

Commands: /start - Welcome message - /help - Usage guide - /summary - Monthly overview - /categories - Available categories - /warmup - System initialization

Deployment: Render free tier with external cron-job.org scheduling for optimal resource usage and 24/7 availability during active hours.