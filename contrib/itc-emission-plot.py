import matplotlib.pyplot as plt
import numpy as np
import imageio.v2 as imageio
import os
from math import exp

# === Constants ===
COIN = 100_000_000
RAMP_UP_END = 259200
PEAK_END = 518400
DECAY_RATE = 0.0000038405

def emission_reward(height):
    if height <= RAMP_UP_END:
        progress = height / RAMP_UP_END
        reward = 0.5 + (1.5 * progress)
    elif height <= PEAK_END:
        reward = 1.5
    else:
        reward = 1.10301990 * exp(-DECAY_RATE * (height - PEAK_END))

    return reward if reward * COIN >= 1 else 0.0

# === Parameters ===
num_frames = 10_000
max_height = 6_000_000
heights = np.linspace(0, max_height, num_frames, dtype=int)
rewards = [emission_reward(h) for h in heights]
total_supply = np.cumsum(rewards)

# === Frame Output ===
frames_dir = "gif_frames"
os.makedirs(frames_dir, exist_ok=True)
filenames = []

# === Create Frames ===
for i in range(1, len(heights) + 1):
    print("✅ saving image: " + str(i))
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(heights[:i], total_supply[:i], color='deepskyblue')
    ax.set_xlim(0, max_height)
    ax.set_ylim(0, max(total_supply) * 1.05)
    ax.set_title("Interchained ITC Emission Curve")
    ax.set_xlabel("Block Height")
    ax.set_ylabel("Cumulative Supply (ITC)")
    ax.grid(True, linestyle='--', alpha=0.3)

    fname = f"{frames_dir}/frame_{i:03d}.png"
    fig.savefig(fname, dpi=100)
    plt.close(fig)
    filenames.append(fname)

# === Build GIF ===
images = [imageio.imread(f) for f in filenames]
imageio.mimsave("itc_emission_curve_fixed.gif", images, fps=20)
print("✅ Saved: itc_emission_curve_fixed.gif")
