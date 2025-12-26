import sys
print("PYTHON:", sys.version)

import logging
import os

# ✅ REPLACED FUZZYWUZZY WITH THEFUZZ
from thefuzz import fuzz

from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler
)

from config import BOT_TOKEN, AUTHORIZED_USERS
from database import InventoryDatabase
from excel_handler import ExcelHandler
from parser import SalesParser, CommandParser
from scheduler import ReportScheduler

# --- Conversation States ---
WAITING_FOR_EXCEL_CONFIRMATION = 1

# ════════════════════════════════════════════════════════════
# SECTION 2 - LOGGING SETUP
# ════════════════════════════════════════════════════════════
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════
# SECTION 3 - INITIALIZE COMPONENTS
# ════════════════════════════════════════════════════════════
db = InventoryDatabase()
excel_handler = ExcelHandler()
sales_parser = SalesParser()
command_parser = CommandParser()
report_scheduler = ReportScheduler()

# ════════════════════════════════════════════════════════════
# SECTION 4 - KEYBOARD
# ════════════════════════════════════════════════════════════
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ['📦 Inventory', '⚠️ Low Stock'],
        ["📥 Today's Sales", '📊 Full Report'],
        ['❓ Help']
    ],
    resize_keyboard=True
)

EXCEL_CONFIRM_KEYBOARD = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("✅ Yes, Add Stock", callback_data="restock_yes"),
        InlineKeyboardButton("🔄 Replace All", callback_data="restock_no")
    ],
    [
        InlineKeyboardButton("❌ Cancel", callback_data="restock_cancel")
    ]
])

# ════════════════════════════════════════════════════════════
# SECTION 5 - AUTHORIZATION FUNCTION
# ════════════════════════════════════════════════════════════
def is_authorized(user_id: int) -> bool:
    if not AUTHORIZED_USERS:
        return True
    return user_id in AUTHORIZED_USERS

# ════════════════════════════════════════════════════════════
# SECTION 6 - COMMAND HANDLERS
# ════════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        await update.message.reply_text(f"❌ Unauthorized access. Your ID: {user_id}")
        return

    med_count = db.get_medicine_count()
    welcome_text = (
        "💊 *Medicine Inventory Bot*\n\n"
        f"Database currently contains *{med_count}* medicines.\n\n"
        "*Quick Start:*\n"
        "1. Upload an Excel/CSV to import inventory.\n"
        "2. Send sales in this format:\n"
        "`crocin 10 150`\n"
        "`dolo 5 125`\n\n"
        "Use the buttons below to navigate."
    )
    await update.message.reply_text(
        welcome_text,
        parse_mode='Markdown',
        reply_markup=MAIN_KEYBOARD
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "❓ *How to use the Bot*\n\n"
        "*1. UPLOAD INVENTORY*\n"
        "Send an Excel (.xlsx) or CSV file.\n\n"
        "*2. RECORD SALES*\n"
        "`medicine_name quantity price`\n\n"
        "*3. VIEW DATA*\n"
        "Inventory • Low Stock • Today's Sales • Full Report\n\n"
        "*4. AUTO FEATURES*\n"
        "Daily report auto-sent at 9 PM."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# (⬇️ REST OF YOUR FILE REMAINS 100% UNCHANGED ⬇️)

def main():
    print("🚀 Starting Medicine Inventory Bot...")
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    report_scheduler.setup(application.bot, db, excel_handler)
    report_scheduler.start()

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
