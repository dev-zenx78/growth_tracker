import pandas as pd
import random
from datetime import datetime, timedelta

users = ['Zenx', 'Kritarth', 'exe', 'DharmXveer']
habits = ['Physics', 'Additional subject (chemistry/maths)', 'Exercise', 'Wake up', 'Screen control']

data = []

start_date = datetime(2025, 12, 1)

for user in users:
    num_entries = random.randint(25, 30)
    for _ in range(num_entries):
        date = start_date + timedelta(days=random.randint(0, 28))
        time = f"{random.randint(8,22):02d}:{random.randint(0,59):02d}:00"
        timestamp = f"{date.strftime('%m/%d/%Y')} {time}"
        row = [timestamp, user]
        for habit in habits:
            row.append(random.choice(['Done', 'Not done']))
        data.append(row)

df = pd.DataFrame(data, columns=['Timestamp', 'Username'] + habits)
df.to_csv('form_data/sample_growth_data.csv', index=False)
print("Sample data generated: form_data/sample_growth_data.csv")
