import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from thefuzz import fuzz, process

import pandas as pd
from config import INVENTORY_FILE, DEFAULT_MIN_STOCK, LOW_STOCK_THRESHOLD, CRITICAL_STOCK_THRESHOLD

class InventoryDatabase:
    # --- INITIALIZATION ---
    def __init__(self):
        self.inventory_file = INVENTORY_FILE
        self.medicines: List[Dict] = []
        self.load_database()

    # --- FILE OPERATIONS ---
    def load_database(self):
        """Load medicines from JSON file if exists."""
        if os.path.exists(self.inventory_file):
            try:
                with open(self.inventory_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.medicines = data.get('medicines', [])
            except (json.JSONDecodeError, FileNotFoundError):
                self.medicines = []
        else:
            self.medicines = []

    def save_database(self):
        """Save medicines to JSON file with updated_at timestamp."""
        data = {
            'updated_at': datetime.now().isoformat(),
            'medicines': self.medicines
        }
        with open(self.inventory_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def clear_database(self):
        """Empty the medicines list and save to file."""
        self.medicines = []
        self.save_database()

    # --- IMPORT OPERATIONS ---
    def import_from_dataframe(self, df: pd.DataFrame) -> Tuple[int, List[str]]:
        """Accept pandas DataFrame and import medicines with flexible column finding."""
        errors = []
        success_count = 0
        
        # Column mapping logic
        col_map = {
            'name': ['medicine_name', 'name', 'product'],
            'stock': ['stock', 'quantity', 'qty'],
            'min_stock': ['min_stock', 'minimum_stock'],
            'price': ['price', 'mrp', 'rate']
        }
        
        actual_cols = {}
        df_cols = [c.lower() for c in df.columns]
        
        for key, aliases in col_map.items():
            for alias in aliases:
                if alias in df_cols:
                    # Find original case column name
                    idx = df_cols.index(alias)
                    actual_cols[key] = df.columns[idx]
                    break
        
        if 'name' not in actual_cols:
            return 0, ["Required column 'medicine_name' or 'name' not found."]

        self.clear_database()
        
        for index, row in df.iterrows():
            try:
                name = str(row[actual_cols['name']]).strip()
                if not name:
                    continue
                
                stock = int(row.get(actual_cols.get('stock'), 0))
                min_stock = int(row.get(actual_cols.get('min_stock'), DEFAULT_MIN_STOCK))
                price = float(row.get(actual_cols.get('price'), 0.0))
                
                medicine_entry = {
                    'id': index + 1,
                    'name': name,
                    'search_name': name.lower(),
                    'stock': stock,
                    'min_stock': min_stock,
                    'price': price,
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
                self.medicines.append(medicine_entry)
                success_count += 1
            except Exception as e:
                errors.append(f"Row {index + 1}: {str(e)}")
        
        self.save_database()
        return success_count, errors

    def restock_from_dataframe(self, df: pd.DataFrame) -> Tuple[int, int, List[str], List[Dict]]:
        """Add stock from DataFrame to existing inventory or create new entries."""
        updated_count = 0
        new_count = 0
        not_found = []
        updates_detail = []

        # Column mapping logic
        col_map = {
            'name': ['medicine_name', 'name', 'medicine', 'product'],
            'stock': ['stock', 'quantity', 'qty'],
            'min_stock': ['min_stock', 'minimum_stock'],
            'price': ['price', 'mrp', 'rate']
        }
        
        actual_cols = {}
        df_cols = [c.lower() for c in df.columns]
        
        for key, aliases in col_map.items():
            for alias in aliases:
                if alias in df_cols:
                    idx = df_cols.index(alias)
                    actual_cols[key] = df.columns[idx]
                    break
        
        if 'name' not in actual_cols:
            return 0, 0, ["Required column 'medicine_name' or 'name' not found."], []

        for index, row in df.iterrows():
            try:
                name_query = str(row[actual_cols['name']]).strip()
                if not name_query:
                    continue
                
                stock_to_add = int(row.get(actual_cols.get('stock'), 0))
                
                # Try to find medicine in database
                med, score = self.find_medicine(name_query)
                
                if med and score >= 60:
                    # UPDATING EXISTING MEDICINE
                    old_stock = med['stock']
                    med['stock'] += stock_to_add
                    
                    # Optional updates
                    if 'min_stock' in actual_cols:
                        med['min_stock'] = int(row[actual_cols['min_stock']])
                    if 'price' in actual_cols:
                        med['price'] = float(row[actual_cols['price']])
                        
                    med['updated_at'] = datetime.now().isoformat()
                    
                    updates_detail.append({
                        'name': med['name'],
                        'old_stock': old_stock,
                        'new_stock': med['stock'],
                        'added': stock_to_add,
                        'status': 'updated'
                    })
                    updated_count += 1
                else:
                    # NEW MEDICINE ENTRY
                    min_stock = int(row.get(actual_cols.get('min_stock'), DEFAULT_MIN_STOCK))
                    price = float(row.get(actual_cols.get('price'), 0.0))
                    
                    new_id = max([m['id'] for m in self.medicines], default=0) + 1
                    new_med = {
                        'id': new_id,
                        'name': name_query,
                        'search_name': name_query.lower(),
                        'stock': stock_to_add,
                        'min_stock': min_stock,
                        'price': price,
                        'created_at': datetime.now().isoformat(),
                        'updated_at': datetime.now().isoformat()
                    }
                    self.medicines.append(new_med)
                    
                    updates_detail.append({
                        'name': name_query,
                        'old_stock': 0,
                        'new_stock': stock_to_add,
                        'added': stock_to_add,
                        'status': 'new'
                    })
                    new_count += 1
                    
            except Exception as e:
                not_found.append(f"Row {index + 1}: {str(e)}")
        
        self.save_database()
        return updated_count, new_count, not_found, updates_detail

    # --- SEARCH OPERATIONS ---
    def find_medicine(self, query: str) -> Tuple[Optional[Dict], int]:
        """Search medicine using exact, partial, or fuzzy matching."""
        query = query.lower().strip()
        if not query:
            return None, 0

        # 1. Exact Match
        for med in self.medicines:
            if med['search_name'] == query:
                return med, 100

        # 2. Partial Match (StartsWith or Contains)
        for med in self.medicines:
            if med['search_name'].startswith(query):
                return med, 90
        
        for med in self.medicines:
            if query in med['search_name']:
                return med, 80

        # 3. Fuzzy Matching (50% threshold)
        med_names = [med['search_name'] for med in self.medicines]
        if not med_names:
            return None, 0
            
        best_match, score = process.extractOne(query, med_names, scorer=fuzz.token_sort_ratio)
        
        if score >= 50:
            for med in self.medicines:
                if med['search_name'] == best_match:
                    return med, score
                    
        return None, 0

    # --- STOCK OPERATIONS ---
    def update_stock(self, medicine_id: int, quantity: int, operation: str) -> Optional[Dict]:
        """Update stock levels and prevent negative values."""
        for med in self.medicines:
            if med['id'] == medicine_id:
                if operation == 'sold':
                    if med['stock'] < quantity:
                        return None # Insufficient stock
                    med['stock'] -= quantity
                elif operation == 'bought':
                    med['stock'] += quantity
                
                med['updated_at'] = datetime.now().isoformat()
                self.save_database()
                return med
        return None

    # --- STATUS & REPORTING ---
    def get_all_medicines(self) -> List[Dict]:
        """Return all medicines."""
        return self.medicines

    def get_low_stock_medicines(self) -> List[Dict]:
        """Return medicines where stock <= min_stock * LOW_STOCK_THRESHOLD."""
        low_stock = [
            med for med in self.medicines 
            if med['stock'] <= (med['min_stock'] * LOW_STOCK_THRESHOLD)
        ]
        return sorted(low_stock, key=lambda x: x['stock'])

    def get_critical_stock_medicines(self) -> List[Dict]:
        """Return medicines where stock <= CRITICAL_STOCK_THRESHOLD."""
        return [med for med in self.medicines if med['stock'] <= CRITICAL_STOCK_THRESHOLD]

    def check_stock_status(self, medicine: Dict) -> str:
        """Return status based on stock thresholds."""
        stock = medicine['stock']
        min_stock = medicine['min_stock']
        
        if stock <= CRITICAL_STOCK_THRESHOLD:
            return 'critical'
        elif stock <= min_stock:
            return 'low'
        elif stock <= (min_stock * LOW_STOCK_THRESHOLD):
            return 'warning'
        else:
            return 'ok'

    def get_medicine_count(self) -> int:
        """Return total number of medicines."""
        return len(self.medicines)

