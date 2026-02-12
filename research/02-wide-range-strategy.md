# Strategy 2: Wide Range / Passive Strategy

## Overview

**Risk Level:** 🟢 Low-Medium  
**Expected APR:** 15-50%  
**Effort:** Low (set and forget)  
**Best For:** Beginners, long-term holders

---

## How It Works

Provide liquidity across a **wide price range** (e.g., ±50-100% or full range) to minimize impermanent loss risk while still earning fees.

### Example Setups

**Conservative Setup (ETH/USDC):**

| Parameter | Value |
|-----------|-------|
| Current ETH Price | $2,050 |
| Lower Bound | $1,025 (50% below) |
| Upper Bound | $4,100 (100% above) |
| Range Width | 2x current price |
| Capital Required | $10,000 |
| Fee Tier | 0.30% |

**Ultra-Conservative (Near Full Range):**

| Parameter | Value |
|-----------|-------|
| Lower Bound | $200 (ETH bear market low) |
| Upper Bound | $10,000 (ETH ATH) |
| Range Width | 50x current price |
| Capital Efficiency | ~2x V2 equivalent |

---

## Mechanics

### Capital Efficiency vs V2

Even wide ranges are more efficient than V2's (0, ∞):

| Range Width | Capital Efficiency vs V2 |
|-------------|--------------------------|
| Full Range | 1x (same as V2) |
| ±100% | ~2x |
| ±50% | ~4x |
| ±25% | ~8x |

### Position Characteristics

**When price stays within range:**
- Earn fees proportional to liquidity share
- Experience IL similar to V2 (but slightly less due to range limits)

**When price exits range:**
- 100% single asset exposure (same as V2)
- No fee earnings until price returns

---

## Expected Returns

### Historical Performance (Major Pools, 2023-2024)

| Pool | Range | Avg APR | Worst Month | Best Month |
|------|-------|---------|-------------|------------|
| ETH/USDC 0.3% | ±75% | 25-35% | 8% | 65% |
| WBTC/ETH 0.3% | ±50% | 20-28% | 5% | 52% |
| ETH/USDT 0.3% | ±100% | 18-25% | 6% | 48% |

### Comparison to V2

| Metric | V2 (Full Range) | V3 (Wide ±75%) | Advantage |
|--------|----------------|----------------|-------------|
| Capital Efficiency | 1x | ~3x | V3 +200% |
| IL Exposure | High | Medium-High | Similar |
| Fee Capture | Lower | Higher | V3 ~2-3x |
| Gas Costs | Lower | Higher | V2 wins |

---

## Risk Analysis

### Impermanent Loss Risk: 🟡 MODERATE

**Key Insight:** Wide ranges reduce IL risk but don't eliminate it.

Example with ±75% range:

```
Initial: $5,000 ETH + $5,000 USDC at $2,000 ETH
Range: $500 - $3,500

Scenario 1: ETH drops to $1,200 (-40%)
- Still in range ✅
- IL = ~8% (vs 20% if held 100% ETH)
- Still earning fees ✅

Scenario 2: ETH drops to $400 (-80%)
- Exits lower bound ❌
- Position becomes 100% ETH (worth $2,000)
- IL = 60% (similar to V2)
```

### Comparison to HODL

| Strategy | ETH to $4,000 | ETH to $1,000 | ETH stays flat |
|----------|---------------|---------------|----------------|
| HODL 50/50 | +25% | -25% | 0% |
| Wide LP ±75% | +20% + fees | -20% + fees | +25% APR |
| Narrow LP ±5% | Out of range | Out of range | +150% APR |

---

## Best Practices

### 1. Range Selection

**Conservative Rule of Thumb:**
- Lower bound: 50% of current price (bear market support)
- Upper bound: 200% of current price (bull market target)

**For Crypto-Natives:**
- Lower bound: Previous cycle low
- Upper bound: 3-5x current price

### 2. Pair Selection

**Ideal Pairs:**
- Blue chips you plan to hold long-term
- High daily volume (>$10M)
- Established fee tiers with consistent activity

**Top Recommendations:**
1. **ETH/USDC (0.30%)** - Most reliable
2. **WBTC/ETH (0.30%)** - Correlated pair, lower IL
3. **ETH/USDT (0.30%)** - High volume alternative
4. **MATIC/ETH (0.30%)** - L2 exposure

### 3. Fee Tier Optimization

| Pool | Recommended Fee | Rationale |
|------|----------------|-----------|
| ETH/USDC | 0.30% | Sweet spot for majors |
| Stablecoins | 0.05% | Lower fees, higher volume |
| WBTC/ETH | 0.30% | Correlated, lower IL |
| Altcoins | 0.30% or higher | Compensate for risk |

---

## Advanced: "Laddering" Strategy

Split capital across multiple wide ranges to capture different scenarios:

### Example: $10,000 across 3 ETH/USDC positions

| Position | Range | Capital | Purpose |
|----------|-------|---------|---------|
| #1 | $1,000 - $2,000 | $3,000 | Bear market accumulation |
| #2 | $1,500 - $3,000 | $4,000 | Current range, high fee |
| #3 | $2,500 - $5,000 | $3,000 | Bull market upside |

**Benefits:**
- Always some liquidity in-range
- Dollar-cost averaging effect
- Reduced IL through diversification

---

## Tax & Rebalancing Considerations

### Tax Efficiency

Wide ranges require fewer rebalances = fewer taxable events

| Strategy | Rebalances/Year | Tax Events |
|----------|-----------------|------------|
| Narrow (±5%) | 20-50 | High |
| Wide (±75%) | 2-5 | Low |
| Full Range | 0-1 | Minimal |

**Pro Tip:** In jurisdictions with capital gains tax, wide ranges are more tax-efficient.

---

## Tools & Monitoring

### Set-and-Forget Tracking

- **Zapper.fi** - Portfolio overview
- **DeBank** - Multi-chain tracking
- **APY.vision** - Position performance

### Rebalance Alerts

Set alerts for:
- Price within 10% of upper/lower bound
- Accumulated fees > 5% of position value
- Time in position > 6 months (tax optimization)

---

## Case Studies

### Case 1: The "HODL+" Strategy (2022-2024)

**Investor:** Long-term ETH holder wanting yield

**Setup:**
- $50,000 in ETH/USDC ±100% range
- 0.30% fee tier on Ethereum mainnet
- Held through bear market

**Results:**
- 2022: -60% (ETH price drop), but earned 22% APR in fees
- 2023: Recovered, earned 35% APR
- 2024: Position exited upper bound (ETH > $4,000)
- **Total 2.5yr return:** +45% vs +30% for pure HODL

### Case 2: Stablecoin Pair (USDC/USDT)

**Setup:**
- $100,000 in 0.01% fee tier
- Full range (0.95 - 1.05)

**Results:**
- APR: 4-8% (low but steady)
- IL: Minimal (<0.5% annual)
- Comparable to: Aave/Compound lending rates

---

## Summary

| Pros | Cons |
|------|------|
| Lower IL risk | Lower APR than narrow ranges |
| Set-and-forget simplicity | Still vulnerable to major moves |
| Tax efficient (fewer rebalances) | Requires patience |
| Good for long-term holders | Opportunity cost in bull markets |
| Beginner-friendly | Gas costs on mainnet |

**Verdict:** The best starting point for new V3 LPs. Combine with Strategy 3 (automated vaults) for truly passive income.
