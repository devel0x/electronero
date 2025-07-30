import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
from math import exp

# === Constants ===
COIN = 100_000_000
RAMP_UP_END = 259_200
PEAK_END = 518_400
DECAY_RATE = 0.0000038405
MAX_HEIGHT = 6_000_000

def emission_reward(height):
    if height <= RAMP_UP_END:
        progress = height / RAMP_UP_END
        reward = 0.5 + (1.5 * progress)
    elif height <= PEAK_END:
        reward = 1.5
    else:
        reward = 1.10301990 * exp(-DECAY_RATE * (height - PEAK_END))
    return reward if reward * COIN >= 1 else 0.0

# === Compute rewards and supply ===
print("🔧 Calculating full emission curve...")
heights_all = np.arange(0, MAX_HEIGHT + 1)
rewards_all = np.array([emission_reward(h) for h in heights_all])
supply_all = np.cumsum(rewards_all)

# === Formatter for comma-separated tick labels ===
formatter = FuncFormatter(lambda x, _: f'{int(x):,}')

# === Plotting ===
fig, ax1 = plt.subplots(figsize=(12, 6))

# Cumulative Supply
ax1.plot(heights_all, supply_all, color='deepskyblue', label='Cumulative Supply')
ax1.set_xlabel("Block Height")
ax1.set_ylabel("Cumulative Supply (ITC)", color='deepskyblue')
ax1.tick_params(axis='y', labelcolor='deepskyblue')
ax1.xaxis.set_major_formatter(formatter)
ax1.yaxis.set_major_formatter(formatter)
ax1.grid(True, linestyle='--', alpha=0.3)

# Block Reward (Secondary Y-axis)
ax2 = ax1.twinx()
ax2.plot(heights_all, rewards_all, color='orange', linestyle='--', label='Block Reward')
ax2.set_ylabel("Block Reward (ITC)", color='orange')
ax2.tick_params(axis='y', labelcolor='orange')

# Title
plt.title("Interchained ITC Emission Curve + Block Reward")
plt.tight_layout()
plt.show()
