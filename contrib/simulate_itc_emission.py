import csv
from math import exp

# Constants
COIN = 100_000_000  # 1 ITC = 100 million satoshis
BLOCK_INTERVAL_SECONDS = 30
BLOCKS_PER_DAY = 24 * 60 * 60 // BLOCK_INTERVAL_SECONDS
BLOCKS_PER_YEAR = BLOCKS_PER_DAY * 365

# Emission phases
RAMP_UP_END = 259200          # ~6 months
PEAK_END = 518400             # ~12 months (1 year post genesis)
DECAY_RATE = 0.0000038405        # exponential decay after PEAK_END
# Output CSV file
OUTPUT_FILE = "itc_emission_simulation.csv"

def get_block_reward(height):
    if height <= RAMP_UP_END:
        progress = height / RAMP_UP_END
        reward = 0.5 + (1.5 * progress)  # ramp from 0.5 to 1.5 ITC
    elif height <= PEAK_END:
        reward = 1.5  # peak phase
    else:
        reward = 1.10301990 * exp(-DECAY_RATE * (height - PEAK_END))  # decay phase

    # Stop if below 1 satoshi
    if reward * COIN < 1:
        return 0.0

    return reward

def simulate_emission():
    height = 0
    total_emitted = 0.0
    records = []

    while True:
        reward = get_block_reward(height)
        if reward == 0.0:
            break

        total_emitted += reward
        records.append({
            'Block Height': height,
            'Reward (ITC)': round(reward, 8),
            'Total Emitted (ITC)': round(total_emitted, 8)
        })
        height += 1

    # Save to CSV
    with open(OUTPUT_FILE, 'w', newline='') as csvfile:
        fieldnames = ['Block Height', 'Reward (ITC)', 'Total Emitted (ITC)']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"Simulation complete. Final block: {height}")
    print(f"Total emitted: {total_emitted:.8f} ITC")
    print(f"Approx. lifespan: {height / BLOCKS_PER_YEAR:.2f} years")
    print(f"CSV saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    simulate_emission()
