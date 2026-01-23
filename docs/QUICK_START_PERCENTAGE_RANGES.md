# Quick Start: Percentage-Based Ranges

## 🎯 What Is This?

A new, easier way to add liquidity to Uniswap V3 pools using **percentages** instead of tick values.

## ⚡ Quick Examples

### Before (tick-based):
```bash
# You had to calculate ticks manually
amm-trading add WETH USDT 3000 -887220 887220 0.1 300
```

### Now (percentage-based):
```bash
# Just specify percentage range around current price
amm-trading add-range WETH USDT 3000 -0.05 0.05 0.1 300
```

## 🚀 Get Started in 30 Seconds

### 1. Command Line

```bash
# Balanced strategy: -5% to +5% around current price
amm-trading add-range WETH USDT 3000 -0.05 0.05 0.1 300
```

### 2. Python

```python
from amm_trading.operations import LiquidityManager

manager = LiquidityManager()

result = manager.add_liquidity_range(
    token0="WETH",
    token1="USDT",
    fee=3000,
    percent_lower=-0.05,  # -5%
    percent_upper=0.05,   # +5%
    amount0=0.1,
    amount1=300,
)

print(f"Position ID: {result['token_id']}")
```

## 📊 Common Strategies

### Balanced Market Making
```bash
amm-trading add-range WETH USDT 3000 -0.05 0.05 1.0 3000
```
Good for: Earning fees in normal conditions

### Concentrated Liquidity
```bash
amm-trading add-range WETH USDT 3000 -0.01 0.01 0.5 1500
```
Good for: Maximum fees per dollar (higher risk)

### Buy the Dip
```bash
amm-trading add-range WETH USDT 3000 -0.10 -0.01 0.2 600
```
Good for: Accumulating assets when price drops

### Take Profits
```bash
amm-trading add-range WETH USDT 3000 0.01 0.10 0.2 0
```
Good for: Selling as price rises

### Wide Range (Safe)
```bash
amm-trading add-range WETH USDT 3000 -0.20 0.20 0.5 1500
```
Good for: Lower risk, passive approach

## 💡 Understanding Percentages

| Input | Meaning |
|-------|---------|
| `-0.05 0.05` | -5% to +5% (symmetric) |
| `-0.10 -0.01` | -10% to -1% (below current price) |
| `0.01 0.10` | +1% to +10% (above current price) |
| `-0.01 0.01` | -1% to +1% (tight range) |
| `-0.20 0.20` | -20% to +20% (wide range) |

## 🎓 Full Documentation

- **[PERCENTAGE_RANGES.md](PERCENTAGE_RANGES.md)** - Complete guide with strategies
- **[example_add_range.py](example_add_range.py)** - Working Python examples
- **[test_percentage_ranges.py](test_percentage_ranges.py)** - Test the feature

## ✅ Test It

```bash
# Run tests (no blockchain needed)
cd amm-tools
python test_percentage_ranges.py
```

## 🔥 Why Use This?

✓ **Intuitive** - Think in percentages, not ticks  
✓ **Fast** - No manual calculation needed  
✓ **Dynamic** - Adjusts to current price automatically  
✓ **Flexible** - Easy to implement strategies  

## ❓ FAQ

**Q: Can I still use the old tick-based method?**  
A: Yes! The old `add` command works exactly as before.

**Q: Will this work with any token pair?**  
A: Yes, as long as a Uniswap V3 pool exists for that pair and fee tier.

**Q: What if the price moves?**  
A: The range is calculated when you run the command, based on the current pool price at that moment.

**Q: Why is my actual range slightly different?**  
A: Due to tick spacing requirements. The system rounds to the nearest valid tick. This is documented in detail in PERCENTAGE_RANGES.md.

## 🛠️ Need Help?

1. Read [PERCENTAGE_RANGES.md](PERCENTAGE_RANGES.md) for detailed explanations
2. Run `python example_add_range.py` for working examples
3. Run `python test_percentage_ranges.py` to validate the feature

## 📝 Syntax Reference

### CLI
```bash
amm-trading add-range <TOKEN0> <TOKEN1> <FEE> <PERCENT_LOWER> <PERCENT_UPPER> <AMOUNT0> <AMOUNT1> [--slippage SLIPPAGE]
```

### Python
```python
manager.add_liquidity_range(
    token0=str,           # Token symbol or address
    token1=str,           # Token symbol or address
    fee=int,              # 100, 500, 3000, or 10000
    percent_lower=float,  # e.g., -0.05
    percent_upper=float,  # e.g., 0.05
    amount0=float,        # Human-readable amount
    amount1=float,        # Human-readable amount
    slippage_bps=int,     # Optional, default 50 (0.5%)
)
```

---

**Happy trading! 🦄**

