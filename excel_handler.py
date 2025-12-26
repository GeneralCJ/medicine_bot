import pandas as pd
import os
from datetime import datetime, date
from typing import List, Dict, Optional
from config import TRANSACTIONS_DIR, REPORTS_DIR

class ExcelHandler:
    # --- INITIALIZATION ---
    def __init__(self):
        self.transactions_dir = TRANSACTIONS_DIR
        self.reports_dir = REPORTS_DIR

    # --- IMPORT OPERATIONS ---
    def read_inventory_excel(self, file_path: str) -> pd.DataFrame:
        """Read inventory from CSV or Excel file and clean column names."""
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == '.csv':
            df = pd.read_csv(file_path)
        elif ext in ['.xlsx', '.xls']:
            df = pd.read_excel(file_path)
        else:
            raise ValueError("Unsupported file format. Please use .csv, .xlsx, or .xls")
        
        # Strip whitespace from column names
        df.columns = [str(c).strip() for c in df.columns]
        return df

    # --- TRANSACTION LOGGING ---
    def get_today_file_path(self) -> str:
        """Return path for today's transaction Excel file."""
        filename = f"transactions_{date.today().isoformat()}.xlsx"
        return os.path.join(self.transactions_dir, filename)

    def add_transaction(self, transaction: Dict):
        """Add a single transaction to today's Excel file."""
        self.add_multiple_transactions([transaction])

    def add_multiple_transactions(self, transactions: List[Dict]):
        """Add multiple transactions to today's Excel file efficiently."""
        file_path = self.get_today_file_path()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        new_data = []
        for tx in transactions:
            new_data.append({
                'Timestamp': timestamp,
                'Medicine Name': tx.get('medicine_name'),
                'Quantity': tx.get('quantity'),
                'Price': tx.get('price'),
                'Type': tx.get('type', 'sold'),
                'Remaining Stock': tx.get('remaining_stock')
            })
        
        new_df = pd.DataFrame(new_data)
        
        if os.path.exists(file_path):
            existing_df = pd.read_excel(file_path)
            updated_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            updated_df = new_df
            
        updated_df.to_excel(file_path, index=False)

    def get_today_transactions(self) -> Optional[str]:
        """Return path to today's transaction file if it exists."""
        file_path = self.get_today_file_path()
        return file_path if os.path.exists(file_path) else None

    # --- REPORT GENERATION ---
    def generate_daily_report(self, medicines: List[Dict], transactions_file: Optional[str] = None) -> str:
        """Generate a comprehensive multi-sheet daily Excel report."""
        report_date = date.today().isoformat()
        file_path = os.path.join(self.reports_dir, f"daily_report_{report_date}.xlsx")
        
        with pd.ExcelWriter(file_path, engine='openpyxl') as writer:
            # 1. Inventory Sheet
            inv_data = []
            total_stock_value = 0
            low_stock_count = 0
            
            for med in medicines:
                stock_value = med['stock'] * med['price']
                total_stock_value += stock_value
                
                # Determine Status
                status = "✓ OK"
                if med['stock'] <= 5: # Critical threshold from config logic
                    status = "🚨 CRITICAL"
                    low_stock_count += 1
                elif med['stock'] <= med['min_stock']:
                    status = "⚠️ LOW"
                    low_stock_count += 1
                
                inv_data.append({
                    'Medicine Name': med['name'],
                    'Current Stock': med['stock'],
                    'Min Stock': med['min_stock'],
                    'Price': med['price'],
                    'Stock Value': stock_value,
                    'Status': status
                })
            
            inv_df = pd.DataFrame(inv_data)
            inv_df.to_excel(writer, sheet_name='Inventory', index=False)
            
            # 2. Transactions Sheet
            today_sales_total = 0
            today_items_sold = 0
            if transactions_file and os.path.exists(transactions_file):
                tx_df = pd.read_excel(transactions_file)
                tx_df.to_excel(writer, sheet_name='Transactions', index=False)
                
                # Calculate metrics for summary
                sold_df = tx_df[tx_df['Type'] == 'sold']
                today_sales_total = (sold_df['Quantity'] * sold_df['Price']).sum()
                today_items_sold = sold_df['Quantity'].sum()
            else:
                pd.DataFrame([{'Info': 'No transactions today'}]).to_excel(writer, sheet_name='Transactions', index=False)

            # 3. Low Stock Alert Sheet
            low_stock_df = inv_df[inv_df['Status'].str.contains('LOW|CRITICAL')]
            low_stock_df.to_excel(writer, sheet_name='Low Stock Alert', index=False)
            
            # 4. Summary Sheet
            summary_data = {
                'Metric': [
                    'Report Date',
                    'Total Products',
                    'Total Stock Value',
                    'Low Stock Items',
                    'Today\'s Total Sales',
                    'Today\'s Items Sold'
                ],
                'Value': [
                    report_date,
                    len(medicines),
                    f"{total_stock_value:.2f}",
                    low_stock_count,
                    f"{today_sales_total:.2f}",
                    today_items_sold
                ]
            }
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)

        return file_path

    def generate_inventory_report(self, medicines: List[Dict]) -> str:
        """Generate a simple inventory-only Excel report."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        file_path = os.path.join(self.reports_dir, f"inventory_{timestamp}.xlsx")
        
        data = []
        for med in medicines:
            data.append({
                'Medicine Name': med['name'],
                'Current Stock': med['stock'],
                'Min Stock': med['min_stock'],
                'Price': med['price'],
                'Last Updated': med.get('updated_at', 'N/A')
            })
            
        df = pd.DataFrame(data)
        df.to_excel(file_path, index=False)
        return file_path
