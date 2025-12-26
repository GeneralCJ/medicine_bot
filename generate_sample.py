import pandas as pd
import os

data = [
    ["Crocin 650mg", 150, 50, 15],
    ["Dolo 650", 200, 40, 30],
    ["Paracetamol 500mg", 300, 100, 10],
    ["Azithromycin 500mg", 50, 20, 70],
    ["Amoxicillin 250mg", 100, 30, 45],
    ["Ciprofloxacin 500mg", 80, 25, 60],
    ["Pantoprazole 40mg", 120, 35, 95],
    ["Omeprazole 20mg", 150, 40, 40],
    ["Ranitidine 150mg", 250, 50, 20],
    ["Cetirizine 10mg", 200, 50, 25],
    ["Levocetirizine 5mg", 180, 40, 55],
    ["Vitamin C 500mg", 300, 100, 20],
    ["B-Complex Syrup", 60, 15, 120],
    ["Calcium Carbonate 500mg", 200, 50, 85],
    ["Vicks Vaporub 25g", 40, 10, 110],
    ["Digene Gel 200ml", 25, 12, 185],
    ["Saridon", 200, 50, 12],
    ["Volini Spray 40g", 35, 10, 195],
    ["Limcee Tablet", 400, 100, 5],
    ["Electral Powder", 150, 30, 22]
]

df = pd.DataFrame(data, columns=["medicine_name", "stock", "min_stock", "price"])

os.makedirs("templates", exist_ok=True)
df.to_excel("templates/sample_inventory.xlsx", index=False)
print("Sample inventory Excel file created at templates/sample_inventory.xlsx")
