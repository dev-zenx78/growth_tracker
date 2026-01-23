import os
import matplotlib.pyplot as plt
import numpy as np

def plot_radar_chart(habit_averages, username):
    labels = ['Physics', 'Additional Subject', 'Exercise', 'Wake Up', 'Screen Control']
    values = habit_averages.values.tolist() + [habit_averages.values[0]]  # Close the loop
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]
    
    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(projection='polar'))
    ax.fill(angles, values, 'b', alpha=0.25)
    ax.plot(angles, values, 'o-', linewidth=2)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_ylim(0, 1)
    ax.set_title(f'Habit Averages for {username}', size=16, fontweight='bold', pad=20)
    plt.tight_layout()
    
    os.makedirs('data/individual_images', exist_ok=True)
    filename = f'data/individual_images/{username}_radar.png'
    plt.savefig(filename)
    plt.close()
    return filename 