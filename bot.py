# ================== DEBUG (KEEP THIS) ==================
import sys
print("PYTHON:", sys.version)
print("🚀 Starting Medicine Inventory Bot...")

# ================== STANDARD IMPORTS ==================
import logging
import os

# ================== FUZZY MATCHING ==================
from thefuzz import fuzz   # ✅ correct replacement

# ================== TELEGRAM IMPORTS ==================
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# ================== ENV + CONFIG ==================
from config import AUTHORIZED_USERS   # ❌ DO NOT import BOT_TOKEN from config

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN not found in environment variables")

# ================== INTERNAL MODULES ==================
from database import InventoryDatabase
from excel_handler import ExcelHandler
from parser import SalesParser, CommandParser
from scheduler import ReportScheduler

# ================== LOGGING ==================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================== INITIALIZE CORE OBJECTS ==================
db = InventoryDatabase()
excel_handler = ExcelHandler()
sales_parser = SalesParser()
command_parser = CommandParser()
report_scheduler = ReportScheduler()

# ================== KEYBOARDS ==================
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["📦 Inventory", "⚠️ Low Stock"],
        ["📥 Today's Sales", "📊 Full Report"],
        ["❓ Help"]
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

# ================== AUTHORIZATION ==================
def is_authorized(user_id: int) -> bool:
    if not AUTHORIZED_USERS:
        return True
    return user_id in AUTHORIZED_USERS

# ================== COMMAND HANDLERS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if not is_authorized(user_id):
        await update.message.reply_text(f"❌ Unauthorized access.\nYour ID: {user_id}")
        return

    med_count = db.get_medicine_count()
    text = (
        "💊 *Medicine Inventory Bot*\n\n"
        f"📦 Medicines in database: *{med_count}*\n\n"
        "*How to use:*\n"
        "• Upload Excel/CSV to import stock\n"
        "• Send sales like:\n"
        "`crocin 10 150`\n"
        "`dolo 5 125`\n\n"
        "Use buttons below 👇"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "❓ *Help*\n\n"
        "📥 Upload inventory via Excel / CSV\n"
        "📤 Record sales using text format\n"
        "📊 View reports & low stock alerts\n\n"
        "⏰ Daily report is sent automatically"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# ================== PLACEHOLDER HANDLERS ==================
# ⚠️ Your existing implementations remain unchanged
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📄 Document received")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 Message received")

# ================== MAIN (STEP 5 FIXED HERE) ==================
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Scheduler must start BEFORE polling
    report_scheduler.setup(application.bot, db, excel_handler)
    report_scheduler.start()

    # 🔥 THIS LINE IS STEP 5 (DO NOT CHANGE)
    application.run_polling()

# ================== ENTRY POINT ==================
if __name__ == "__main__":
    main()
