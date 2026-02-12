# Dynamic Range Management Framework

## The Core Problem

**Static ranges fail because:**
- Market conditions change (volatility, trend, sentiment)
- Your position becomes suboptimal as price moves
- Impermanent loss accumulates when ranges are wrong
- Other LPs adapt, squeezing your fee capture

**Dynamic range management = Adjusting your position based on signals**

---

## Part 1: Market Regime Detection

### The 4 Market Regimes

| Regime | Characteristics | Best Range Strategy |
|--------|-----------------|---------------------|
| **1. High Volatility / Trending** | Large moves, directional, news-driven | Wide or hedged |
| **2. Low Volatility / Ranging** | Sideways, mean-reverting, consolidation | Narrow |
| **3. Breakout / Momentum** | Breaking key levels, volume surge | Exit or wide |
| **4. Uncertainty / Event Risk** | Pre-FOMC, earnings, protocol upgrades | Extremely wide or exit |

### Regime Detection Signals

#### Signal 1: Historical Volatility (HV)

```python
def calculate_hv(prices, window=20):
    """Annualized historical volatility"""
    log_returns = np.log(prices / prices.shift(1))
    volatility = log_returns.std() * np.sqrt(365)
    return volatility

# Interpretation
hv < 30%:   Low vol → Narrow ranges (±3-5%)
hv 30-60%:  Medium vol → Medium ranges (±10-15%)
hv > 60%:   High vol → Wide ranges (±25-50%) or exit
```

**Example:**
- ETH 30-day HV = 45% → Use ±15% range
- ETH 30-day HV = 85% (post-crash) → Use ±40% or exit

#### Signal 2: Options Implied Volatility (IV)

**Where to get it:**
- Deribit (ETH/BTC options)
- Lyra (on-chain)
- Panoptic (Uniswap-native)

```
IV Rank = Current IV / 52-week IV range

IV Rank > 80%:   Expecting big moves → Widen ranges
IV Rank 20-80%:  Normal conditions → Standard ranges  
IV Rank < 20%:   Complacency → Tighten ranges, but watch for vol expansion
```

**The IV-HV Spread:**
```
IV > HV (contango): Market pricing in future volatility → Expect moves
IV < HV (backwardation): Recent vol higher than expected → Calming down
```

#### Signal 3: ATR (Average True Range)

```python
# Daily ATR as % of price
daily_atr_pct = (ATR(14) / current_price) * 100

# Range width recommendation
range_width = daily_atr_pct * 3  # 3x daily move for buffer

# Example:
# ETH at $2,000, ATR = $80 (4%)
# Recommended range: ±12% (4% * 3)
```

---

## Part 2: On-Chain LP Intelligence

### Competitor Range Analysis

**Tool:** Revert.finance, APY.vision, or direct contract calls

```python
def analyze_liquidity_distribution(pool_address):
    """
    Analyze where other LPs have positioned their capital
    """
    # Get all active positions
    positions = get_v3_positions(pool_address)
    
    # Calculate liquidity histogram
    liquidity_by_tick = {}
    for pos in positions:
        for tick in range(pos.lower_tick, pos.upper_tick):
            liquidity_by_tick[tick] += pos.liquidity
    
    return liquidity_by_tick
```

**Strategic Insights:**

| Scenario | Interpretation | Action |
|----------|----------------|--------|
| Crowded around current price | Intense competition for fees | Widen range to capture edge moves |
| Sparse at edges | LPs expect mean reversion | Narrow range at center OR position at edges for breakouts |
| Bimodal distribution | Two schools of thought | Avoid the middle (low fee density) |
| Uniform distribution | Efficient market | Match the average range width |

### Tick Density Analysis

```
Pool: ETH/USDC 0.3%
Current tick: 205,000 ($2,050)

Tick Analysis:
204,800-205,200: 45% of total liquidity ← CROWDED (avoid)
205,200-206,000: 20% of liquidity
203,000-204,800: 25% of liquidity
Outside 203k-206k: 10% of liquidity ← OPPORTUNITY
```

**Strategy:** Position where liquidity is sparse but volume still exists.

---

## Part 3: News & Sentiment Signals

### Event-Driven Range Adjustments

#### Category 1: Protocol News (Uniswap-specific)

| Event | Expected Impact | Range Action |
|-------|----------------|--------------|
| V4 launch announcement | High volatility, initial chaos | Widen ±50% or exit |
| Fee tier change proposal | Medium volatility | Monitor volume shifts |
| Governance exploit | Extreme volatility | Exit immediately |
| New hook announcement | Medium-term range expansion | Gradual widening |

#### Category 2: Macro / Crypto News

```python
news_signals = {
    "ETF approval": {"vol_expectation": "+50%", "direction": "up", "range_action": "widen_upper"},
    "Fed rate decision": {"vol_expectation": "+30%", "direction": "either", "range_action": "widen_both"},
    "Exchange hack": {"vol_expectation": "+100%", "direction": "down", "range_action": "emergency_exit"},
    "Major partnership": {"vol_expectation": "+40%", "direction": "up", "range_action": "widen_upper"},
    "Regulatory clarity": {"vol_expectation": "+20%", "direction": "up", "range_action": "gradual_widen"},
}
```

#### Category 3: Social Sentiment

**Sources:**
- Twitter/X volume and sentiment (LunarCrush API)
- Reddit activity
- Telegram group chatter
- Funding rates (perpetuals)

```python
def sentiment_adjustment(sentiment_score, current_range):
    """
    sentiment_score: -100 (extreme fear) to +100 (extreme greed)
    """
    if sentiment_score > 80:  # Extreme greed
        # Expecting correction or consolidation
        return tighten_range(current_range, factor=0.8)
    elif sentiment_score < -80:  # Extreme fear
        # Capitulation, expect bounce or further drop
        return widen_range(current_range, factor=1.5)
    else:
        return current_range
```

---

## Part 4: Technical Analysis Integration

### Support/Resistance Levels

```python
key_levels = {
    "ETH": {
        "strong_support": [1800, 1600, 1400],
        "strong_resistance": [2200, 2500, 2800],
        "current": 2050
    }
}

def range_around_levels(current_price, levels):
    """
    Set range boundaries at key technical levels
    """
    # Find nearest support and resistance
    support = max([s for s in levels["strong_support"] if s < current_price])
    resistance = min([r for r in levels["strong_resistance"] if r > current_price])
    
    return {
        "lower": support * 0.98,  # 2% below support
        "upper": resistance * 1.02  # 2% above resistance
    }

# Example: ETH at $2,050
# Range: $1,764 (1800*0.98) to $2,244 (2200*1.02)
```

### Moving Average Envelopes

```python
def ma_envelope_range(prices, ma_period=20, envelope_pct=0.05):
    """
    Range centered around moving average with dynamic width
    """
    ma = prices.rolling(ma_period).mean()
    
    # Width based on volatility
    volatility = prices.pct_change().std()
    dynamic_width = envelope_pct * (1 + volatility * 10)
    
    return {
        "center": ma,
        "lower": ma * (1 - dynamic_width),
        "upper": ma * (1 + dynamic_width)
    }
```

---

## Part 5: The Rebalancing Decision Matrix

### When to Rebalance?

| Trigger | Threshold | Action | Priority |
|---------|-----------|--------|----------|
| Price near boundary | Within 5% of upper/lower | Prepare rebalance | High |
| Vol regime change | HV change >20% | Adjust width | High |
| IV spike | IV Rank >90% | Widen or exit | Critical |
| News event | Major announcement | Emergency assessment | Critical |
| Time-based | 7 days in position | Review | Medium |
| Fee accumulation | Fees >5% of principal | Compound decision | Low |
| Competitor shift | >30% liquidity moved | Reassess positioning | Medium |

### The Rebalancing Execution

```python
class RebalancingStrategy:
    def __init__(self, pool, position):
        self.pool = pool
        self.position = position
        
    def should_rebalance(self):
        signals = {
            "price_proximity": self.check_price_boundary(),
            "volatility_shift": self.check_vol_regime(),
            "iv_spike": self.check_iv_rank(),
            "news_impact": self.assess_news(),
            "time_decay": self.check_duration(),
        }
        
        # Weighted score
        score = sum(signals.values())
        return score > 0.7  # Threshold
    
    def execute_rebalance(self):
        # 1. Collect fees first
        self.collect_fees()
        
        # 2. Calculate new optimal range
        new_range = self.calculate_optimal_range()
        
        # 3. Remove old position
        self.remove_liquidity()
        
        # 4. Optional: Wait for gas optimization
        if not self.is_gas_optimal():
            self.schedule_for_later()
            return
        
        # 5. Add new position
        self.add_liquidity(new_range)
        
        # 6. Update hedges if using Strategy 4
        if self.hedge_active:
            self.rebalance_hedge()
```

---

## Part 6: Advanced - Multi-Factor Scoring

### The Range Score Algorithm

```python
def calculate_range_score(market_data):
    """
    Multi-factor scoring for range width decision
    Returns: 0-100 (higher = wider range needed)
    """
    
    scores = {
        # Volatility (30% weight)
        "hv_score": min(market_data.hv_30d / 100, 1) * 30,
        
        # IV (25% weight)
        "iv_score": (market_data.iv_rank / 100) * 25,
        
        # Trend strength (20% weight)
        "trend_score": abs(market_data.adx_14) / 100 * 20,
        
        # News sentiment (15% weight)
        "news_score": (market_data.news_volatility_expectation / 100) * 15,
        
        # On-chain competition (10% weight)
        "competition_score": market_data.liquidity_crowding_index * 10,
    }
    
    total_score = sum(scores.values())
    
    # Map score to range width
    if total_score < 25:
        return "narrow", "±5-8%"
    elif total_score < 50:
        return "medium", "±10-15%"
    elif total_score < 75:
        return "wide", "±20-30%"
    else:
        return "extreme", "±40%+ or exit"
```

---

## Part 7: Practical Implementation

### The Daily Check Routine

**Morning (9 AM):**
1. Check overnight volatility
2. Review options IV
3. Scan for overnight news
4. Assess current position vs boundaries

**Midday (2 PM):**
1. Monitor price action
2. Check competitor liquidity shifts
3. Review funding rates (if hedged)

**Evening (8 PM):**
1. Calculate daily PnL
2. Assess if rebalance needed tomorrow
3. Set alerts for boundary approaches

### Automation Possibilities

**Level 1: Alerts (Manual)**
- Set price alerts at ±80% of range
- Set vol alerts at regime change
- Manual rebalance decision

**Level 2: Semi-Automated**
- Bot calculates optimal range daily
- Sends recommendation
- Human approves execution

**Level 3: Fully Automated**
- Smart contract or keeper bot
- Threshold-based rebalancing
- Emergency circuit breakers

---

## Summary: The Dynamic LP Framework

```
INPUTS:
├── Volatility (HV, IV, ATR)
├── Market Structure (liquidity distribution)
├── News & Sentiment
├── Technical Levels
└── Time/Economic Events

PROCESSING:
├── Regime Classification
├── Risk Scoring
├── Range Optimization
└── Rebalancing Triggers

OUTPUT:
├── Current: Narrow/Medium/Wide/Extreme
├── Action: Hold/Rebalance/Exit
├── Target: New range boundaries
└── Hedge: Adjust perp/options positions
```

---

## Example Scenarios

### Scenario 1: ETH Pre-Merge

**Context:** ETH at $1,800, merge announcement confirmed

**Signals:**
- IV: 85% (extreme)
- News: "ETH merge in 3 days" (high impact)
- Competitors: All widening ranges
- Sentiment: Euphoric (+90)

**Decision:**
- Current range: ±10% ($1,620-$1,980) ← TOO NARROW
- Action: WIDEN to ±35% ($1,170-$2,430)
- Alternative: Exit and re-enter post-merge

**Outcome:**
- ETH swings $1,400-$2,100 during merge
- Wide range captures fees throughout
- Narrow range would have been knocked out

### Scenario 2: BTC Post-ETF Approval

**Context:** BTC at $45K, spot ETF approved

**Signals:**
- IV: 60% (elevated but falling)
- News: "ETF sees $500M inflows" (bullish but known)
- Trend: Strong upward, ADX 45
- Competitors: Positioning for continuation

**Decision:**
- Current range: ±20%
- Action: Asymmetric range — widen upper, tighten lower
- New range: $43K-$55K (vs $36K-$54K symmetric)

**Rationale:**
- More upside room for momentum
- Protective lower bound for pullback

---

## Tools & Data Sources

| Data Type | Source | Cost |
|-----------|--------|------|
| Volatility | TradingView, CoinGecko API | Free-$100/mo |
| Options IV | Deribit, Lyra, Panoptic | Free (on-chain) |
| On-chain | Revert, APY.vision, Dune | Free-$50/mo |
| News | RSS feeds, CryptoPanic | Free |
| Sentiment | LunarCrush, Santiment | Free-$300/mo |
| TA | TradingView, Coinigy | $15-100/mo |

---

## Conclusion

**Static LP ranges = Leaving money on the table**

The best LPs treat their positions like **active trading strategies**, continuously adapting to market conditions.

**Key Takeaways:**
1. Volatility is the primary driver of range width
2. Options IV is the best forward-looking indicator
3. Competitor positioning reveals fee density
4. News creates predictable volatility patterns
5. Rebalancing is a cost-benefit decision (gas vs IL protection)

**Recommended Reading:**
- "Market Microstructure" by Larry Harris
- "Volatility Trading" by Euan Sinclair
- Uniswap V3 whitepaper (concentrated liquidity math)

---

*This framework enables the transition from "passive LP" to "active market maker" — the key to superior returns in V3.*
