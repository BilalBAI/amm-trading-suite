# Percentage-Based Liquidity Ranges

## Overview

The `add-range` command and `add_liquidity_range()` method provide a more intuitive way to add liquidity to Uniswap V3 pools by specifying price ranges as **percentages** around the current pool price, rather than as absolute tick values.

## Why Use Percentage Ranges?

### Benefits

1. **Intuitive**: Think in terms of "I want liquidity from -5% to +5%" rather than calculating tick values
2. **Dynamic**: Automatically adjusts to current market price
3. **Strategy-Focused**: Easily implement common liquidity strategies
4. **No Tick Math**: No need to manually convert prices to ticks or worry about tick spacing

### Traditional vs. Percentage Approach

**Traditional (tick-based):**
```bash
# You need to:
# 1. Get current price
# 2. Calculate target prices
# 3. Convert prices to ticks
# 4. Round to tick spacing
amm-trading add WETH USDT 3000 -887220 887220 0.1 300
```

**New (percentage-based):**
```bash
# Simply specify percentage range
amm-trading add-range WETH USDT 3000 -0.05 0.05 0.1 300
```

## How It Works

### The Conversion Process

1. **Get Current Price**: Fetches the current pool price from the blockchain
2. **Calculate Target Prices**:
   - `price_lower = current_price × (1 + percent_lower)`
   - `price_upper = current_price × (1 + percent_upper)`
3. **Convert to Ticks**: Uses the formula `tick = log(price) / log(1.0001)`
4. **Round to Spacing**: Ensures ticks are valid for the pool's fee tier
5. **Add Liquidity**: Calls the standard liquidity addition with calculated ticks

### Example Calculation

For WETH/USDT at current price of $3000:

```
Input:    percent_lower = -0.05 (-5%)
          percent_upper = 0.05 (+5%)

Step 1:   current_price = 3000 USDT per WETH

Step 2:   price_lower = 3000 × (1 - 0.05) = 2850 USDT
          price_upper = 3000 × (1 + 0.05) = 3150 USDT

Step 3:   tick_lower = log(2850) / log(1.0001) ≈ 68902
          tick_upper = log(3150) / log(1.0001) ≈ 69566

Step 4:   (For fee 3000, spacing = 60)
          valid_tick_lower = 68880 (rounded to nearest 60)
          valid_tick_upper = 69540 (rounded to nearest 60)

Result:   Liquidity added from $2850 to $3150 per WETH
```

## Usage

### Command Line

```bash
# Basic syntax
amm-trading add-range TOKEN0 TOKEN1 FEE PERCENT_LOWER PERCENT_UPPER AMOUNT0 AMOUNT1

# Examples:

# Symmetric range: -5% to +5%
amm-trading add-range WETH USDT 3000 -0.05 0.05 0.1 300

# Wide symmetric: -20% to +20%
amm-trading add-range WETH USDT 3000 -0.20 0.20 0.1 300

# Tight symmetric: -1% to +1% (concentrated liquidity)
amm-trading add-range WETH USDT 3000 -0.01 0.01 0.1 300

# Below current price: -10% to -1%
amm-trading add-range WETH USDT 3000 -0.10 -0.01 0.1 300

# Above current price: +1% to +10%
amm-trading add-range WETH USDT 3000 0.01 0.10 0.1 300

# Custom slippage (1%)
amm-trading add-range WETH USDT 3000 -0.05 0.05 0.1 300 --slippage 1.0
```

### Python API

```python
from amm_trading.operations import LiquidityManager

manager = LiquidityManager()

# Basic usage
result = manager.add_liquidity_range(
    token0="WETH",
    token1="USDT",
    fee=3000,
    percent_lower=-0.05,  # -5%
    percent_upper=0.05,   # +5%
    amount0=0.1,
    amount1=300,
    slippage_bps=50,
)

# Result includes price information
print(f"Position ID: {result['token_id']}")
print(f"Current price: {result['current_price']:.2f}")
print(f"Price range: {result['price_lower']:.2f} to {result['price_upper']:.2f}")
print(f"Tick range: {result['tick_lower']} to {result['tick_upper']}")
```

## Common Strategies

### 1. Balanced Market Making (-5% to +5%)

**Use Case**: Provide liquidity around current price for fee generation

```bash
amm-trading add-range WETH USDT 3000 -0.05 0.05 1.0 3000
```

**Characteristics:**
- Earns fees in normal market conditions
- Moderate capital efficiency
- Lower impermanent loss risk than narrower ranges

### 2. Concentrated Liquidity (-1% to +1%)

**Use Case**: Maximum capital efficiency in stable/low-volatility markets

```bash
amm-trading add-range WETH USDT 3000 -0.01 0.01 0.5 1500
```

**Characteristics:**
- Highest fee earning potential per unit of capital
- High impermanent loss risk if price moves outside range
- Best for stablecoin pairs or low-volatility periods

### 3. Buy the Dip (-10% to -1%)

**Use Case**: Provide liquidity below current price to "buy the dip"

```bash
amm-trading add-range WETH USDT 3000 -0.10 -0.01 0.2 600
```

**Characteristics:**
- Currently inactive (no fees until price drops)
- Automatically accumulates token0 (WETH) if price falls into range
- Good for accumulating assets you're bullish on

### 4. Take Profits (+1% to +10%)

**Use Case**: Provide liquidity above current price to take profits

```bash
amm-trading add-range WETH USDT 3000 0.01 0.10 0.2 0
```

**Characteristics:**
- Currently inactive (no fees until price rises)
- Automatically sells token0 (WETH) for token1 (USDT) as price rises
- Good for taking profits on appreciated assets

### 5. Wide Range (-50% to +100%)

**Use Case**: Uniswap V2-style passive market making

```bash
amm-trading add-range WETH USDT 3000 -0.50 1.00 0.5 1500
```

**Characteristics:**
- Lower fee generation per unit of capital
- Lower impermanent loss risk
- More passive, "set and forget" approach

## Understanding Percentage Values

### Symmetric Ranges

**Centered around current price:**
- `-0.05 0.05` = -5% to +5% (10% total range)
- `-0.10 0.10` = -10% to +10% (20% total range)
- `-0.20 0.20` = -20% to +20% (40% total range)

### Asymmetric Ranges

**Below current price:**
- `-0.10 -0.01` = -10% to -1% below
- `-0.20 -0.05` = -20% to -5% below
- `-0.50 -0.10` = -50% to -10% below

**Above current price:**
- `0.01 0.10` = +1% to +10% above
- `0.05 0.20` = +5% to +20% above
- `0.10 0.50` = +10% to +50% above

**Mixed (mostly below):**
- `-0.10 0.02` = -10% to +2%
- `-0.15 0.05` = -15% to +5%

**Mixed (mostly above):**
- `-0.02 0.10` = -2% to +10%
- `-0.05 0.15` = -5% to +15%

## Best Practices

### 1. Consider Volatility

**Low volatility (stablecoins):** Tight ranges work well
```bash
amm-trading add-range USDC USDT 100 -0.001 0.001 1000 1000
```

**High volatility (ETH, BTC):** Wider ranges reduce risk
```bash
amm-trading add-range WETH USDT 3000 -0.20 0.20 0.5 1500
```

### 2. Monitor Your Positions

Price can move outside your range, causing:
- Zero fee earning (position becomes inactive)
- 100% position in one token (full conversion)

Use `amm-trading query position <id>` to monitor.

### 3. Rebalance When Needed

If price moves significantly, consider:
```bash
# Migrate to new range
amm-trading migrate <old_position_id> <new_tick_lower> <new_tick_upper>
```

Or use the percentage-based approach:
1. Remove liquidity from old position
2. Add new position with current price ranges

### 4. Start Conservative

If you're new to concentrated liquidity:
1. Start with wider ranges (-10% to +10%)
2. Use smaller amounts to test
3. Observe fee generation and impermanent loss
4. Gradually narrow ranges as you gain experience

## Comparison with Full Range

### Full Range (Uniswap V2 style)
```bash
amm-trading add WETH USDT 3000 -887220 887220 0.1 300
```

### Approximate Full Range with Percentages
```bash
# ~-99% to +1000% (very wide, but not truly infinite)
amm-trading add-range WETH USDT 3000 -0.99 10.0 0.1 300
```

**Note**: Full range positions are still best specified with tick values for exact bounds.

## Output and Saved Data

Results are saved to `results/add_liquidity_<token_id>.json`:

```json
{
  "token_id": 1234567,
  "tx_hash": "0x...",
  "block": 18000000,
  "token0": "WETH",
  "token1": "USDT",
  "tick_lower": 68880,
  "tick_upper": 69540,
  "current_price": 3000.0,
  "price_lower": 2850.0,
  "price_upper": 3150.0,
  "percent_lower": -0.05,
  "percent_upper": 0.05
}
```

## Fee Tiers and Tick Spacing

The function automatically handles tick spacing for each fee tier:

| Fee | Tick Spacing | Use Case |
|-----|--------------|----------|
| 100 | 1 | Stablecoin pairs (very tight ranges possible) |
| 500 | 10 | Correlated assets |
| 3000 | 60 | Most pairs (default) |
| 10000 | 200 | Exotic/volatile pairs |

## Error Handling

### Common Errors

**Invalid range:**
```bash
# percent_lower must be < percent_upper
amm-trading add-range WETH USDT 3000 0.05 -0.05 0.1 300  # ❌ ERROR
```

**Pool doesn't exist:**
```bash
# Make sure the pool exists for the given fee tier
amm-trading add-range TOKEN1 TOKEN2 3000 -0.05 0.05 1 1
```

**Insufficient balance:**
```bash
# Check balances first
amm-trading query balances --address <your_address>
```

## See Also

- [TICKS_AND_PRICES.md](TICKS_AND_PRICES.md) - Understanding the underlying tick math
- [README.md](README.md) - Main documentation
- [example_add_range.py](example_add_range.py) - Working examples

## Summary

The percentage-based range feature makes it easy to:
- ✅ Add liquidity without calculating ticks
- ✅ Implement common strategies quickly
- ✅ Adjust to current market prices automatically
- ✅ Think in intuitive percentage terms

**Quick Reference:**
```bash
# Balanced (most common)
amm-trading add-range WETH USDT 3000 -0.05 0.05 0.1 300

# Concentrated (high fees, high risk)
amm-trading add-range WETH USDT 3000 -0.01 0.01 0.1 300

# Wide (low fees, low risk)
amm-trading add-range WETH USDT 3000 -0.20 0.20 0.1 300
```

