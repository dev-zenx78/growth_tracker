import os
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np

CSV_PATH = "form_data/growth_data.csv"

# ===== SAFE CHECK =====
if not os.path.exists(CSV_PATH):
    print("❌ CSV file not found")
    exit()

if os.path.getsize(CSV_PATH) == 0:
    print("❌ CSV file is empty")
    exit()
# ======================

def load_and_normalize_csv(path):
    try:
        df = pd.read_csv(path)
        print("✅ CSV loaded successfully")
        print(df.head())
        
        # Normalize column names
        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
            .str.replace(" ", "_")
            .str.replace(r"[()/]", "", regex=True)
        )
        
        # Convert timestamp to datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors='coerce')
        
        return df
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        exit()

def map_habit_values(df):
    yes_no_map = {
        "yes": 1,
        "no": 0,
        "done": 1,
        "not done": 0
    }
    
    for col in df.columns:
        if col in ["physics", "additional_subject_chemistrymaths", "exercise", "wake_up", "screen_control"]:
            df[col] = df[col].astype(str).str.lower().map(yes_no_map).fillna(0).astype(int)
    
    return df

def calculate_daily_scores(df):
    habit_columns = [
        "physics",
        "additional_subject_chemistrymaths",
        "exercise",
        "wake_up",
        "screen_control"
    ]
    
    # Ensure all habit columns exist
    missing_cols = [col for col in habit_columns if col not in df.columns]
    if missing_cols:
        print(f"❌ Missing habit columns: {missing_cols}")
        exit()
    
    # Prioritize academic and mental: weight 2, physical 1
    df["daily_score"] = (
        df["physics"] * 2 +
        df["additional_subject_chemistrymaths"] * 2 +
        df["exercise"] * 1 +
        df["wake_up"] * 2 +
        df["screen_control"] * 2
    )
    return df

def calculate_academic_streak(group):
    group = group.sort_values('timestamp')
    group = group[(group['physics'] == 1) & (group['additional_subject_chemistrymaths'] == 1)]
    if group.empty:
        return 0
    group['date'] = pd.to_datetime(group['timestamp']).dt.date
    group['date_diff'] = group['date'].diff().apply(lambda x: x.days if pd.notna(x) else 0)
    group['streak_group'] = (group['date_diff'] != 1).cumsum()
    streaks = group.groupby('streak_group').size()
    return streaks.iloc[-1] if not streaks.empty else 0

def calculate_physical_streak(group):
    group = group.sort_values('timestamp')
    group = group[group['exercise'] == 1]
    if group.empty:
        return 0
    group['date'] = pd.to_datetime(group['timestamp']).dt.date
    group['date_diff'] = group['date'].diff().apply(lambda x: x.days if pd.notna(x) else 0)
    group['streak_group'] = (group['date_diff'] != 1).cumsum()
    streaks = group.groupby('streak_group').size()
    return streaks.iloc[-1] if not streaks.empty else 0

def calculate_mental_streak(group):
    group = group.sort_values('timestamp')
    group = group[(group['wake_up'] == 1) & (group['screen_control'] == 1)]
    if group.empty:
        return 0
    group['date'] = pd.to_datetime(group['timestamp']).dt.date
    group['date_diff'] = group['date'].diff().apply(lambda x: x.days if pd.notna(x) else 0)
    group['streak_group'] = (group['date_diff'] != 1).cumsum()
    streaks = group.groupby('streak_group').size()
    return streaks.iloc[-1] if not streaks.empty else 0

def generate_user_summaries(df):
    def summarize_group(group):
        total_score = group['daily_score'].sum()
        average_score = group['daily_score'].mean()
        days_logged = len(group)
        academic_streak = calculate_academic_streak(group)
        physical_streak = calculate_physical_streak(group)
        mental_streak = calculate_mental_streak(group)
        return pd.Series({
            'total_score': total_score,
            'average_score': average_score,
            'days_logged': days_logged,
            'academic_streak': academic_streak,
            'physical_streak': physical_streak,
            'mental_streak': mental_streak
        })
    
    summaries = df.groupby("username").apply(summarize_group, include_groups=False).round(2).sort_values(by="average_score", ascending=False)
    return summaries

def plot_average_scores(summaries):
    fig, ax = plt.subplots()
    ax.bar(summaries.index, summaries['average_score'])
    ax.set_xlabel('User')
    ax.set_ylabel('Average Score')
    ax.set_title('Average Scores per User')
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('average_scores.png')
    plt.close()

def plot_streaks(summaries):
    users = summaries.index
    x = np.arange(len(users))
    width = 0.25
    fig, ax = plt.subplots()
    ax.bar(x - width, summaries['academic_streak'], width, label='Academic')
    ax.bar(x, summaries['physical_streak'], width, label='Physical')
    ax.bar(x + width, summaries['mental_streak'], width, label='Mental')
    ax.set_xlabel('User')
    ax.set_ylabel('Streak Length')
    ax.set_title('Streaks per User')
    ax.set_xticks(x, users)
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('streaks.png')
    plt.close()

# Main execution
df = load_and_normalize_csv(CSV_PATH)
df = map_habit_values(df)
df = calculate_daily_scores(df)

print("\nNormalized data:")
print(df)

print("\nActual columns:")
print(df.columns.tolist())

print("\nDaily scores:")
print(df[["timestamp", "username", "daily_score"]])

print("\n🏆 User Summaries:")
summaries = generate_user_summaries(df)
print(summaries)

# Generate and save plots
plot_average_scores(summaries)
plot_streaks(summaries)
print("✅ Plots saved as 'average_scores.png' and 'streaks.png'")
