import os
import pandas as pd
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
import re
import json
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

CSV_PATH = "form_data/growth_data.csv"

# ===== SAFE CHECK =====
if not os.path.exists(CSV_PATH):
    print("❌ CSV file not found")
    exit()

if os.path.getsize(CSV_PATH) == 0:
    print("❌ CSV file is empty")
    exit()
# ======================

def validate_and_clean_data(df):
    # Check for duplicates based on timestamp and username
    initial_rows = len(df)
    df = df.drop_duplicates(subset=['timestamp', 'username'], keep='first')
    if len(df) < initial_rows:
        print(f"⚠️ Removed {initial_rows - len(df)} duplicate entries.")
    
    # Validate timestamps (ensure they are valid dates)
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    invalid_dates = df['timestamp'].isna().sum()
    if invalid_dates > 0:
        print(f"⚠️ Found {invalid_dates} invalid timestamps; they have been set to NaT.")
    
    # Clean usernames: strip whitespace, but keep case-sensitive as per your instruction
    df['username'] = df['username'].str.strip()
    
    # Flag potential username typos (simple check for similar names)
    usernames = df['username'].unique()
    for user in usernames:
        similar = [u for u in usernames if u != user and re.sub(r'[^a-zA-Z]', '', u.lower()) == re.sub(r'[^a-zA-Z]', '', user.lower())]
        if similar:
            print(f"⚠️ Possible username typo: '{user}' similar to {similar}")
    
    # Check for missing values in key columns
    key_cols = ['username', 'timestamp', 'physics', 'additional_subject_chemistrymaths', 'exercise', 'wake_up', 'screen_control']
    missing = df[key_cols].isnull().sum()
    if missing.any():
        print(f"⚠️ Missing values in columns: {missing[missing > 0].to_dict()}")
        # Optionally, fill with defaults (e.g., 0 for habits)
        df[key_cols] = df[key_cols].fillna(0)
    
    return df

def load_and_normalize_csv(path):
    try:
        df = pd.read_csv(path)
        print("✅ CSV loaded successfully")
        print(df.head())
        
        # Normalize column names first
        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
            .str.replace(" ", "_")
            .str.replace(r"[()/.]", "", regex=True)
            .str.replace("\n", "")
            .str.replace(":", "")
        )
        
        # Rename columns to expected names
        rename_dict = {
            "username_use_same_username_always_it_is_case_sensitive_so_keep_that_also_in_mind": "username",
            "timestamp": "timestamp",
            "physics_45_minutes_is_minimum": "physics",
            "additional_subject_do_any_one_out_of_chemistry_or_maths_for_at_least_45_minutes": "additional_subject_chemistrymaths",
            "exercise_do_50_pushups_and_50_situps_or_run_2km_or_do_whatever_you_can_accept_as_doing_something_physical": "exercise",
            "wake_up__wake_up_before_600_am": "wake_up",
            "screen_control_the_wasteful_screen_time_must_be_less_than_1_hour_": "screen_control"
        }
        df = df.rename(columns=rename_dict)
        
        # Add validation and cleaning after renaming
        df = validate_and_clean_data(df)
        
        return df
        
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return pd.DataFrame()

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
    
    # Equal weight for all habits
    df["daily_score"] = df[habit_columns].sum(axis=1)
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
    # ==========================================
    # ⚙️ CONFIG: SET YOUR REFERENCE DATE HERE
    # Format: "YYYY-MM-DD" (e.g., "2023-10-25")
    # If you leave this None, it will default to the earliest date found in the CSV.
    COMPETITION_START_DATE = "2023-10-25" 
    # ==========================================

    # 1. Determine the Start Date
    if COMPETITION_START_DATE:
        start_date_obj = pd.to_datetime(COMPETITION_START_DATE).date()
    else:
        start_date_obj = df['timestamp'].min().date()

    # 2. Determine the End Date (The "Current" state of the competition)
    # We use the latest timestamp in the CSV to represent "Today" relative to the data.
    # If you want it to always be actual today, use: end_date_obj = datetime.now().date()
    end_date_obj = df['timestamp'].max().date()

    # 3. Calculate Total Competition Days (The Denominator)
    # This counts every single day from start to end, regardless of whether a user logged in.
    total_competition_days = (end_date_obj - start_date_obj).days + 1
    
    # Safety check to avoid division by zero
    total_competition_days = max(1, total_competition_days)

    print(f"ℹ️ Calculation Report:")
    print(f"   Competition Start: {start_date_obj}")
    print(f"   Latest Data Point: {end_date_obj}")
    print(f"   Total Days Counted: {total_competition_days}")

    def summarize_group(group):
        # Filter out points logged BEFORE the competition started (optional fairness check)
        # valid_logs = group[group['timestamp'].dt.date >= start_date_obj]
        # total_score = valid_logs['daily_score'].sum()
        
        # Or simply sum all scores if you don't care about early logs:
        total_score = group['daily_score'].sum()
        
        # --- NEW LOGIC ---
        # Average = Total Points Earned / Total Duration of Competition
        average_score = total_score / total_competition_days
        # -----------------

        days_logged = len(group)
        academic_streak = calculate_academic_streak(group)
        physical_streak = calculate_physical_streak(group)
        mental_streak = calculate_mental_streak(group)
        
        return pd.Series({
            'total_score': total_score,
            'average_score': average_score,
            'days_logged': days_logged, # How many days they actually submitted
            'days_counted': total_competition_days, # The fixed denominator used
            'academic_streak': academic_streak,
            'physical_streak': physical_streak,
            'mental_streak': mental_streak
        })
    
    summaries = df.groupby("username").apply(summarize_group, include_groups=False).round(2).sort_values(by="average_score", ascending=False)
    return summaries
    # 1. Identify the "Current Date" of the challenge.
    # We use the latest timestamp found in the entire CSV. 
    # This acts as the anchor; if anyone logs a new day, everyone's timeline extends to this point.
    global_latest_date = df['timestamp'].max()

    def summarize_group(group):
        total_score = group['daily_score'].sum()
        
        # --- NEW AVERAGE LOGIC ---
        # Find when this specific user started
        user_start_date = group['timestamp'].min()
        
        # Calculate the span of days from their start to the global end
        # We convert to .date() to ignore hours/minutes and get a clean day count
        total_possible_days = (global_latest_date.date() - user_start_date.date()).days + 1
        
        # Ensure we don't divide by zero (though unlikely)
        total_possible_days = max(1, total_possible_days)
        
        # Calculate average based on the lifespan of their participation
        average_score = total_score / total_possible_days
        # -------------------------

        days_logged = len(group)
        academic_streak = calculate_academic_streak(group)
        physical_streak = calculate_physical_streak(group)
        mental_streak = calculate_mental_streak(group)
        
        return pd.Series({
            'total_score': total_score,
            'average_score': average_score,
            'days_logged': days_logged,
            'days_counted': total_possible_days, # Optional: helpful to see the denominator
            'academic_streak': academic_streak,
            'physical_streak': physical_streak,
            'mental_streak': mental_streak
        })
    
    # Apply the summary
    summaries = df.groupby("username").apply(summarize_group, include_groups=False).round(2).sort_values(by="average_score", ascending=False)
    return summaries
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
    
    summaries = df.groupby("username").apply(summarize_group, include_groups=False).round(2).sort_values(by="total_score", ascending=False)
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

def plot_sorted_summaries_table(summaries):
    # Include username as first column
    table_data = summaries.round(2).reset_index().values
    col_labels = ['Username'] + list(summaries.columns)
    
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.axis('tight')
    ax.axis('off')
    table = ax.table(cellText=table_data, colLabels=col_labels, loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.2)
    plt.title('User Summaries Table (Sorted by Average Score)')
    plt.savefig('user_summaries_table.png')
    plt.close()

def plot_individual_trends(df, username):
    import json
    user_df = df[df['username'] == username].sort_values('timestamp')
    if user_df.empty:
        print(f"⚠️ No data for user {username}")
        return
    
    # Load user config
    try:
        with open('user_config.json', 'r') as f:
            user_config = json.load(f)
        config = user_config.get(username, {})
        title = config.get('title', f'Daily Score Trends for {username}')
        color = config.get('color', 'blue')
    except FileNotFoundError:
        title = f'Daily Score Trends for {username}'
        color = 'blue'
    
    fig, ax = plt.subplots()
    ax.plot(user_df['timestamp'], user_df['daily_score'], marker='o', color=color)
    ax.set_xlabel('Date')
    ax.set_ylabel('Daily Score')
    ax.set_title(title)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(f'data/individual_images/{username}_trends.png')
    plt.close()
    
    # Add avatar if configured
    avatar_path = config.get('avatar_path')
    if avatar_path and os.path.exists(avatar_path):
        from PIL import Image as PILImage
        img = PILImage.open(f'data/individual_images/{username}_trends.png')
        avatar = PILImage.open(avatar_path).resize((50, 50))
        img.paste(avatar, (10, 10))
        img.save(f'data/individual_images/{username}_trends.png')

def generate_individual_report(df, username):
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.utils import ImageReader
    
    user_df = df[df['username'] == username]
    if user_df.empty:
        return
    
    trend_file = f'data/individual_images/{username}_trends.png'
    if not os.path.exists(trend_file):
        plot_individual_trends(df, username)
    
    pdf_file = f'data/individual_images/{username}_report.pdf'
    c = canvas.Canvas(pdf_file, pagesize=letter)
    width, height = letter
    
    # Title page
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, height - 100, f"Personal Growth Report for {username}")
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 120, f"Generated on {datetime.now().strftime('%Y-%m-%d')}")
    
    # Summary stats
    total_score = user_df['daily_score'].sum()
    average_score = user_df['daily_score'].mean()
    days_logged = len(user_df)
    c.drawString(100, height - 160, f"Total Score: {total_score}")
    c.drawString(100, height - 180, f"Average Score: {average_score:.2f}")
    c.drawString(100, height - 200, f"Days Logged: {days_logged}")
    
    c.showPage()
    
    # Embed trend plot
    if os.path.exists(trend_file):
        img = ImageReader(trend_file)
        c.drawImage(img, 50, height - 400, width=500, height=300)
    
    c.save()
    print(f"✅ Report saved as {pdf_file}")

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

def plot_sorted_summaries_table(summaries):
    # Include username as first column
    table_data = summaries.round(2).reset_index().values
    col_labels = ['Username'] + list(summaries.columns)
    
    fig, ax = plt.subplots(figsize=(12, 8))
    ax.axis('tight')
    ax.axis('off')
    table = ax.table(cellText=table_data, colLabels=col_labels, loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.2)
    plt.title('User Summaries Table (Sorted by Average Score)')
    plt.savefig('user_summaries_table.png')
    plt.close()

plot_sorted_summaries_table(summaries)

print("✅ Plots saved as 'average_scores.png', 'streaks.png', and 'user_summaries_table.png'")

# Generate individual reports
users = df['username'].unique()
for user in users:
    plot_individual_trends(df, user)
    generate_individual_report(df, user)
    print(f"✅ Individual report generated for {user}")

print("✅ All individual reports generated")
