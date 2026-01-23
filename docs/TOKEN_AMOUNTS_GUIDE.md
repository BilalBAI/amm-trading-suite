# Token Amounts Guide: Understanding Liquidity Ratios in Uniswap V3

## ❓ The Question: Can I Input Any Amounts?

**Short Answer:** No, there's an optimal ratio based on:
1. Current pool price
2. Your tick range (price range)
3. Where the current price sits within your range

## 🎯 The Problem

When you add liquidity to Uniswap V3, you can't just specify any arbitrary amounts. The protocol calculates an **optimal ratio** based on the current price and your chosen range.

### Example Scenario

Let's say WETH is trading at $3000:

```bash
# You try to add:
amm-trading add-range WETH USDT 3000 -0.05 0.05 0.1 300
#                                                   ^^^  ^^^
#                                            0.1 WETH  300 USDT
```

**What might happen:**
- Optimal ratio might need: `0.1 WETH` and `285 USDT`
- Result: **15 USDT stays in your wallet unused**
- Or worse: Transaction fails due to slippage if ratio is way off

## ✅ The Solution: Calculate Optimal Amounts First

We've added tools to calculate the **exact optimal amounts** before adding liquidity.

---

## 📊 How Token Ratios Work

### Case 1: Current Price is IN RANGE

When the current price is within your tick range, you need **BOTH tokens** in a specific ratio.

**Example:**
- Current price: $3000 per WETH
- Your range: -5% to +5% ($2850 to $3150)
- Current price is IN this range ✓

**Optimal ratio depends on:**
```
ratio = f(current_price, tick_lower, tick_upper, pool_math)
```

For a -5% to +5% range at $3000:
- If you provide 0.1 WETH → You need ~285 USDT
- If you provide 300 USDT → You need ~0.105 WETH

### Case 2: Current Price is BELOW RANGE

When current price is below your range, you need **ONLY token0** (the "left" token).

**Example:**
- Current price: $3000 per WETH
- Your range: +10% to +20% ($3300 to $3600)
- Current price is BELOW this range

**Result:**
- You need: **WETH only** (token0)
- You need: **0 USDT** (token1)
- Position is currently **inactive** (earns no fees until price rises)

### Case 3: Current Price is ABOVE RANGE

When current price is above your range, you need **ONLY token1** (the "right" token).

**Example:**
- Current price: $3000 per WETH
- Your range: -20% to -10% ($2400 to $2700)
- Current price is ABOVE this range

**Result:**
- You need: **0 WETH** (token0)
- You need: **USDT only** (token1)
- Position is currently **inactive** (earns no fees until price drops)

---

## 🛠️ Using the Calculate Tools

### Method 1: Python API

```python
from amm_trading.operations import LiquidityManager
from amm_trading import Web3Manager

# Initialize (no wallet needed for calculation)
web3_manager = Web3Manager(require_signer=False)
manager = LiquidityManager(manager=web3_manager)

# Calculate optimal amounts
result = manager.calculate_optimal_amounts_range(
    token0="WETH",
    token1="USDT",
    fee=3000,
    percent_lower=-0.05,
    percent_upper=0.05,
    amount0_desired=0.1,  # I have 0.1 WETH
    amount1_desired=None,  # Calculate optimal USDT
)

print(f"WETH needed: {result['token0']['amount']}")
print(f"USDT needed: {result['token1']['amount']}")
print(f"Current price: ${result['current_price']:.2f}")
print(f"Position type: {result['position_type']}")
```

### Method 2: Command Line

```bash
# Calculate using percentage range
amm-trading calculate amounts-range WETH USDT 3000 -0.05 0.05 --amount0 0.1

# Or calculate with tick range
amm-trading calculate amounts WETH USDT 3000 -196800 -195780 --amount0 0.1
```

**Output:**
```
📊 POSITION DETAILS
  Pool: WETH/USDT (0.30% fee)
  Current Price: 3000.000000 USDT/WETH
  Price Range: 2850.000000 to 3150.000000
  Position Status: In Range

💰 OPTIMAL AMOUNTS
  WETH: 0.100000
  USDT: 285.500000

📈 RATIO
  1 WETH = 3000.00 USDT
```

---

## 📝 Complete Workflow

### Step 1: Calculate Optimal Amounts

```bash
# I have 0.1 WETH, how much USDT do I need?
amm-trading calculate amounts-range WETH USDT 3000 -0.05 0.05 --amount0 0.1
```

Output shows you need: `0.1 WETH` and `~285 USDT`

### Step 2: Add Liquidity with Optimal Amounts

```bash
# Use the calculated amounts
amm-trading add-range WETH USDT 3000 -0.05 0.05 0.1 285
```

Now both tokens will be fully utilized with minimal leftover!

---

## 💡 Pro Tips

### Tip 1: Always Calculate First

```python
# 1. Calculate first
result = manager.calculate_optimal_amounts_range(
    token0="WETH", token1="USDT", fee=3000,
    percent_lower=-0.05, percent_upper=0.05,
    amount0_desired=0.1,
)

# 2. Check if you have enough of both tokens
print(f"Need: {result['token0']['amount']} WETH")
print(f"Need: {result['token1']['amount']} USDT")

# 3. Add liquidity with optimal amounts
manager_with_wallet = LiquidityManager()  # Requires wallet.env
manager_with_wallet.add_liquidity_range(
    token0="WETH", token1="USDT", fee=3000,
    percent_lower=-0.05, percent_upper=0.05,
    amount0=result['token0']['amount'],
    amount1=result['token1']['amount'],
)
```

### Tip 2: Check Position Type

```python
result = manager.calculate_optimal_amounts_range(...)

if result['position_type'] == 'below_range':
    print("⚠️ Position will be inactive at current price")
    print(f"Only {result['token0']['symbol']} is needed")
elif result['position_type'] == 'above_range':
    print("⚠️ Position will be inactive at current price")
    print(f"Only {result['token1']['symbol']} is needed")
else:
    print("✓ Position will be active and earn fees immediately")
```

### Tip 3: Calculate Both Ways

```python
# Check if you have enough WETH
result1 = manager.calculate_optimal_amounts_range(
    "WETH", "USDT", 3000, -0.05, 0.05,
    amount0_desired=0.1,  # Based on WETH
)

# Check if you have enough USDT  
result2 = manager.calculate_optimal_amounts_range(
    "WETH", "USDT", 3000, -0.05, 0.05,
    amount1_desired=300,  # Based on USDT
)

# Use whichever fits your available balances better
```

---

## 🧮 The Math Behind It

### For "In Range" Positions

The optimal ratio is calculated using Uniswap V3's liquidity math:

```
sqrt_price = current_price^0.5
sqrt_lower = price_lower^0.5
sqrt_upper = price_upper^0.5

Given amount0:
  amount1 = amount0 * (sqrt_price - sqrt_lower) / (1/sqrt_price - 1/sqrt_upper)

Given amount1:
  amount0 = amount1 * (1/sqrt_price - 1/sqrt_upper) / (sqrt_price - sqrt_lower)
```

### For "Out of Range" Positions

- **Below range**: Only token0 needed, amount1 = 0
- **Above range**: Only token1 needed, amount0 = 0

---

## 🎯 Common Scenarios

### Scenario 1: I have X of token0, need token1

```bash
amm-trading calculate amounts-range WETH USDT 3000 -0.05 0.05 --amount0 0.5
```

**Use case:** You have WETH and want to know how much USDT to buy.

### Scenario 2: I have Y of token1, need token0

```bash
amm-trading calculate amounts-range WETH USDT 3000 -0.05 0.05 --amount1 1500
```

**Use case:** You have USDT and want to know how much WETH to buy.

### Scenario 3: Below current price (buy the dip)

```bash
amm-trading calculate amounts-range WETH USDT 3000 -0.10 -0.01 --amount0 1.0
```

**Result:** Only WETH needed, USDT = 0 (position inactive until price drops)

### Scenario 4: Above current price (take profits)

```bash
amm-trading calculate amounts-range WETH USDT 3000 0.01 0.10 --amount1 3000
```

**Result:** Only USDT needed, WETH = 0 (position inactive until price rises)

---

## 📊 Comparison Table

| Your Input | Current Price Position | Token0 Needed | Token1 Needed | Position Active? |
|------------|----------------------|---------------|---------------|------------------|
| -5% to +5% | In range | ✓ Yes | ✓ Yes | ✓ Yes |
| -10% to -1% | Below range | ✓ Yes | ✗ No | ✗ No |
| +1% to +10% | Above range | ✗ No | ✓ Yes | ✗ No |
| -20% to +20% | In range | ✓ Yes | ✓ Yes | ✓ Yes |

---

## 🚫 Common Mistakes

### Mistake 1: Providing Unbalanced Amounts

```bash
# BAD: Random amounts that don't match optimal ratio
amm-trading add-range WETH USDT 3000 -0.05 0.05 0.1 500
#                                                       ^^^ Too much USDT!
```

**Result:** 200+ USDT stays unused in wallet, wasted gas on approval.

**FIX:**
```bash
# GOOD: Calculate first
amm-trading calculate amounts-range WETH USDT 3000 -0.05 0.05 --amount0 0.1
# Shows you need ~285 USDT

# Then use optimal amount
amm-trading add-range WETH USDT 3000 -0.05 0.05 0.1 285
```

### Mistake 2: Not Checking Position Type

```bash
# BAD: Providing both tokens for out-of-range position
amm-trading add-range WETH USDT 3000 -0.10 -0.01 0.1 300
#                                                       ^^^ Not needed!
```

**Result:** If position is below current price, USDT won't be used.

**FIX:**
```bash
# Calculate first to check position type
amm-trading calculate amounts-range WETH USDT 3000 -0.10 -0.01 --amount0 0.1
# Shows: position_type = "below_range", USDT = 0

# Only provide WETH
amm-trading add-range WETH USDT 3000 -0.10 -0.01 0.1 0
```

---

## 🎓 Advanced: Adjusting for Slippage

The `add_liquidity` functions use "desired" and "minimum" amounts:

```python
# Internally, the code does:
amount0_min = amount0_desired * (1 - slippage/10000)
amount1_min = amount1_desired * (1 - slippage/10000)
```

This means:
- Uniswap will use UP TO your desired amounts
- But not less than your minimum amounts
- If it can't meet minimum, transaction reverts

**Default slippage:** 0.5% (50 basis points)

---

## 📚 Related Documentation

- [PERCENTAGE_RANGES.md](PERCENTAGE_RANGES.md) - Using percentage ranges
- [TICKS_AND_PRICES.md](TICKS_AND_PRICES.md) - Understanding ticks and prices
- [example_calculate_amounts.py](example_calculate_amounts.py) - Working examples

---

## 🎯 Summary

**Key Takeaways:**

1. ❌ **Can't use arbitrary amounts** - there's an optimal ratio
2. ✅ **Use calculate tools** to find optimal amounts before adding liquidity
3. 📊 **Ratio depends on** current price and your tick range
4. 🎯 **Position type matters** (in range, below range, above range)
5. 💡 **Always calculate first** to avoid wasted tokens

**Quick Commands:**

```bash
# Calculate optimal amounts
amm-trading calculate amounts-range WETH USDT 3000 -0.05 0.05 --amount0 0.1

# Then add liquidity with optimal amounts
amm-trading add-range WETH USDT 3000 -0.05 0.05 <calculated_amount0> <calculated_amount1>
```

---

**Now you know exactly how much of each token you need!** 🎉

