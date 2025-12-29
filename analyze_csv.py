import os
import pandas as pd

CSV_PATH = "form_data/growth_data.csv"

# ===== SAFE CHECK =====
if not os.path.exists(CSV_PATH):
    print("❌ CSV file not found")
    exit()

if os.path.getsize(CSV_PATH) == 0:
    print("❌ CSV file is empty")
    exit()
# ======================

df = pd.read_csv(CSV_PATH)
print("✅ CSV loaded successfully")
print(df.head())


# ---- NORMALIZATION ----
df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

yes_no_map = {
    "yes": 1,
    "no": 0,
    "done": 1,
    "not done": 0
}

for col in df.columns:
    df[col] = df[col].astype(str).str.lower().map(yes_no_map).fillna(df[col])

print("\nNormalized data:")
print(df)


print("\nActual columns:")
print(df.columns.tolist())


# ---- DAILY SCORE ----
habit_columns = [
    "physics",
    "additional_subject_(chemistry/maths)",
    "exercise",
    "wake_up",
    "screen_control"
]


df["daily_score"] = df[habit_columns].sum(axis=1)

print("\nDaily score:")
print(df[["timestamp", "username", "daily_score"]])
