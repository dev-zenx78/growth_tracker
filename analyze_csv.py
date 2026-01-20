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
import json
from datetime import timedelta

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
    


def collapse_to_daily(df):
    """Collapse multiple submissions on the same date to a single daily row (max of each habit)."""
    df['date'] = pd.to_datetime(df['timestamp']).dt.date
    habit_cols = ['physics','additional_subject_chemistrymaths','exercise','wake_up','screen_control']
    daily = (
        df.groupby(['username','date'])[habit_cols]
        .max()   # did the user do it at least once that day
        .reset_index()
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
        return 0, None  # streak, last_log_date

    # Map date -> row
    daily_df = daily_df.sort_values('date')
    daily_df['valid_day'] = daily_df[required_cols].all(axis=1)

    logged_dates = set(daily_df['date'].tolist())
    valid_dates = set(daily_df[daily_df['valid_day']]['date'].tolist())

    last_log = daily_df['date'].max()

    # If user hasn't logged within mercy_days of end, they show no active streak
    if (end_date_obj - last_log).days > mercy_days:
        # still return last_log so you can persist it, but streak=0 for display.
        return 0, last_log

    # Walk backwards from last_log day-by-day and count streak
    streak = 0
    missing_in_a_row = 0
    cur_date = last_log

    while cur_date >= start_date_obj:
        if cur_date in valid_dates:
            # a valid completed day -> streak continues
            streak += 1
            missing_in_a_row = 0
            cur_date = cur_date - timedelta(days=1)
            continue
        elif cur_date in logged_dates and cur_date not in valid_dates:
            # user logged but failed required tasks -> streak broken
            break
        else:
            # cur_date not logged at all (missing)
            missing_in_a_row += 1
            if missing_in_a_row > mercy_days:
                break
            # allow gap and continue backwards
            cur_date = cur_date - timedelta(days=1)
            continue

    return streak, last_log

def save_streak_state(streak_state, path='streaks_state.json'):
    try:
        existing = {}
        if os.path.exists(path):
            with open(path, 'r') as f:
                existing = json.load(f)
        # merge/overwrite
        existing.update(streak_state)
        with open(path, 'w') as f:
            json.dump(existing, f, default=str, indent=2)
    except Exception as e:
        print(f"⚠️ Could not save streak state: {e}")
   

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
    # Define weights: Harder tasks = more points
    weights = {
        "physics": 2.0,          # Core subject, high value
        "additional_subject_chemistrymaths": 2.0,
        "exercise": 1.5,         # Physical health
        "wake_up": 1.0,          # Discipline
        "screen_control": 1.0    # Discipline
    }
    
    # Calculate weighted sum
    df["daily_score"] = 0
    for col, weight in weights.items():
        if col in df.columns:
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

# ---------------------------
# Helper: collapse to daily
# ---------------------------
def collapse_to_daily(df):
    """
    Collapse multiple submissions per username/date to a single row per day.
    We use .max() across habit columns so if a user did a habit at least once that day,
    the day is considered completed for that habit.
    Returns a DataFrame with columns: ['username', 'date', habits...]
    """
    # Ensure timestamp is datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    df['date'] = df['timestamp'].dt.date

    habit_cols = ['physics', 'additional_subject_chemistrymaths', 'exercise', 'wake_up', 'screen_control']
    daily = (
        df.groupby(['username', 'date'])[habit_cols]
          .max()            # did the user do this habit at least once that day?
          .reset_index()
    )
    return daily


# ---------------------------
# Helper: compute streak for one user
# ---------------------------
def compute_streak_for_user(daily_df, required_cols, start_date_obj, end_date_obj, mercy_days=2):
    """
    Compute active streak length for the given user's daily dataframe.
    Rules implemented:
      - A day counts only if ALL required_cols are True on that day (logged & completed).
      - Missing days (no log at all) are tolerated up to `mercy_days` consecutive days.
      - If the user logged but failed required tasks on any day in the backward walk, the streak stops immediately.
      - If the user's last log is older than `mercy_days` relative to end_date_obj, visible streak = 0.
    Returns: (streak_int, last_log_date_or_None)
    """
    # If user has no logs
    if daily_df.empty:
        return 0, None

    # Prepare and mark valid days
    daily_df = daily_df.sort_values('date').copy()
    daily_df['valid_day'] = daily_df[required_cols].all(axis=1)

    logged_dates = set(daily_df['date'].tolist())
    valid_dates = set(daily_df[daily_df['valid_day']]['date'].tolist())
    last_log = daily_df['date'].max()

    # If the last time user logged is beyond mercy_days from end_date_obj -> show no active streak
    if (end_date_obj - last_log).days > mercy_days:
        return 0, last_log

    # Walk backwards day-by-day starting from last_log
    streak = 0
    missing_in_a_row = 0
    cur_date = last_log

    while cur_date >= start_date_obj:
        if cur_date in valid_dates:
            # Completed day -> continue streak
            streak += 1
            missing_in_a_row = 0
            cur_date = cur_date - timedelta(days=1)
            continue

        if cur_date in logged_dates and cur_date not in valid_dates:
            # The user logged this day but did NOT complete required tasks -> immediate break
            break

        # cur_date was not logged at all (missing day)
        missing_in_a_row += 1
        if missing_in_a_row > mercy_days:
            # Gap exceeded mercy allowance -> break
            break

        # Allowed missing day -> continue walking backwards
        cur_date = cur_date - timedelta(days=1)

    return streak, last_log


# ---------------------------
# Helper: persist streak state
# ---------------------------
def save_streak_state(streak_state, path='streaks_state.json'):
    """
    Save/merge streak_state into a JSON file.
    Format: { username: { academic_streak: int, physical_streak: int, ... , saved_on: 'YYYY-MM-DD' } }
    """
    try:
        existing = {}
        if os.path.exists(path):
            with open(path, 'r') as f:
                existing = json.load(f)
        # Update and write back
        existing.update(streak_state)
        with open(path, 'w') as f:
            json.dump(existing, f, default=str, indent=2)
    except Exception as e:
        print(f"⚠️ Could not save streak state to {path}: {e}")


# ---------------------------
# Updated generate_user_summaries
# ---------------------------
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
        # Robustly determine username: prefer column if present, otherwise use group.name
        if 'username' in group.columns:
            username = group['username'].iloc[0]
        else:
            # group.name holds the group key (the username) when pandas removes the column
            username = group.name

        # Get the collapsed daily rows for this user (used for streak calculation)
        user_daily = daily_all[daily_all['username'] == username].copy()
        days_logged = len(user_daily)

        # Keep total_score and average_score logic as before (score is from original df)
        total_score = group['daily_score'].sum()
        average_score = total_score / total_competition_days

        # Compute the three streaks using the unified engine (mercy applies only to missing logs)
        academic_streak, last_log_acad = compute_streak_for_user(
            user_daily,
            required_cols=['physics', 'additional_subject_chemistrymaths'],
            start_date_obj=start_date_obj,
            end_date_obj=end_date_obj,
            mercy_days=MERCY_DAYS
        )

        physical_streak, last_log_phys = compute_streak_for_user(
            user_daily,
            required_cols=['exercise'],
            start_date_obj=start_date_obj,
            end_date_obj=end_date_obj,
            mercy_days=MERCY_DAYS
        )

        mental_streak, last_log_ment = compute_streak_for_user(
            user_daily,
            required_cols=['wake_up', 'screen_control'],
            start_date_obj=start_date_obj,
            end_date_obj=end_date_obj,
            mercy_days=MERCY_DAYS
        )

        # Return summary row; include last-log metadata for persistence
        return pd.Series({
            'total_score': total_score,
            'average_score': average_score,
            'days_logged': days_logged,
            'days_counted': total_competition_days,
            'academic_streak': academic_streak,
            'physical_streak': physical_streak,
            'mental_streak': mental_streak,
            'last_log_academic': str(last_log_acad) if last_log_acad is not None else None,
            'last_log_physical': str(last_log_phys) if last_log_phys is not None else None,
            'last_log_mental': str(last_log_ment) if last_log_ment is not None else None
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
            'academic_streak': int(row['academic_streak']),
            'physical_streak': int(row['physical_streak']),
            'mental_streak': int(row['mental_streak']),
            'last_log_academic': row['last_log_academic'],
            'last_log_physical': row['last_log_physical'],
            'last_log_mental': row['last_log_mental'],
            'saved_on': str(end_date_obj)
        }
    save_streak_state(streak_state, path=STREAK_STATE_PATH)

    return summaries

    '''
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
    '''

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


def plot_radar_chart(df, username):
    # Filter for user and calculate average compliance (0.0 to 1.0) for each habit
    user_df = df[df['username'] == username]
    categories = ["physics", "additional_subject_chemistrymaths", "exercise", "wake_up", "screen_control"]
    
    # Calculate success rate % for each category
    values = []
    for cat in categories:
        values.append(user_df[cat].mean()) # 0.8 means 80% success rate
    
    # Close the loop for the radar chart
    values += values[:1]
    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.fill(angles, values, color='blue', alpha=0.25)
    ax.plot(angles, values, color='blue', linewidth=2)
    
    # Fix labels
    ax.set_yticklabels([])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(["Phy", "Add. Sub", "Gym", "WakeUp", "NoScreen"])
    
    plt.title(f"Habit Balance: {username}")
    plt.savefig(f'data/individual_images/{username}_radar.png')
    plt.close()

for user in users:
    plot_radar_chart(df, user)
    print(f"✅ plot-chart generated for {user}")

print("✅ All individual reports generated")