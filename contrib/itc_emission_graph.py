import matplotlib.pyplot as plt
from math import exp

# Constants
BLOCKS_PER_DAY = 2880
DAYS_PER_MONTH = 30
RAMP_UP_MONTHS = 6
PEAK_MONTHS = 12
RAMP_UP_END = RAMP_UP_MONTHS * DAYS_PER_MONTH * BLOCKS_PER_DAY
PEAK_END = RAMP_UP_END + (PEAK_MONTHS * DAYS_PER_MONTH * BLOCKS_PER_DAY)
PEAK_REWARD = 1.0
INITIAL_REWARD = 0.5
DECAY_RATE = 0.0000044  # Adjust this to stretch lifespan

# Simulation
rewards = []
supply = []
total_supply = 0
height = 0

while True:
    if height <= RAMP_UP_END:
        progress = height / RAMP_UP_END
        reward = INITIAL_REWARD + ((PEAK_REWARD - INITIAL_REWARD) * progress)
    elif height <= PEAK_END:
        reward = PEAK_REWARD
    else:
        reward = PEAK_REWARD * exp(-DECAY_RATE * (height - PEAK_END))
        if reward < 0.00000001:  # Stop once rewards drop below 1 sat
            break

    total_supply += reward
    rewards.append(reward)
    supply.append(total_supply)
    height += 1

# Plot
fig, axs = plt.subplots(2, 1, figsize=(12, 6), sharex=True)

axs[0].plot(rewards, color='blue')
axs[0].set_ylabel('Reward per Block (ITC)')
axs[0].set_title('ITC Emission Curve (Graceful Ramp → 12mo Peak → Decay)')

axs[1].plot(supply, color='green')
axs[1].set_xlabel('Block Height')
axs[1].set_ylabel('Cumulative Emitted Supply (ITC)')

plt.tight_layout()
plt.show()
