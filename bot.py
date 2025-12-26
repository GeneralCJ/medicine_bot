import logging
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler

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
        ['📥 Today\'s Sales', '📊 Full Report'],
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
    """Check if the user is authorized to use the bot."""
    if not AUTHORIZED_USERS:  # Allow all if empty (for testing)
        return True
    return user_id in AUTHORIZED_USERS

# ════════════════════════════════════════════════════════════
# SECTION 6 - COMMAND HANDLERS
# ════════════════════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command: Authorization check and welcome message."""
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
    await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=MAIN_KEYBOARD)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command: Detailed instructions."""
    help_text = (
        "❓ *How to use the Bot*\n\n"
        "*1. UPLOAD INVENTORY*\n"
        "Send an Excel (.xlsx) or CSV file. Columns should be: `medicine_name`, `stock`, `min_stock`, `price`.\n\n"
        "*2. RECORD SALES*\n"
        "Send a message with one or more items:\n"
        "`medicine_name quantity price` (per line)\n"
        "Example:\n"
        "`aspirin 2 40`\n"
        "`vicks 1 50`\n\n"
        "*3. VIEW DATA*\n"
        "• *Inventory:* View all stock status.\n"
        "• *Low Stock:* View items below safety levels.\n"
        "• *Today's Sales:* Download current transaction log.\n\n"
        "*4. AUTO FEATURES*\n"
        "• Inventory is updated instantly after each sale.\n"
        "• Low stock warnings are sent if items reach critical levels.\n"
        "• Full report is auto-sent every day at 9 PM."
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def show_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Inventory button/command: List all medicines with status emojis."""
    medicines = db.get_all_medicines()
    if not medicines:
        await update.message.reply_text("📭 Database is empty. Please upload an Excel file first.")
        return

    response = "📦 *Current Inventory*\n\n"
    for med in medicines:
        status = db.check_stock_status(med)
        emoji = "✓"
        if status == 'critical': emoji = "🚨"
        elif status == 'low': emoji = "⚠️"
        
        line = f"{emoji} {med['name']}: *{med['stock']}*\n"
        
        if len(response) + len(line) > 3500:
            await update.message.reply_text(response, parse_mode='Markdown')
            response = ""
        response += line

    response += f"\n🔢 Total Medicines: *{len(medicines)}*"
    await update.message.reply_text(response, parse_mode='Markdown')

async def show_low_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Low Stock button/command: List items below threshold."""
    low_stock = db.get_low_stock_medicines()
    if not low_stock:
        await update.message.reply_text("✅ All items well stocked!")
        return

    response = "⚠️ *Low Stock Alert*\n\n"
    for med in low_stock:
        status = db.check_stock_status(med)
        emoji = "🚨" if status == 'critical' else "⚠️"
        response += f"{emoji} *{med['name']}*\nStock: {med['stock']} (Min: {med['min_stock']})\n\n"

    response += f"⚠️ Total items low on stock: *{len(low_stock)}*"
    await update.message.reply_text(response, parse_mode='Markdown')

async def send_today_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Today's Sales button: Send current transaction file."""
    tx_file = excel_handler.get_today_transactions()
    if not tx_file:
        await update.message.reply_text("📥 No transactions recorded today.")
        return

    with open(tx_file, 'rb') as f:
        await update.message.reply_document(document=f, filename=os.path.basename(tx_file))

async def send_full_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Full Report button: Generate and send comprehensive daily report."""
    medicines = db.get_all_medicines()
    if not medicines:
        await update.message.reply_text("❌ Cannot generate report: Database is empty.")
        return

    await update.message.reply_text("⏳ Generating comprehensive report, please wait...")
    
    tx_file = excel_handler.get_today_transactions()
    report_path = excel_handler.generate_daily_report(medicines, tx_file)
    
    with open(report_path, 'rb') as f:
        await update.message.reply_document(document=f, filename=os.path.basename(report_path))

# ════════════════════════════════════════════════════════════
# SECTION 7 - MESSAGE & DOCUMENT HANDLERS
# ════════════════════════════════════════════════════════════

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Excel/CSV file uploads to import inventory."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    doc = update.message.document
    file_name = doc.file_name.lower()
    
    if not (file_name.endswith('.xlsx') or file_name.endswith('.xls') or file_name.endswith('.csv')):
        await update.message.reply_text("❌ Invalid file format. Please upload .xlsx, .xls or .csv")
        return

    sent_msg = await update.message.reply_text("⏳ Processing file, please wait...")
    
    try:
        # Download and save temporary file
        temp_path = os.path.join("data", doc.file_name)
        new_file = await context.bot.get_file(doc.file_id)
        await new_file.download_to_drive(temp_path)
        
        # Read and Import
        df = excel_handler.read_inventory_excel(temp_path)
        success_count, errors = db.import_from_dataframe(df)
        
        # Cleanup
        if os.path.exists(temp_path):
            os.remove(temp_path)
        
        # Respond
        response = f"✅ Success! Imported *{success_count}* medicines."
        if errors:
            response += f"\n\n🚨 *Errors ({len(errors)}):*\n" + "\n".join(errors[:5])
            if len(errors) > 5: response += "\n...and more."
            
        await sent_msg.edit_text(response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Import error: {str(e)}")
        await sent_msg.edit_text(f"❌ Error processing file: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route text messages to commands or sales processor."""
    user_id = update.effective_user.id
    if not is_authorized(user_id):
        return

    text = update.message.text.strip()
    
    # Map button texts to internal commands
    button_map = {
        '📦 Inventory': 'inventory',
        '⚠️ Low Stock': 'low_stock',
        "📥 Today's Sales": 'today',
        '📊 Full Report': 'report',
        '❓ Help': 'help'
    }
    
    cmd_key = button_map.get(text)
    if not cmd_key:
        cmd_key = command_parser.parse_command(text)
        
    # Route to handlers
    if cmd_key == 'inventory': await show_inventory(update, context)
    elif cmd_key == 'low_stock': await show_low_stock(update, context)
    elif cmd_key == 'today': await send_today_transactions(update, context)
    elif cmd_key == 'report': await send_full_report(update, context)
    elif cmd_key == 'help': await help_command(update, context)
    elif sales_parser.is_sales_message(text):
        await process_sales(update, text)
    else:
        await update.message.reply_text(
            "🤔 I didn't understand that. Send sales in format:\n`medicine_name quantity price` or use buttons.",
            parse_mode='Markdown'
        )

async def process_sales(update: Update, message_text: str):
    """Parse and record sales, updating stock levels."""
    parsed_sales = sales_parser.parse_sales_message(message_text)
    
    if not parsed_sales:
        await update.message.reply_text("❌ Could not parse sales data. Use: `name qty price`", parse_mode='Markdown')
        return

    success_tx = []
    insufficient = []
    not_found = []
    low_stock_alerts = []
    total_sales_val = 0
    
    for sale in parsed_sales:
        med, score = db.find_medicine(sale['medicine_query'])
        
        if not med:
            not_found.append(sale['medicine_query'])
            continue
            
        # Update Stock
        updated_med = db.update_stock(med['id'], sale['quantity'], 'sold')
        
        if not updated_med:
            insufficient.append(f"{med['name']} (Stock: {med['stock']})")
        else:
            # Add to transaction logs
            tx_entry = {
                'medicine_name': updated_med['name'],
                'quantity': sale['quantity'],
                'price': sale['price'],
                'type': 'sold',
                'remaining_stock': updated_med['stock']
            }
            success_tx.append(tx_entry)
            total_sales_val += (sale['quantity'] * sale['price'])
            
            # Check for low stock alert
            status = db.check_stock_status(updated_med)
            if status in ['low', 'critical']:
                emoji = "🚨" if status == 'critical' else "⚠️"
                low_stock_alerts.append(f"{emoji} *{updated_med['name']}* is low! (Stock: {updated_med['stock']})")

    # Log to Excel
    if success_tx:
        excel_handler.add_multiple_transactions(success_tx)

    # Build Response
    response = "✅ *Sale Recorded*\n" + "─" * 20 + "\n"
    for tx in success_tx:
        response += f"• {tx['medicine_name']} x {tx['quantity']} = ₹{tx['quantity']*tx['price']}\n"
    
    response += f"\n💰 *Total: ₹{total_sales_val:,.2f}*\n"
    
    if insufficient:
        response += f"\n❌ *Insufficient Stock:*\n" + "\n".join(insufficient)
    if not_found:
        response += f"\n❓ *Not Found:*\n" + "\n".join(not_found)
    if low_stock_alerts:
        response += f"\n\n🔔 *Stock Warnings:*\n" + "\n".join(low_stock_alerts)

    await update.message.reply_text(response, parse_mode='Markdown')

# ════════════════════════════════════════════════════════════
# SECTION 8 - MAIN ENTRY POINT
# ════════════════════════════════════════════════════════════

def main():
    """Start the bot."""
    print("🚀 Starting Medicine Inventory Bot...")
    
    # 1. Create Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # 2. Add Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("inventory", show_inventory))
    application.add_handler(CommandHandler("low", show_low_stock))
    application.add_handler(CommandHandler("today", send_today_transactions))
    application.add_handler(CommandHandler("report", send_full_report))
    
    # 3. Add Document Handler (Excel/CSV imports)
    application.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    
    # 4. Add Message Handler (Sales and internal commands)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # 5. Setup & Start Scheduler
    report_scheduler.setup(application.bot, db, excel_handler)
    report_scheduler.start()
    
    # 6. Status Prints
    from config import DAILY_REPORT_HOUR, DAILY_REPORT_MINUTE
    print(f"✅ Bot is running!")
    print(f"📅 Daily report scheduled at {DAILY_REPORT_HOUR:02d}:{DAILY_REPORT_MINUTE:02d}")
    print(f"📦 Loaded {db.get_medicine_count()} medicines from database")
    
    # 7. Run Polling
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
