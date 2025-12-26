import re
from typing import List, Dict, Optional

class SalesParser:
    # --- INITIALIZATION ---
    def __init__(self):
        # Pattern: medicine_name (can have spaces) space quantity (digits) space price (digits or decimals)
        self.sales_pattern = re.compile(r'^(.+?)\s+(\d+)\s+([\d.]+)$')

    # --- SALES PARSING ---
    def parse_sales_message(self, message: str) -> List[Dict]:
        """Split message by newlines and parse each line into a sales dictionary."""
        lines = message.strip().split('\n')
        parsed_entries = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            entry = self.parse_single_line(line)
            if entry:
                parsed_entries.append(entry)
                
        return parsed_entries

    def parse_single_line(self, line: str) -> Optional[Dict]:
        """Attempt to parse a single line into medicine_query, quantity, and price."""
        match = self.sales_pattern.match(line)
        
        if match:
            return {
                'medicine_query': match.group(1).strip(),
                'quantity': int(match.group(2)),
                'price': float(match.group(3))
            }
        
        # Fallback split method if regex fails (last two parts must be numbers)
        parts = line.split()
        if len(parts) >= 3:
            try:
                price = float(parts[-1])
                quantity = int(parts[-2])
                medicine_query = " ".join(parts[:-2])
                return {
                    'medicine_query': medicine_query.strip(),
                    'quantity': quantity,
                    'price': price
                }
            except (ValueError, IndexError):
                return None
                
        return None

    def is_sales_message(self, message: str) -> bool:
        """Return True if at least one line can be correctly parsed as a sales entry."""
        lines = message.strip().split('\n')
        for line in lines:
            if line.strip() and self.parse_single_line(line.strip()):
                return True
        return False

class CommandParser:
    # --- COMMAND KEYWORDS ---
    COMMANDS = {
        'inventory': ['inventory', 'inv', 'stock', 'all', 'show all'],
        'low_stock': ['low', 'lowstock', 'low stock', 'shortage', 'kam'],
        'today': ['today', 'aaj', 'daily', 'transactions'],
        'report': ['report', 'full report', 'generate report'],
        'help': ['help', 'madad', 'commands', '?'],
        'upload': ['upload', 'import', 'excel']
    }

    # --- COMMAND PARSING ---
    def parse_command(self, message: str) -> Optional[str]:
        """Convert message to lowercase and match against defined command keywords."""
        msg = message.lower().strip()
        
        # Exact match or keyword inclusion
        for command, keywords in self.COMMANDS.items():
            if msg in keywords:
                return command
                
        return None
