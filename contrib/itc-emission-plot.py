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
    return reward

# === Generate full reward data ===
max_height = 6_000_000
rewards = np.array([emission_reward(h) for h in range(max_height + 1)], dtype=np.float32)
total_supply = np.cumsum(rewards)

# === Animation config ===
num_frames = 250
frame_heights = np.linspace(1, max_height, num_frames, dtype=int)

# === Downsampling function ===
def downsample(x, y, max_points=1000):
    if len(x) <= max_points:
        return x, y
    step = len(x) // max_points
    return x[::step], y[::step]

# === Output folders ===
frames_dir = "gif_frames"
os.makedirs(frames_dir, exist_ok=True)
filenames = []

# === Create frames ===
for i, h in enumerate(frame_heights):
    print(f"📸 Frame {i+1}/{num_frames}, height={h}")
    x = np.arange(h + 1)
    y = total_supply[:h + 1]
    x_ds, y_ds = downsample(x, y)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(x_ds, y_ds, color='deepskyblue')
    ax.set_xlim(0, max_height)
    ax.set_ylim(0, total_supply[-1] * 1.05)
    ax.set_title("Interchained ITC Emission Curve")
    ax.set_xlabel("Block Height")
    ax.set_ylabel("Cumulative Supply (ITC)")
    ax.grid(True, linestyle='--', alpha=0.3)

    fname = f"{frames_dir}/frame_{i:04d}.png"
    fig.savefig(fname, dpi=100)
    plt.close(fig)
    filenames.append(fname)

# === Build GIF ===
with imageio.get_writer("itc_emission_curve.gif", mode='I', fps=20) as writer:
    for fname in filenames:
        writer.append_data(imageio.imread(fname))

print(f"✅ GIF saved! Total Supply: {total_supply[-1]:,.0f} ITC")
