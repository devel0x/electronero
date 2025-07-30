import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import imageio.v2 as imageio
import os
from math import exp

# === Constants ===
COIN = 100_000_000
RAMP_UP_END = 259_200
PEAK_END = 518_400
DECAY_RATE = 0.0000038405
MAX_HEIGHT = 6_000_000
NUM_FRAMES = 130

def emission_reward(height):
    if height <= RAMP_UP_END:
        progress = height / RAMP_UP_END
        reward = 0.5 + (1.5 * progress)
    elif height <= PEAK_END:
        reward = 1.5
    else:
        reward = 1.10301990 * exp(-DECAY_RATE * (height - PEAK_END))
    return reward if reward * COIN >= 1 else 0.0

# === Step 1: Compute all rewards and supply ===
print("🔧 Calculating emission for all blocks...")
heights_all = np.arange(0, MAX_HEIGHT + 1)
rewards_all = np.array([emission_reward(h) for h in heights_all])
supply_all = np.cumsum(rewards_all)

# === Step 2: Logarithmic frame progression ===
frame_indices = np.geomspace(1, MAX_HEIGHT, NUM_FRAMES, dtype=int)
frame_indices = np.unique(frame_indices)

# === Formatter for comma-separated tick labels ===
formatter = FuncFormatter(lambda x, _: f'{int(x):,}')

# === Step 3: Save frames ===
frames_dir = "gif_frames_adaptive_2"
os.makedirs(frames_dir, exist_ok=True)
filenames = []

for i, idx in enumerate(frame_indices):
    print(f"📸 Saving frame {i+1}/{len(frame_indices)}: block {idx}")
    fig, ax1 = plt.subplots(figsize=(10, 5))

    # Primary axis: Cumulative Supply
    ax1.plot(heights_all[:idx+1], supply_all[:idx+1], color='deepskyblue', label='Cumulative Supply')
    ax1.set_xlim(0, heights_all[idx])
    ax1.set_ylim(0, supply_all[idx] * 1.05)
    ax1.set_xlabel("Block Height")
    ax1.set_ylabel("Cumulative Supply (ITC)", color='deepskyblue')
    ax1.tick_params(axis='y', labelcolor='deepskyblue')
    ax1.xaxis.set_major_formatter(formatter)
    ax1.yaxis.set_major_formatter(formatter)
    ax1.grid(True, linestyle='--', alpha=0.3)

    # Secondary axis: Block Reward
    ax2 = ax1.twinx()
    ax2.plot(heights_all[:idx+1], rewards_all[:idx+1], color='orange', linestyle='--', label='Block Reward')
    ax2.set_ylim(0, max(rewards_all[:idx+1]) * 1.1)
    ax2.set_ylabel("Block Reward (ITC)", color='orange')
    ax2.tick_params(axis='y', labelcolor='orange')

    # Title
    ax1.set_title("Interchained ITC Emission Curve + Block Reward")

    # Save frame
    fname = f"{frames_dir}/frame_{i:04d}.png"
    fig.savefig(fname, dpi=100)
    plt.close(fig)
    filenames.append(fname)

# === Step 4: Build final GIF ===
gif_path = "itc_emission_full.gif"
with imageio.get_writer(gif_path, mode='I', fps=20, loop=0) as writer:
    for fname in filenames:
        writer.append_data(imageio.imread(fname))

print(f"✅ Done! Saved GIF: {gif_path}")

