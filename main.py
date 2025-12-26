import os
from datetime import date


username = input("Enter your username: ")
today = str(date.today())

print("\nAnswer with y or n\n")

physics = input("Did you study Physics today? (y/n): ")
additional = input("Did you study Chemistry/Maths today? (y/n): ")
exercise = input("Did you exercise today? (y/n): ")
wake = input("Did you wake up between 5:00–5:30? (y/n): ")
screen = input("Was wasteful screen time ≤ 1 hour? (y/n): ")

print("\nData collected successfully")

filename = f"data/{username}.txt"

with open(filename, "a") as file:
    file.write(f"Date: {today}\n")
    file.write(f"Physics: {physics}\n")
    file.write(f"Additional Subject: {additional}\n")
    file.write(f"Exercise: {exercise}\n")
    file.write(f"Wake on time: {wake}\n")
    file.write(f"Screen control: {screen}\n")
    file.write("-" * 20 + "\n")

print("Data saved successfully")
