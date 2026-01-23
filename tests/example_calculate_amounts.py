#!/usr/bin/env python3
"""
Example: Calculate Optimal Token Amounts

This example demonstrates how to calculate the exact optimal amounts
of each token needed for a liquidity position BEFORE adding liquidity.

This helps you understand:
1. The exact ratio needed
2. Which token you might have too much/little of
3. Whether the position will be active at current price
"""

from amm_trading.operations import LiquidityManager
from amm_trading import Web3Manager

# Initialize manager (requires RPC connection, but NOT wallet)
# We pass a Web3Manager without signer for read-only operations
web3_manager = Web3Manager(require_signer=False)
manager = LiquidityManager(manager=web3_manager)

print("=" * 70)
print("EXAMPLE 1: Calculate amounts for percentage range")
print("=" * 70)
print("\nScenario: You want to add 0.1 WETH with -5% to +5% range")
print("Question: How much USDT do you need?")

result = manager.calculate_optimal_amounts_range(
    token0="WETH",
    token1="USDT",
    fee=3000,
    percent_lower=-0.05,
    percent_upper=0.05,
    amount0_desired=0.1,  # You have 0.1 WETH
    amount1_desired=None,  # Calculate optimal USDT
)

print(f"\n✓ Answer:")
print(f"  WETH needed: {result['token0']['amount']:.6f}")
print(f"  USDT needed: {result['token1']['amount']:.2f}")
print(f"  Current price: ${result['current_price']:.2f}")
print(f"  Ratio: {result['ratio']}")

print("\n" + "=" * 70)
print("EXAMPLE 2: Calculate the other direction")
print("=" * 70)
print("\nScenario: You have 300 USDT and want to add liquidity")
print("Question: How much WETH do you need?")

result2 = manager.calculate_optimal_amounts_range(
    token0="WETH",
    token1="USDT",
    fee=3000,
    percent_lower=-0.05,
    percent_upper=0.05,
    amount0_desired=None,   # Calculate optimal WETH
    amount1_desired=300,    # You have 300 USDT
)

print(f"\n✓ Answer:")
print(f"  WETH needed: {result2['token0']['amount']:.6f}")
print(f"  USDT needed: {result2['token1']['amount']:.2f}")

print("\n" + "=" * 70)
print("EXAMPLE 3: Position below current price")
print("=" * 70)
print("\nScenario: Add liquidity -10% to -1% below current price")
print("This is a 'buy the dip' strategy")

result3 = manager.calculate_optimal_amounts_range(
    token0="WETH",
    token1="USDT",
    fee=3000,
    percent_lower=-0.10,
    percent_upper=-0.01,
    amount0_desired=0.1,
)

print(f"\n✓ Answer:")
print(f"  WETH needed: {result3['token0']['amount']:.6f}")
print(f"  USDT needed: {result3['token1']['amount']:.2f}")
print(f"  Position type: {result3['position_type']}")

if result3['position_type'] == 'below_range':
    print(f"\n⚠️  This position is BELOW current price")
    print(f"  Only WETH is needed, no USDT required")
    print(f"  Position will become active when price drops below ${result3['price_upper']:.2f}")

print("\n" + "=" * 70)
print("EXAMPLE 4: Position above current price")
print("=" * 70)
print("\nScenario: Add liquidity +1% to +10% above current price")
print("This is a 'take profits' strategy")

result4 = manager.calculate_optimal_amounts_range(
    token0="WETH",
    token1="USDT",
    fee=3000,
    percent_lower=0.01,
    percent_upper=0.10,
    amount1_desired=300,  # Note: using amount1 here
)

print(f"\n✓ Answer:")
print(f"  WETH needed: {result4['token0']['amount']:.6f}")
print(f"  USDT needed: {result4['token1']['amount']:.2f}")
print(f"  Position type: {result4['position_type']}")

if result4['position_type'] == 'above_range':
    print(f"\n⚠️  This position is ABOVE current price")
    print(f"  Only USDT is needed, no WETH required")
    print(f"  Position will become active when price rises above ${result4['price_lower']:.2f}")

print("\n" + "=" * 70)
print("EXAMPLE 5: Using calculated amounts to add liquidity")
print("=" * 70)

# First calculate
result5 = manager.calculate_optimal_amounts_range(
    token0="WETH",
    token1="USDT",
    fee=3000,
    percent_lower=-0.05,
    percent_upper=0.05,
    amount0_desired=0.1,
)

print(f"\nStep 1: Calculate optimal amounts")
print(f"  WETH: {result5['token0']['amount']:.6f}")
print(f"  USDT: {result5['token1']['amount']:.2f}")

print(f"\nStep 2: Use these amounts to add liquidity")
print(f"  (Requires wallet.env)")

# Uncomment to actually add liquidity:
# manager_with_wallet = LiquidityManager(require_signer=True)
# add_result = manager_with_wallet.add_liquidity_range(
#     token0="WETH",
#     token1="USDT",
#     fee=3000,
#     percent_lower=-0.05,
#     percent_upper=0.05,
#     amount0=result5['token0']['amount'],
#     amount1=result5['token1']['amount'],
# )
# print(f"Position created: {add_result['token_id']}")

print("\n" + "=" * 70)
print("Summary: Use calculate_optimal_amounts_range() to:")
print("  1. Know exact amounts needed before adding liquidity")
print("  2. Avoid having leftover tokens")
print("  3. Understand if position will be active at current price")
print("  4. Plan your capital allocation better")
print("=" * 70)

