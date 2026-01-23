import os
import pandas as pd
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from datetime import timedelta
import matplotlib.pyplot as plt
import json
from weekly_report import generate_weekly_report
from radar_chart import plot_radar_chart

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
        print(f"⚠️ Removed {initial_rows - len(df)} duplicate rows")
    
    # Validate timestamps (ensure they are valid dates)
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    invalid_dates = df['timestamp'].isna().sum()
    if invalid_dates > 0:
        print(f"⚠️ Dropped {invalid_dates} rows with invalid timestamps")
        df = df.dropna(subset=['timestamp'])
    
    # Clean usernames: strip whitespace, but keep case-sensitive as per your instruction
    df['username'] = df['username'].str.strip()
    
    # Flag potential username typos (simple check for similar names)
    usernames = df['username'].unique()
    for user in usernames:
        similar = [u for u in usernames if u != user and u.lower() in user.lower() or user.lower() in u.lower()]
        if similar:
            print(f"⚠️ Potential typo for {user}: similar usernames {similar}")
    
    # Check for missing values in key columns
    key_cols = ['username', 'timestamp', 'physics', 'additional_subject_chemistrymaths', 'exercise', 'wake_up', 'screen_control']
    missing = df[key_cols].isnull().sum()
    if missing.any():
        print(f"⚠️ Missing values in key columns: {missing[missing > 0].to_dict()}")
    
    return df

def load_and_normalize_csv(path):
    try:
        df = pd.read_csv(path)
        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
            .str.replace(" ", "_")
            .str.replace(r"[()/.]", "", regex=True)
            .str.replace("\n", "")
            .str.replace(":", "")
        )
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
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        df['username'] = df['username'].str.strip().str.lower()
        df = df.dropna(subset=['timestamp'])
        return df
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return pd.DataFrame()

def collapse_to_daily(df):
    """Collapse multiple submissions on the same date to a single daily row (max of each habit)."""
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    habit_cols = ['physics','additional_subject_chemistrymaths','exercise','wake_up','screen_control']
    daily = (
        df.groupby(['username','date'])[habit_cols]
        .max()        .reset_index()
    )
    return daily

def compute_streak_for_user(daily_df, required_cols, start_date_obj, end_date_obj, mercy_days=2):
    """
    Compute streak for one user using:
      - required_cols: list of columns that must be True on a day to count as a valid day
      - mercy_days: allowed consecutive missing days (no submissions) tolerated
    Rules:
      - A logged day with required_cols not all True breaks the streak immediately.
      - Missing days (no row) are tolerated up to mercy_days in a row.
      - If last_log is older than mercy_days relative to end_date_obj, return 0 (no visible streak).
    """
    if daily_df.empty:
        return 0
    
    # Map date -> row
    daily_df = daily_df.sort_values('date')
    daily_df['valid_day'] = daily_df[required_cols].all(axis=1)

    logged_dates = set(daily_df['date'].tolist())
    valid_dates = set(daily_df[daily_df['valid_day']]['date'].tolist())

    last_log = daily_df['date'].max()

    # If user hasn't logged within mercy_days of end, they show no active streak
    if (end_date_obj - last_log).days > mercy_days:
        return 0

    # Walk backwards from last_log day-by-day and count streak
    streak = 0
    missing_in_a_row = 0
    cur_date = last_log

    while cur_date >= start_date_obj:
        if cur_date in logged_dates:
            if cur_date in valid_dates:
                streak += 1
                missing_in_a_row = 0
            else:
                # Logged but invalid -> break streak
                break
        else:
            missing_in_a_row += 1
            if missing_in_a_row > mercy_days:
                break
        cur_date -= timedelta(days=1)
    
    return streak

def save_streak_state(streak_state, path='streaks_state.json'):
    try:
        if os.path.exists(path):
            with open(path, 'r') as f:
                existing = json.load(f)
            existing.update(streak_state)
            streak_state = existing
        with open(path, 'w') as f:
            json.dump(streak_state, f, indent=4)
        print(f"✅ Streak state saved to {path}")
    except Exception as e:
        print(f"❌ Error saving streak state: {e}")

def map_habit_values(df):
    yes_no_map = {
        "yes": 1,
        "no": 0,
        "done": 1,
        "not done": 0
    }
    
    for col in df.columns:
        if col in ['physics', 'additional_subject_chemistrymaths', 'exercise', 'wake_up', 'screen_control']:
            df[col] = df[col].astype(str).str.lower().map(yes_no_map).fillna(0).astype(int)
    
    return df

def calculate_daily_scores(df):
    # Define weights: Harder tasks = more points
    weights = {
        "physics": 2.0,        "additional_subject_chemistrymaths": 2.0,
        "exercise": 1.5,        "wake_up": 1.0,        "screen_control": 1.0    }
    
    # Calculate weighted sum
    df["daily_score"] = 0
    for col, weight in weights.items():
        df["daily_score"] += df[col] * weight
            
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

# --------------------------- Helper: collapse to daily (duplicate removed) ---------------------------

# --------------------------- Helper: compute streak for one user (duplicate removed) ---------------------------

# --------------------------- Helper: persist streak state (duplicate removed) ---------------------------

def generate_user_summaries(df):
    """
    Updated user summaries generator that:
      - uses a fixed competition start date
      - collapses logs to one row per user/day
      - computes three streak types with mercy for missing days
      - persists streak state to 'streaks_state.json'

    NOTE: This version fixes a KeyError when the grouped DataFrame does not contain
    the 'username' column (pandas may move the group key to group.name).
    """
    # -------------------------
    # CONFIG - adjust as required
    # -------------------------
    COMPETITION_START_DATE = "2023-10-25"   # format YYYY-MM-DD; set None to use earliest CSV date
    MERCY_DAYS = 2                          # allowed consecutive missing days tolerated in a streak
    STREAK_STATE_PATH = 'streaks_state.json'
    # -------------------------

    # Ensure timestamp is datetime (safety)
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')

    # 1) Determine competition start date
    if COMPETITION_START_DATE:
        start_date_obj = pd.to_datetime(COMPETITION_START_DATE).date()
    else:
        start_date_obj = df['timestamp'].min().date()

    # 2) Determine "current" snapshot for computation (latest CSV timestamp)
    end_date_obj = df['timestamp'].max().date()

    # 3) Competition duration (denominator for averages)
    total_competition_days = (end_date_obj - start_date_obj).days + 1
    total_competition_days = max(1, total_competition_days)  # safety

    print(f"ℹ️ Calculation Report:")
    print(f"   Competition Start: {start_date_obj}")
    print(f"   Latest Data Point: {end_date_obj}")
    print(f"   Total Days Counted: {total_competition_days}")

    # 4) Collapse original logs into one row per user/day for streak evaluation
    daily_all = collapse_to_daily(df)

    # 5) Summarize per user (note: `group` might not include 'username' column)
    def summarize_group(group):
        total_score = group['daily_score'].sum()
        average_score = total_score / total_competition_days
        
        # Compute streaks using daily data
        user_daily = daily_all[daily_all['username'] == group.name]
        academic_streak = compute_streak_for_user(user_daily, ['physics', 'additional_subject_chemistrymaths'], start_date_obj, end_date_obj, MERCY_DAYS)
        physical_streak = compute_streak_for_user(user_daily, ['exercise'], start_date_obj, end_date_obj, MERCY_DAYS)
        mental_streak = compute_streak_for_user(user_daily, ['wake_up', 'screen_control'], start_date_obj, end_date_obj, MERCY_DAYS)
        
        days_logged = len(group)
        
        return pd.Series({
            'total_score': total_score,
            'average_score': average_score,
            'days_logged': days_logged,
            'days_counted': total_competition_days,
            'academic_streak': academic_streak,
            'physical_streak': physical_streak,
            'mental_streak': mental_streak
        })

    # Run grouping and sorting
    summaries = (
        df.groupby("username")
          .apply(summarize_group, include_groups=False)
          .round(2)
          .sort_values(by="average_score", ascending=False)
    )

    # Persist streak state for each user (keeps a record separate from the CSV)
    streak_state = {}
    for u, row in summaries.iterrows():
        streak_state[u] = {
            'academic_streak': row['academic_streak'],
            'physical_streak': row['physical_streak'],
            'mental_streak': row['mental_streak'],
            'saved_on': str(datetime.now().date())
        }
    save_streak_state(streak_state, path=STREAK_STATE_PATH)

    return summaries

def plot_individual_trends(df, username):
    user_df = df[df['username'] == username].sort_values('timestamp')
    if user_df.empty:
        return None
    
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
    os.makedirs('data/individual_images', exist_ok=True)
    filename = f'data/individual_images/{username}_trends.png'
    plt.savefig(filename)
    plt.close()
    return filename

def generate_individual_report(df, username, summaries):
    user_summary = summaries.loc[username]
    
    # Generate trend plot
    trend_file = plot_individual_trends(df, username)
    if not trend_file:
        return
    
    # Create PDF
    os.makedirs('data/individual_images', exist_ok=True)
    pdf_file = f'data/individual_images/{username}_report.pdf'
    c = canvas.Canvas(pdf_file, pagesize=letter)
    width, height = letter
    
    # Title page
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, height - 100, f"Personal Growth Report for {username}")
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 120, f"Generated on {datetime.now().strftime('%Y-%m-%d')}")
    
    # Summary stats from summaries
    c.drawString(100, height - 160, f"Total Score: {user_summary['total_score']}")
    c.drawString(100, height - 180, f"Average Score: {user_summary['average_score']}")
    c.drawString(100, height - 200, f"Days Logged: {user_summary['days_logged']}")
    c.drawString(100, height - 220, f"Academic Streak: {user_summary['academic_streak']}")
    c.drawString(100, height - 240, f"Physical Streak: {user_summary['physical_streak']}")
    c.drawString(100, height - 260, f"Mental Streak: {user_summary['mental_streak']}")
    
    c.showPage()
    
    # Embed trend plot
    if os.path.exists(trend_file):
        img = ImageReader(trend_file)
        c.drawImage(img, 50, height - 400, width=500, height=300)
    
    c.save()
    print(f"✅ Individual report saved as {pdf_file}")

# Main execution
df = load_and_normalize_csv(CSV_PATH)
df = validate_and_clean_data(df)
df = map_habit_values(df)
df = calculate_daily_scores(df)

def generate_individual_report(df, username, summaries):
    user_summary = summaries.loc[username]
    user_df = df[df['username'] == username]
    
    # Generate trend plot
    trend_file = plot_individual_trends(df, username)
    if not trend_file:
        return
    
    # Generate radar chart for habits
    habit_cols = ['physics', 'additional_subject_chemistrymaths', 'exercise', 'wake_up', 'screen_control']
    habit_averages = user_df[habit_cols].mean()
    radar_file = plot_radar_chart(habit_averages, username)
    
    # Create PDF
    os.makedirs('data/individual_images', exist_ok=True)
    pdf_file = f'data/individual_images/{username}_report.pdf'
    c = canvas.Canvas(pdf_file, pagesize=letter)
    width, height = letter
    
    # Title page
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, height - 100, f"Personal Growth Report for {username}")
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 120, f"Generated on {datetime.now().strftime('%Y-%m-%d')}")
    
    # Summary stats
    c.drawString(100, height - 160, f"Total Score: {user_summary['total_score']}")
    c.drawString(100, height - 180, f"Average Score: {user_summary['average_score']}")
    c.drawString(100, height - 200, f"Days Logged: {user_summary['days_logged']}")
    c.drawString(100, height - 220, f"Academic Streak: {user_summary['academic_streak']}")
    c.drawString(100, height - 240, f"Physical Streak: {user_summary['physical_streak']}")
    c.drawString(100, height - 260, f"Mental Streak: {user_summary['mental_streak']}")
    
    c.showPage()
    
    # Embed trend plot
    if os.path.exists(trend_file):
        img = ImageReader(trend_file)
        c.drawImage(img, 50, height - 400, width=500, height=300)
    
    c.showPage()
    
    # Embed radar chart
    if radar_file and os.path.exists(radar_file):
        img = ImageReader(radar_file)
        c.drawImage(img, 50, height - 400, width=500, height=300)
    
    c.save()
    print(f"✅ Individual report saved as {pdf_file}")

print("\nNormalized data:")
print(df.head())

print("\nActual columns:")
print(df.columns.tolist())

print("\nDaily scores:")
print(df[["timestamp", "username", "daily_score"]].head())

print("\n🏆 User Summaries:")
summaries = generate_user_summaries(df)
print(summaries)

# Generate one PDF per user (individual growth tracking)
users = df['username'].unique()
for user in users:
    if user in summaries.index:
        generate_individual_report(df, user, summaries)

print("✅ All individual PDFs generated")

# Generate weekly report
generate_weekly_report()

