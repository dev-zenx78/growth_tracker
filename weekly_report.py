import pandas as pd
from datetime import datetime, timedelta

CSV_PATH = "form_data/growth_data.csv"

# -----------------------------
# 1. Load CSV
# -----------------------------
df = pd.read_csv(CSV_PATH)

# -----------------------------
# 2. Normalize column names
# -----------------------------
df.columns = (
    df.columns
    .str.strip()
    .str.lower()
    .str.replace(" ", "_")
    .str.replace(r"[()/]", "", regex=True)
)

# Rename long column once (VERY IMPORTANT)
df = df.rename(columns={
    "additional_subject_chemistrymaths": "additional_subject"
})

# -----------------------------
# 3. Convert timestamp
# -----------------------------
df["timestamp"] = pd.to_datetime(df["timestamp"])

# -----------------------------
# 4. Normalize Done / Not done
# -----------------------------
def normalize_done(val):
    if pd.isna(val):
        return 0
    val = str(val).strip().lower()
    if val == "done" or val == "yes":
        return 1
    return 0

habit_cols = [
    "physics",
    "additional_subject",
    "exercise",
    "wake_up",
    "screen_control"
]

for col in habit_cols:
    df[col] = df[col].apply(normalize_done)

# -----------------------------
# 5. Daily score
# -----------------------------
df["daily_score"] = df[habit_cols].sum(axis=1)

# -----------------------------
# 6. Current week filter
# -----------------------------
today = datetime.now()
start_of_week = today - timedelta(days=today.weekday())
end_of_week = start_of_week + timedelta(days=6)

week_df = df[
    (df["timestamp"] >= start_of_week) &
    (df["timestamp"] <= end_of_week)
]

if week_df.empty:
    print("❌ No data for this week")
    exit()

# -----------------------------
# 7. Weekly league table
# -----------------------------
league = (
    week_df
    .groupby("username")
    .agg(
        total_score=("daily_score", "sum"),
        days_logged=("daily_score", "count")
    )
)

league["average_score"] = league["total_score"] / league["days_logged"]

league = league.sort_values(
    by=["average_score", "total_score"],
    ascending=False
)

# -----------------------------
# 8. Output
# -----------------------------
print("\n🏆 WEEKLY LEAGUE TABLE\n")
print(league.round(2))
