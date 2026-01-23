# Changelog: Percentage-Based Range Feature

## Summary

Added a new feature to add liquidity using **percentage ranges** around the current pool price, making it easier and more intuitive to create Uniswap V3 positions.

## What's New

### 1. New Method: `add_liquidity_range()`

**Location**: `amm_trading/operations/liquidity.py`

Added to the `LiquidityManager` class, this method accepts percentage-based ranges instead of absolute tick values.

**Signature:**
```python
def add_liquidity_range(
    self,
    token0,
    token1,
    fee,
    percent_lower,      # NEW: e.g., -0.05 for -5%
    percent_upper,      # NEW: e.g., 0.05 for +5%
    amount0,
    amount1,
    slippage_bps=50,
)
```

**Key Features:**
- Automatically fetches current pool price
- Converts percentage ranges to prices
- Converts prices to ticks using the formula: `tick = log(price) / log(1.0001)`
- Rounds ticks to valid tick spacing for the fee tier
- Calls the existing `add_liquidity()` method
- Returns result with both tick and price information

### 2. New CLI Command: `add-range`

**Location**: `amm_trading/cli/main.py`

**Syntax:**
```bash
amm-trading add-range TOKEN0 TOKEN1 FEE PERCENT_LOWER PERCENT_UPPER AMOUNT0 AMOUNT1 [--slippage]
```

**Examples:**
```bash
# Symmetric: -5% to +5% around current price
amm-trading add-range WETH USDT 3000 -0.05 0.05 0.1 300

# Below current: -10% to -1%
amm-trading add-range WETH USDT 3000 -0.10 -0.01 0.1 300

# Above current: +1% to +10%
amm-trading add-range WETH USDT 3000 0.01 0.10 0.1 300
```

### 3. Documentation

**New Files:**
- `PERCENTAGE_RANGES.md` - Comprehensive guide with examples, strategies, and best practices
- `example_add_range.py` - Working Python examples demonstrating the feature
- `test_percentage_ranges.py` - Test script validating the conversion logic

**Updated Files:**
- `README.md` - Added examples and documentation references

## Technical Details

### Implementation

1. **Pool Price Fetching**:
   - Uses Uniswap V3 Factory to locate the pool
   - Creates a Pool contract instance
   - Calls `pool.get_price()` to fetch current price

2. **Price Calculation**:
   ```python
   price_lower = current_price * (1 + percent_lower)
   price_upper = current_price * (1 + percent_upper)
   ```

3. **Tick Conversion**:
   - Uses existing `price_to_tick()` utility
   - Formula: `tick = int(log(price) / log(1.0001))`

4. **Tick Rounding**:
   - Uses existing `round_tick_to_spacing()` utility
   - Respects fee tier tick spacing (1, 10, 60, or 200)

5. **Error Handling**:
   - Validates percentage ranges (lower < upper)
   - Checks if pool exists
   - Maintains all existing error checking from `add_liquidity()`

### Dependencies

No new external dependencies added. Uses existing utilities:
- `price_to_tick()` from `utils/math.py`
- `Pool` from `contracts/pool.py`
- `ERC20` from `contracts/erc20.py`

## Usage Examples

### Python API

```python
from amm_trading.operations import LiquidityManager

manager = LiquidityManager()

# Simple usage
result = manager.add_liquidity_range(
    token0="WETH",
    token1="USDT",
    fee=3000,
    percent_lower=-0.05,
    percent_upper=0.05,
    amount0=0.1,
    amount1=300,
)

print(f"Position {result['token_id']}")
print(f"Range: {result['price_lower']:.2f} to {result['price_upper']:.2f}")
```

### Command Line

```bash
# Balanced strategy
amm-trading add-range WETH USDT 3000 -0.05 0.05 0.1 300

# Concentrated liquidity
amm-trading add-range WETH USDT 3000 -0.01 0.01 0.1 300

# Wide range
amm-trading add-range WETH USDT 3000 -0.20 0.20 0.1 300
```

## Testing

Run the validation script:
```bash
cd amm-tools
python test_percentage_ranges.py
```

This tests the conversion logic for:
- Symmetric ranges
- Asymmetric ranges (above/below)
- Different fee tiers
- Different price points
- Stablecoin pairs

All tests pass successfully ✓

## Benefits

### For Users
1. **Intuitive**: Think in percentages, not ticks
2. **Faster**: No manual tick calculation needed
3. **Flexible**: Easy to implement trading strategies
4. **Dynamic**: Automatically adjusts to current market price

### For Developers
1. **Clean API**: Simple percentage parameters
2. **Backward Compatible**: Existing `add_liquidity()` unchanged
3. **Well Tested**: Validation script included
4. **Documented**: Comprehensive guides and examples

## Common Use Cases

| Strategy | Range | Example |
|----------|-------|---------|
| Balanced market making | ±5% | `-0.05 0.05` |
| Concentrated liquidity | ±1% | `-0.01 0.01` |
| Buy the dip | -10% to -1% | `-0.10 -0.01` |
| Take profits | +1% to +10% | `0.01 0.10` |
| Wide passive | -20% to +20% | `-0.20 0.20` |

## Files Modified

### Core Implementation
- `amm_trading/operations/liquidity.py` - Added `add_liquidity_range()` method
- `amm_trading/cli/main.py` - Added `add-range` command and CLI handler

### Documentation
- `README.md` - Updated with examples and references
- `PERCENTAGE_RANGES.md` - NEW: Complete guide
- `example_add_range.py` - NEW: Working examples
- `test_percentage_ranges.py` - NEW: Validation tests
- `CHANGELOG_PERCENTAGE_RANGES.md` - NEW: This file

## Notes

- Tick rounding may cause actual percentages to differ slightly from requested (due to tick spacing)
- The feature respects all existing safety checks (balance, approvals, etc.)
- Output includes both percentage and tick information for transparency
- Full range positions should still use tick-based `add` command for exact bounds

## Future Enhancements

Potential improvements for future versions:
1. Add `migrate-range` command (migrate using percentages)
2. Support for "width" parameter (e.g., `--width 0.10` for ±5%)
3. Preset strategies (e.g., `--strategy balanced`)
4. Real-time fee APY estimation for the range

## Version

This feature was added on January 23, 2026.

Compatible with:
- Python 3.8+
- web3.py 6.0.0+
- All existing amm-trading functionality

