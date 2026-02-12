# Strategy 1: Narrow Range / High Fee Strategy

## Overview

**Risk Level:** 🔴 High  
**Expected APR:** 50-200%+  
**Effort:** High (requires active monitoring)  
**Best For:** Experienced LPs, volatile pairs

---

## How It Works

Provide liquidity in a **tight price range** (e.g., ±5-10% around current price) to capture maximum fees while the price stays in-range.

### Example Setup

**Pool:** ETH/USDC 0.30% fee tier

| Parameter | Value |
|-----------|-------|
| Current ETH Price | $2,050 |
| Lower Bound | $1,948 (5% below) |
| Upper Bound | $2,153 (5% above) |
| Range Width | ±5% |
| Capital Required | $10,000 |
| Fee Tier | 0.30% |

**Capital Efficiency:** Your liquidity is 20x more concentrated than providing full range, meaning you earn 20x the fees per dollar while in-range.

---

## Mechanics

### Tick Selection

Uniswap V3 uses ticks spaced at 0.01% intervals:

```
Tick 0: 1.0000
Tick 1: 1.0001 (+0.01%)
Tick 2: 1.0002 (+0.02%)
...
```

For 0.30% fee tier, ticks are spaced 60 ticks apart (0.6% per tick boundary).

### Position Sizing

| Price Movement | Outcome |
|----------------|---------|
| Stays in 5% range | Earn fees at 20x efficiency |
| Exits upper bound | 100% ETH (sold USDC at upper price) |
| Exits lower bound | 100% USDC (bought ETH at lower price) |

---

## Expected Returns

### Historical Data (ETH/USDC 0.3% pool, 2024)

| Range Width | Avg APR | Time In-Range |
|-------------|---------|---------------|
| ±2.5% | 150-400% | ~40% |
| ±5% | 80-200% | ~60% |
| ±10% | 30-80% | ~80% |

**Key Insight:** Narrower ranges = higher APR when active, but higher risk of going out-of-range.

### Fee Calculation

```
Fee Income = (Pool Volume × Fee Tier) × (Your Liquidity / Total Liquidity in Range)

Example:
- Pool daily volume: $50M
- Fee tier: 0.30%
- Your liquidity: $10K in narrow range
- Total liquidity in your range: $500K

Daily Fees = ($50M × 0.003) × ($10K / $500K) = $150 × 0.02 = $3/day
Annualized = $1,095 (10.95% APR)
```

*Note: If concentrated 20x more than full-range LPs, effective APR is ~219%*

---

## Risk Analysis

### Impermanent Loss Risk: 🔴 HIGH

When price exits your range, you experience:

1. **Full IL** on one asset (100% exposure)
2. **No fee earnings** until price returns
3. **Opportunity cost** of capital sitting idle

### IL Calculation Example

```
Initial: $5,000 ETH + $5,000 USDC at $2,000 ETH
Range: $1,900 - $2,100

If ETH drops to $1,800 (outside range):
- Position becomes 100% ETH (worth $4,500 at new price)
- IL = $500 (10% loss)
- Plus gas costs to rebalance
```

### Volatility Risk

| Volatility Level | Suitable? | Notes |
|------------------|-----------|-------|
| Low (<30% annual) | ✅ Yes | Stablecoins, wrapped BTC/ETH |
| Medium (30-60%) | ⚠️ Caution | ETH majors, need wider ranges |
| High (>60%) | ❌ No | Meme coins, frequent rebalancing needed |

---

## Best Practices

### 1. Pair Selection

**Ideal Pairs:**
- High volume + relatively stable (ETH/USDC, WBTC/ETH)
- Low fee tier pools (0.05% for stablecoins)
- Established pools with consistent volume

**Avoid:**
- Low volume exotic pairs
- Pairs with extreme volatility (>100% annual)
- New/untested tokens

### 2. Rebalancing Strategy

**Manual Approach:**
1. Set alerts at ±2% from range bounds
2. When price approaches boundary, prepare rebalance transaction
3. Remove liquidity, wait for price to stabilize
4. Re-add at new range around current price

**Optimal Rebalance Triggers:**
- Price within 1% of upper/lower bound
- Gas costs < 10% of accrued fees
- Volume declining (lower opportunity cost)

### 3. Fee Tier Selection

| Pair Type | Recommended Fee | Rationale |
|-----------|----------------|-----------|
| Stablecoins | 0.01% | High volume, tight spreads |
| ETH majors | 0.30% | Standard, good volume |
| Altcoins | 0.30-1.00% | Compensate for IL risk |
| Exotics | 1.00% | High IL risk, need compensation |

---

## Real Examples

### Case Study: ETH/USDC on Arbitrum (2024)

**Strategy:** ±7% range, 0.30% fee tier

| Month | Time In-Range | Gross APR | Rebalance Costs | Net APR |
|-------|---------------|-----------|-----------------|---------|
| Jan | 65% | 180% | 15% | 165% |
| Feb | 58% | 155% | 18% | 137% |
| Mar | 72% | 210% | 12% | 198% |
| Apr | 45% | 95% | 25% | 70% |

**Lesson:** Even "wide" narrow ranges (7%) can be challenging in volatile markets.

---

## Tools & Resources

### Position Tracking
- [Revert Finance](https://revert.finance/) - V3 position analytics
- [APY.vision](https://apy.vision/) - LP performance tracking
- [DexScreener](https://dexscreener.com/) - Real-time price monitoring

### Calculators
- [Uniswap V3 Fee Calculator](https://uniswapv3.flipsidecrypto.com/)
- [Daily DeFi IL Calculator](https://dailydefi.org/tools/impermanent-loss-calculator/)

---

## Summary

| Pros | Cons |
|------|------|
| Extremely high capital efficiency | High IL risk when out of range |
| Best fee capture when active | Requires constant monitoring |
| Clear entry/exit strategy | Gas costs for rebalancing |
| Works in trending markets | Emotional stress from IL |

**Verdict:** Best for experienced LPs with time to actively manage positions. Beginners should start with Strategy 2 (Wide Range) or Strategy 3 (Automated Vaults).
