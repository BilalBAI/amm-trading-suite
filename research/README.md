# 5 Uniswap V3 LP Money-Making Strategies

Research conducted: February 11, 2026

## Executive Summary

Uniswap V3's **concentrated liquidity** allows LPs to allocate capital within specific price ranges, dramatically increasing capital efficiency (up to 4000x vs V2). However, it introduces impermanent loss (IL) management complexity.

Each strategy has different **risk/reward profiles** based on:
- Range width (narrow = higher yield, higher IL risk)
- Fee tier (0.05% for stablecoins, 0.3% for majors, 1% for exotic)
- Rebalancing frequency
- Hedging approach

## The 5 Strategies

1. **[Narrow Range / High Yield Strategy](strategy-1-narrow-range.md)**
   Aggressive fee capture in tight ranges

2. **[Wide Range / Passive Strategy](strategy-2-wide-range.md)**
   Set-and-forget with lower maintainance

3. **[Automated LP Vaults](strategy-3-automated-vaults.md)**
   Arrakis, Gamma, Beefy Finance

4. **[Delta-Neutral Hedging](strategy-4-delta-hedging.md)**
   Using perps/options to hedge IL

5. **[Just-In-Time Liquidity](strategy-5-jit-liquidity.md)**
   MEV-aware concentrated providing

---

## Key Concepts from Research

### Concentrated Liquidity Mechanics

In V3, LPs choose **price ranges** [P_lower, P_upper] instead of (0, ∞).

**Capital Efficiency:** Providing liquidity in [0.99, 1.01] for stablecoins can generate **same depth with 1/200th the capital** compared to V2.

**Tick Spacing:**
- 0.01% fee tier (stablecoins): 1 tick spacing
- 0.05% fee tier: 10 tick spacing  
- 0.30% fee tier (standard): 60 tick spacing
- 1.00% fee tier (exotics): 200 tick spacing

### Impermanent Loss Formula

For concentrated liquidity in V3, IL is **amplified** compared to V2:

```
If price moves from P0 to P1 outside your range:
IL_V3 > IL_V2 for same % price move
```

This is because the LP becomes 100% in the depreciating asset when price exits range.

---

## Summary Table: All 5 Strategies

| Strategy | Risk | APR Range | Effort | Best For | Capital Req |
|----------|------|-----------|--------|----------|-------------|
| 1. Narrow Range | 🔴 High | 50-200% | High | Experienced | Any |
| 2. Wide Range | 🟢 Low | 15-50% | Low | Beginners | Any |
| 3. Auto Vaults | 🟡 Med | 25-80% | Minimal | Passive | $1K+ |
| 4. Delta-Neutral | 🟡 Adv | 40-120% | High | Traders | $10K+ |
| 5. JIT | 🔴 Expert | 100-500% | Extreme | MEV Pros | $10M+ |

## Quick Decision Guide

**I'm new to V3:** Start with Strategy 2 (Wide Range) or Strategy 3 (Vaults)

**I have time and want higher yields:** Strategy 1 (Narrow) with careful monitoring

**I know derivatives:** Strategy 4 (Hedging) for superior risk-adjusted returns

**I want completely passive:** Strategy 3 (Vaults) - hands-off automation

**I'm a sophisticated MEV searcher:** Strategy 5 (JIT) - but you already know this

---

## References

- [Uniswap V3 Whitepaper](https://uniswap.org/whitepaper-v3.pdf)
- [Concentrated Liquidity Docs](https://docs.uniswap.org/concepts/protocol/concentrated-liquidity)
- Arrakis Finance - Automated Market Making
- Gamma Strategies - Active Liquidity Management
- Panoptic Research - Options-based Hedging
- Haydens Adams V2 Whitepaper (HackMD)
- DeFi Llama - Protocol Analytics
- Revert Finance - V3 Analytics
- APY.vision - LP Performance Tracking
