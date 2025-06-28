#include <iostream>
#include <map>
#include <string>

// Simple staking pool demonstration. Not production-ready.
// Users stake an amount at a given block height and accrue rewards
// linearly per block. Rewards are minted native coins for simplicity.

class StakingPool {
public:
    explicit StakingPool(double reward_rate_per_block)
        : reward_rate(reward_rate_per_block) {}

    void stake(const std::string &user, uint64_t amount, uint64_t block_height) {
        StakeInfo &info = stakes[user];
        if (info.amount > 0) {
            // accumulate reward on existing stake before adding more
            info.amount += pending_rewards(user, block_height);
        }
        info.amount += amount;
        info.start_block = block_height;
    }

    uint64_t pending_rewards(const std::string &user, uint64_t block_height) const {
        auto it = stakes.find(user);
        if (it == stakes.end()) return 0;
        uint64_t blocks = block_height - it->second.start_block;
        return static_cast<uint64_t>(it->second.amount * reward_rate * blocks);
    }

    uint64_t withdraw(const std::string &user, uint64_t block_height) {
        auto it = stakes.find(user);
        if (it == stakes.end()) return 0;
        uint64_t reward = pending_rewards(user, block_height);
        uint64_t total = it->second.amount + reward;
        stakes.erase(it);
        return total;
    }

private:
    struct StakeInfo {
        uint64_t amount = 0;
        uint64_t start_block = 0;
    };

    double reward_rate; // reward per block per token
    std::map<std::string, StakeInfo> stakes;
};

int main() {
    StakingPool pool(0.02); // 2% reward per block for demo
    pool.stake("alice", 1000, 1);
    std::cout << "Rewards after 5 blocks: " << pool.pending_rewards("alice", 6) << '\n';
    uint64_t total = pool.withdraw("alice", 6);
    std::cout << "Alice withdraws total: " << total << '\n';
}
