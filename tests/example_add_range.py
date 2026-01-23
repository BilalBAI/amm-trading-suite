#!/usr/bin/env python3
"""
Example: Add liquidity using percentage ranges

This example demonstrates the new add_liquidity_range() method which allows
you to specify liquidity ranges as percentages around the current pool price,
rather than as absolute tick values.
"""

from amm_trading.operations import LiquidityManager

# Initialize the manager (requires wallet.env with PRIVATE_KEY)
manager = LiquidityManager()

# Example 1: Symmetric range around current price
# This adds liquidity from -5% to +5% around the current WETH/USDT price
print("Example 1: Symmetric range (-5% to +5%)")
print("=" * 60)

result = manager.add_liquidity_range(
    token0="WETH",
    token1="USDT",
    fee=3000,           # 0.3% fee tier
    percent_lower=-0.05,  # -5% below current price
    percent_upper=0.05,   # +5% above current price
    amount0=0.1,         # 0.1 WETH
    amount1=300,         # 300 USDT
    slippage_bps=50,     # 0.5% slippage tolerance
)

print(f"\n✓ Position created!")
print(f"  Token ID: {result['token_id']}")
print(f"  Transaction: {result['receipt'].transactionHash.hex()}")
print(f"  Current price: {result['current_price']:.2f} {result['token1']}/{result['token0']}")
print(f"  Price range: {result['price_lower']:.2f} to {result['price_upper']:.2f}")
print(f"  Tick range: {result['tick_lower']} to {result['tick_upper']}")

# Example 2: Asymmetric range below current price
# Useful for "buy the dip" strategies
print("\n\nExample 2: Asymmetric range below current price (-10% to -1%)")
print("=" * 60)
print("This strategy provides liquidity only when price drops")

result2 = manager.add_liquidity_range(
    token0="WETH",
    token1="USDT",
    fee=3000,
    percent_lower=-0.10,  # -10% below current price
    percent_upper=-0.01,  # -1% below current price
    amount0=0.05,
    amount1=150,
    slippage_bps=50,
)

print(f"\n✓ Position created!")
print(f"  Token ID: {result2['token_id']}")
print(f"  Price range: {result2['price_lower']:.2f} to {result2['price_upper']:.2f}")

# Example 3: Asymmetric range above current price
# Useful for taking profits as price rises
print("\n\nExample 3: Asymmetric range above current price (+1% to +10%)")
print("=" * 60)
print("This strategy provides liquidity only when price rises")

result3 = manager.add_liquidity_range(
    token0="WETH",
    token1="USDT",
    fee=3000,
    percent_lower=0.01,   # +1% above current price
    percent_upper=0.10,   # +10% above current price
    amount0=0.05,
    amount1=150,
    slippage_bps=50,
)

print(f"\n✓ Position created!")
print(f"  Token ID: {result3['token_id']}")
print(f"  Price range: {result3['price_lower']:.2f} to {result3['price_upper']:.2f}")

print("\n" + "=" * 60)
print("All positions created successfully!")
print("=" * 60)

