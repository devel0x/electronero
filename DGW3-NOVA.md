# 💠 DGW3-NOVA: Adaptive Difficulty Retargeting Algorithm

## 🧠 Overview

**DGW3-NOVA** is an advanced, height-aware evolution of **Dark Gravity Wave v3 (DGW3)**, designed for faster blockchains like *Interchained* that need **smooth, safe, and reactive difficulty adjustment**. It addresses rapid hashrate changes and timestamp manipulation without sacrificing block time stability.

This version introduces **graceful decay**, **rolling medians**, **asymmetric clamps**, and **emergency controls** — all applied conditionally at fork heights.

---

## 🔧 Motivation

Standard DGW3 reacts sharply to fast solve times and extreme hashrate drops, causing instability or stalls. DGW3-NOVA refines that:

- Prevents abrupt difficulty drops (death spiral)
- Smooths upward difficulty to reflect real hashrate increases
- Gradually adjusts to slow blocks without panicking

---

## 🏗️ Architecture Summary

| Fork     | Height   | Features                                                                 |
|----------|----------|--------------------------------------------------------------------------|
| Fork 4   | N/A      | Log2-based graceful decay                                                |
| Fork 5   | N/A      | Exponential decay with cap                                               |
| Fork 6   | 12818+   | Emergency clamp, improved decay logic                                    |
| Fork 7   | 14299+   | Decay exponent `0.45`, decay cap `2.0`, min solve time `15s`             |
| **Fork 8** | 14342+ | ✅ Rolling median solve time<br>✅ Median-smoothed difficulty<br>✅ Asymmetric clamp (drop slower than rise) |

---

## 🔍 Core Enhancements

### ✅ 1. Graceful Decay Logic

Applies an exponential decay factor only when `solveTime > targetSpacing`:

```cpp
multiplier = actualSolveTime / targetSpacing;
decayFactor = pow(multiplier, exponent);     // exponent varies by fork
```

| Fork    | Exponent | Cap  |
|---------|----------|------|
| ≤Fork5  | 0.6      | 4.0  |
| Fork6   | 0.5      | 3.0  |
| Fork7   | 0.45     | 2.0  |

Used to **soften difficulty drops** without overreacting.

---

### ✅ 2. Emergency Difficulty Clamp

If solve time is *too fast* and cumulative timespan too short, trigger emergency decay:

```cpp
if (actualSolveTime < 2 × minSolve && timespan < target / 6)
```

Avoids block flooding or timestamp abuse.

---

### ✅ 3. Rolling Median Solve Time (Fork 8)

Replaces volatile `actualSolveTime` with a median over past 9 blocks:

```cpp
solveTimes = last 9 intervals;
rollingSolveTime = median(solveTimes);
```

Reduces noise from outlier blocks.

---

### ✅ 4. Difficulty Median Smoothing (Fork 8)

Uses a median of last 5 difficulties instead of raw average:

```cpp
pastDiffs = last 5 difficulties;
difficultySmoothing = median(pastDiffs);
```

Prevents recent spikes/drops from distorting the trend.

---

### ✅ 5. Asymmetric Difficulty Clamping (Fork 8+)

Downward adjustments apply **decay**, while upward jumps remain **agile**:

```cpp
if (baseline < previous) {
    newDifficulty = previous - ((previous - baseline) / decayFactor);
}
```

Lets difficulty catch up to rising hashrate quickly, while being cautious on the way down.

---

## 📈 Visual Behavior (Expected)

- 📉 Smooth decay of difficulty after block floods
- 📈 Quick rise in difficulty after sustained fast blocks
- 🎯 Stable long-term average near target spacing
- 🛡️ Protection from timestamp games and difficulty manipulation

---

## ⚙️ Final Formula (Simplified)

```cpp
// Median smoothing
difficultySmoothing = median(pastN difficulties)
rollingSolveTime = median(lastN solve times)

// Graceful decay
decayFactor = pow(min(actualSolveTime / target, cap), exponent)

// Baseline update
baseline = difficultySmoothing * actualTimespan / target

// Final difficulty
if (dropping):
    newDifficulty = difficultySmoothing - ((difficultySmoothing - baseline) / decayFactor)
else:
    newDifficulty = baseline
```

---

## 🧬 Compatibility

- ✅ Built on DGW3 (inherits weighted average + timespan clamping)
- ✅ Uses `nBits` compact target format
- ✅ Plug-and-play in `GetNextWorkRequired()`-style interfaces

---

## 📚 Suggested Citation

> *DGW3-NOVA: A Fork-Aware, Asymmetric, Graceful Decay Difficulty Algorithm for Fast Blockchains.*  
> Interchained Project, 2025. Based on Dark Gravity Wave v3 by Evan Duffield.
