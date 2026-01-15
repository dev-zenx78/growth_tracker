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
from PIL import Image

CSV_PATH = "form_data/growth_data.csv"

# Copy necessary functions from analyze_csv.py to avoid import issues
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
        df['username'] = df['username'].str.strip()
        df = df.dropna(subset=['timestamp'])
        return df
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
        return pd.DataFrame()

def map_habit_values(df):
    yes_no_map = {"yes": 1, "no": 0, "done": 1, "not done": 0}
    for col in df.columns:
        if col in ["physics", "additional_subject_chemistrymaths", "exercise", "wake_up", "screen_control"]:
            df[col] = df[col].astype(str).str.lower().map(yes_no_map).fillna(0).astype(int)
    return df

def calculate_daily_scores(df):
    habit_columns = ["physics", "additional_subject_chemistrymaths", "exercise", "wake_up", "screen_control"]
    df["daily_score"] = df[habit_columns].sum(axis=1)
    return df

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
    filename = f'data/individual_images/{username}_trends.png'
    plt.savefig(filename)
    plt.close()
    return filename

def generate_individual_report(username):
    df = load_and_normalize_csv(CSV_PATH)
    df = map_habit_values(df)
    df = calculate_daily_scores(df)
    
    user_df = df[df['username'] == username]
    if user_df.empty:
        print(f"⚠️ No data for {username}")
        return
    
    # Generate trend plot
    trend_file = plot_individual_trends(df, username)
    if not trend_file:
        return
    
    # Create PDF
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

if __name__ == "__main__":
    # Generate for all users
    df = load_and_normalize_csv(CSV_PATH)
    df = map_habit_values(df)
    df = calculate_daily_scores(df)
    users = df['username'].unique()
    for user in users:
        generate_individual_report(user)