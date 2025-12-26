from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz
import pandas as pd
import os
from config import DAILY_REPORT_HOUR, DAILY_REPORT_MINUTE, TIMEZONE, AUTHORIZED_USERS

class ReportScheduler:
    # --- INITIALIZATION ---
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=pytz.timezone(TIMEZONE))
        self.bot = None
        self.db = None
        self.excel_handler = None

    def setup(self, bot, db, excel_handler):
        """Set references to bot, database, and excel_handler for report generation."""
        self.bot = bot
        self.db = db
        self.excel_handler = excel_handler

    # --- REPORT TASK ---
    async def send_daily_report(self):
        """Generate and send the daily report to all authorized users."""
        if not all([self.bot, self.db, self.excel_handler]):
            print("Scheduler Error: Components not configured.")
            return

        try:
            # 1. Gather Data
            medicines = self.db.get_all_medicines()
            tx_file = self.excel_handler.get_today_transactions()
            report_path = self.excel_handler.generate_daily_report(medicines, tx_file)
            
            # 2. Calculate Brief Summary
            today_sales_total = 0
            if tx_file and os.path.exists(tx_file):
                tx_df = pd.read_excel(tx_file)
                sold_df = tx_df[tx_df['Type'] == 'sold']
                today_sales_total = (sold_df['Quantity'] * sold_df['Price']).sum()

            low_stock_items = self.db.get_low_stock_medicines()
            report_date = datetime.now().strftime("%Y-%m-%d")

            summary_msg = (
                f"📊 *Daily Inventory Report: {report_date}*\n\n"
                f"💰 Today's Total Sales: ₹{today_sales_total:,.2f}\n"
                f"📦 Total Products in DB: {len(medicines)}\n"
                f"⚠️ Low Stock Items: {len(low_stock_items)}\n\n"
                f"Please find the detailed report attached below."
            )

            # 3. Send to Authorized Users
            for user_id in AUTHORIZED_USERS:
                try:
                    # Send message
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=summary_msg,
                        parse_mode='Markdown'
                    )
                    # Send Excel file
                    with open(report_path, 'rb') as f:
                        await self.bot.send_document(
                            chat_id=user_id,
                            document=f,
                            filename=os.path.basename(report_path)
                        )
                except Exception as e:
                    print(f"Error sending report to user {user_id}: {str(e)}")

        except Exception as e:
            print(f"Critial status in scheduled report: {str(e)}")

    # --- SCHEDULER CONTROL ---
    def start(self):
        """Add the daily report job and start the scheduler."""
        trigger = CronTrigger(
            hour=DAILY_REPORT_HOUR, 
            minute=DAILY_REPORT_MINUTE
        )
        
        self.scheduler.add_job(
            self.send_daily_report,
            trigger=trigger,
            id='daily_report',
            replace_existing=True
        )
        
        self.scheduler.start()
        print(f"Scheduler started: Daily report set for {DAILY_REPORT_HOUR:02d}:{DAILY_REPORT_MINUTE:02d}")

    def stop(self):
        """Shut down the scheduler."""
        self.scheduler.shutdown()
        print("Scheduler stopped.")
