import os

# TELEGRAM SETTINGS
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
AUTHORIZED_USERS = []  # Add authorized Telegram user IDs here (e.g., [123456789])

# INVENTORY SETTINGS
DEFAULT_MIN_STOCK = 20
LOW_STOCK_THRESHOLD = 1.5  # multiply with min_stock to get warning level
CRITICAL_STOCK_THRESHOLD = 5

# FILE PATHS
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TRANSACTIONS_DIR = os.path.join(DATA_DIR, "transactions")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")
INVENTORY_FILE = os.path.join(DATA_DIR, "inventory.json")

# Auto-create directories if they don't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(TRANSACTIONS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# DAILY REPORT SETTINGS
DAILY_REPORT_HOUR = 21  # 9 PM
DAILY_REPORT_MINUTE = 0
TIMEZONE = "Asia/Kolkata"
