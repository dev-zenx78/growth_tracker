import os
from datetime import date


username = input("Enter your username: ")
today = str(date.today())

print("\nAnswer with y or n\n")

def yn_to_int(answer):
    return 1 if answer.lower() == "y" else 0



physics = yn_to_int(input("Did you study Physics today? (y/n): "))
additional = yn_to_int(input("Did you study Chemistry/Maths today? (y/n): "))
exercise = yn_to_int(input("Did you exercise today? (y/n): "))
wake = yn_to_int(input("Did you wake up between 5:00–5:30? (y/n): "))
screen = yn_to_int(input("Was wasteful screen time ≤ 1 hour? (y/n): "))

print("\nData collected successfully")

def already_logged_today(filename, today):
    if not os.path.exists(filename):
        return False

    with open(filename, "r") as file:
        for line in file:
            if f"Date: {today}" in line:
                return True
    return False



def remove_today_entry(filename, today):
    if not os.path.exists(filename):
        return

    new_lines = []
    skip = False

    with open(filename, "r") as file:
        for line in file:
            if line.strip() == f"Date: {today}":
                skip = True
                continue
            if skip and line.strip() == "--------------------":
                skip = False
                continue
            if not skip:
                new_lines.append(line)

    with open(filename, "w") as file:
        file.writelines(new_lines)


filename = f"data/{username}.txt"

remove_today_entry(filename, today)


with open(filename, "a") as file:
    file.write(f"Date: {today}\n")
    file.write(f"Physics: {physics}\n")
    file.write(f"Additional Subject: {additional}\n")
    file.write(f"Exercise: {exercise}\n")
    file.write(f"Wake on time: {wake}\n")
    file.write(f"Screen control: {screen}\n")
    file.write("-" * 20 + "\n")

print("Data saved successfully")
