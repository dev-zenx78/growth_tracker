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

# Rename columns to expected names
df = df.rename(columns={
    "username_(use_same_username_always._it_is_case_sensitive_so_keep_that_also_in_mind)": "username",
    "physics_(45_minutes_is_minimum)": "physics",
    "additional_subject_(do_any_one_out_of_chemistry_or_maths_for_at_least_45_minutes)": "additional_subject_(chemistry/maths)",
    "exercise_(do_50_pushups_and_50_situps_or_run_2km_or_do_whatever_you_can_accept_as_doing_something_physical)": "exercise",
    "wake_up_(_wake_up_before_6:00_am)": "wake_up",
    "screen_control_(the_wasteful_screen_time_must_be_less_than_1_hour_)": "screen_control"
})

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
