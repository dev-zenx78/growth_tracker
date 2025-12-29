import os
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "form_data", "growth_data.csv")
OUTPUT_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(OUTPUT_DIR, exist_ok=True)

print("Looking for CSV at:", CSV_PATH)

df = pd.read_csv(CSV_PATH)

# ✅ normalize column names
df.columns = (
    df.columns
    .str.strip()
    .str.lower()
    .str.replace(" ", "_")
)

for _, row in df.iterrows():
    username = row["username"]
    username = username.lower()
    file_path = os.path.join(OUTPUT_DIR, f"{username}.txt")

    with open(file_path, "a") as f:
        f.write(f"Date: {row['timestamp']}\n")
        f.write(f"Physics: {row['physics']}\n")
        f.write(f"Additional Subject: {row['additional_subject_(chemistry/maths)']}\n")
        f.write(f"Exercise: {row['exercise']}\n")
        f.write(f"Wake Up On Time: {row['wake_up']}\n")
        f.write(f"Screen Control: {row['screen_control']}\n")
        f.write("-" * 20 + "\n")

print("✅ TXT files generated per user")
