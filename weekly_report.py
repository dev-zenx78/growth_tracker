import pandas as pd
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import numpy as np
import os

CSV_PATH = "form_data/growth_data.csv"

def load_and_process_csv():
    # Load CSV
    df = pd.read_csv(CSV_PATH)
    
    # Normalize column names
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
        .str.replace(r"[()/.]", "", regex=True)
        .str.replace("\n", "")
        .str.replace(":", "")
    )
    
    # Rename columns (aligned with analyze_csv.py)
    df = df.rename(columns={
        "username_use_same_username_always_it_is_case_sensitive_so_keep_that_also_in_mind": "username",
        "physics_45_minutes_is_minimum": "physics",
        "additional_subject_do_any_one_out_of_chemistry_or_maths_for_at_least_45_minutes": "additional_subject_chemistrymaths",
        "exercise_do_50_pushups_and_50_situps_or_run_2km_or_do_whatever_you_can_accept_as_doing_something_physical": "exercise",
        "wake_up__wake_up_before_600_am": "wake_up",
        "screen_control_the_wasteful_screen_time_must_be_less_than_1_hour_": "screen_control"
    })
    
    # Convert timestamp
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors='coerce')
    df = df.dropna(subset=['timestamp'])
    
    # Normalize username: strip and lower case for consistency
    df['username'] = df['username'].str.strip().str.lower()
    
    # Normalize habits to 0/1
    def normalize_done(val):
        if pd.isna(val):
            return 0
        val = str(val).strip().lower()
        return 1 if val in ["done", "yes"] else 0
    
    habit_cols = ["physics", "additional_subject_chemistrymaths", "exercise", "wake_up", "screen_control"]
    for col in habit_cols:
        df[col] = df[col].apply(normalize_done)
    
    # Weighted daily score
    weights = {"physics": 2.0, "additional_subject_chemistrymaths": 2.0, "exercise": 1.5, "wake_up": 1.0, "screen_control": 1.0}
    df["daily_score"] = sum(df[col] * weight for col, weight in weights.items())
    
    return df, habit_cols

def get_current_week_df(df):
    today = datetime.now()
    start_of_week = today - timedelta(days=today.weekday())  # Monday 00:00
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
    week_df = df[(df["timestamp"] >= start_of_week) & (df["timestamp"] <= end_of_week)]
    # Remove duplicates per user per timestamp
    week_df = week_df.drop_duplicates(subset=['username', 'timestamp'], keep='first')
    return week_df, start_of_week, end_of_week

def generate_weekly_league(week_df):
    league = (
        week_df
        .groupby("username")
        .agg(total_score=("daily_score", "sum"), days_logged=("daily_score", "count"))
    )
    league["average_score"] = league["total_score"] / league["days_logged"]
    return league.sort_values(by="total_score", ascending=False)

def plot_weekly_average_scores(league):
    fig, ax = plt.subplots()
    ax.bar(league.index, league['average_score'])
    ax.set_xlabel('User')
    ax.set_ylabel('Average Score')
    ax.set_title('Weekly Average Scores per User')
    plt.xticks(rotation=45)
    plt.tight_layout()
    os.makedirs('data', exist_ok=True)
    plt.savefig('data/weekly_average_scores.png')
    plt.close()

def plot_weekly_table(league):
    table_data = league.round(2).reset_index().values
    col_labels = ['Username'] + list(league.columns)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis('tight')
    ax.axis('off')
    table = ax.table(cellText=table_data, colLabels=col_labels, loc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.2)
    plt.title('Weekly League Table')
    plt.savefig('data/weekly_league_table.png')
    plt.close()

def plot_user_growth_lines(week_df):
    fig, ax = plt.subplots(figsize=(10, 6))
    for username, group in week_df.groupby('username'):
        group = group.sort_values('timestamp')
        ax.plot(group['timestamp'], group['daily_score'], marker='o', label=username)
    ax.set_xlabel('Date')
    ax.set_ylabel('Daily Score')
    ax.set_title('Weekly Growth: Daily Scores per User')
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('data/weekly_user_growth_lines.png')
    plt.close()

def plot_cumulative_growth(week_df):
    fig, ax = plt.subplots(figsize=(10, 6))
    for username, group in week_df.groupby('username'):
        group = group.sort_values('timestamp')
        cumulative = group['daily_score'].cumsum()
        ax.plot(group['timestamp'], cumulative, marker='o', label=username)
    ax.set_xlabel('Date')
    ax.set_ylabel('Cumulative Score')
    ax.set_title('Weekly Growth: Cumulative Scores per User')
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('data/weekly_cumulative_growth.png')
    plt.close()

def plot_polar_growth_comparison(week_df):
    fig = plt.figure(figsize=(8, 8))
    ax = fig.add_subplot(111, polar=True)
    
    # Sort the week by date
    week_df = week_df.sort_values('timestamp')
    start_date = week_df['timestamp'].min().date()
    
    for username, group in week_df.groupby('username'):
        group = group.sort_values('timestamp')
        group['days_since_start'] = (group['timestamp'] - pd.Timestamp(start_date)).dt.days
        cumulative = group['daily_score'].cumsum()
        angles = (group['days_since_start'] / 7) * 2 * np.pi  # Scale to 0-2pi over 7 days
        ax.plot(angles, cumulative, 'o-', linewidth=2, label=username)
    
    # Set ticks for days
    day_angles = np.linspace(0, 2 * np.pi, 8, endpoint=True)  # 0 to 7 days
    ax.set_xticks(day_angles)
    ax.set_xticklabels([f'Day {i}' for i in range(8)])
    ax.set_title('Polar Growth Comparison: Cumulative Scores Over Week', size=14, fontweight='bold', pad=20)
    ax.legend(loc='upper right', bbox_to_anchor=(1.1, 1.1))
    plt.tight_layout()
    plt.savefig('data/weekly_polar_growth_comparison.png')
    plt.close()

def plot_habit_heatmap(week_df, habit_cols):
    # Aggregate habits by user and day
    week_df['date'] = week_df['timestamp'].dt.date
    habit_summary = week_df.groupby(['username', 'date'])[habit_cols].mean().unstack(level=0)
    fig, ax = plt.subplots(figsize=(12, 8))
    cax = ax.imshow(habit_summary.T, aspect='auto', cmap='viridis')
    ax.set_xticks(range(len(habit_summary.index)))
    ax.set_xticklabels([d.strftime('%a') for d in habit_summary.index], rotation=45)
    ax.set_yticks(range(len(habit_summary.columns)))
    ax.set_yticklabels(habit_summary.columns)
    ax.set_title('Weekly Habit Completion Heatmap')
    fig.colorbar(cax)
    plt.tight_layout()
    plt.savefig('data/weekly_habit_heatmap.png')
    plt.close()

def generate_weekly_report():
    df, habit_cols = load_and_process_csv()
    week_df, start, end = get_current_week_df(df)
    if week_df.empty:
        print("❌ No data for this week")
        return
    
    league = generate_weekly_league(week_df)
    
    # Generate all visualizations
    plot_weekly_average_scores(league)
    plot_weekly_table(league)
    plot_user_growth_lines(week_df)
    plot_cumulative_growth(week_df)
    plot_habit_heatmap(week_df, habit_cols)
    plot_polar_growth_comparison(week_df)
    
    print(f"\n🏆 WEEKLY LEAGUE TABLE ({start.date()} to {end.date()})\n")
    print(league.round(2))
    print("\n✅ Weekly visualizations saved to data/")

if __name__ == "__main__":
    generate_weekly_report()

