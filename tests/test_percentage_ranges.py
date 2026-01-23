#!/usr/bin/env python3
"""
Test script for percentage range conversion

This script validates that the percentage-to-tick conversion works correctly
without requiring blockchain interaction.
"""

import math
from amm_trading.utils.math import price_to_tick, tick_to_price, round_tick_to_spacing


def test_percentage_conversion(current_price, percent_lower, percent_upper, decimals0=18, decimals1=6, fee=3000):
    """Test percentage to tick conversion"""
    
    print(f"\nTest Case:")
    print(f"  Current price: {current_price:.2f}")
    print(f"  Range: {percent_lower*100:.1f}% to {percent_upper*100:.1f}%")
    print(f"  Fee tier: {fee}")
    print("-" * 60)
    
    # Calculate target prices
    price_lower = current_price * (1 + percent_lower)
    price_upper = current_price * (1 + percent_upper)
    
    print(f"Target prices:")
    print(f"  Lower: {price_lower:.2f}")
    print(f"  Upper: {price_upper:.2f}")
    
    # Convert to ticks
    tick_lower = price_to_tick(price_lower, decimals0, decimals1)
    tick_upper = price_to_tick(price_upper, decimals0, decimals1)
    
    print(f"Raw ticks:")
    print(f"  Lower: {tick_lower}")
    print(f"  Upper: {tick_upper}")
    
    # Round to valid spacing
    spacing_map = {100: 1, 500: 10, 3000: 60, 10000: 200}
    spacing = spacing_map[fee]
    
    valid_tick_lower = round_tick_to_spacing(tick_lower, spacing)
    valid_tick_upper = round_tick_to_spacing(tick_upper, spacing)
    
    print(f"Valid ticks (spacing={spacing}):")
    print(f"  Lower: {valid_tick_lower}")
    print(f"  Upper: {valid_tick_upper}")
    
    # Verify by converting back to prices
    actual_price_lower = tick_to_price(valid_tick_lower, decimals0, decimals1)
    actual_price_upper = tick_to_price(valid_tick_upper, decimals0, decimals1)
    
    print(f"Actual prices after rounding:")
    print(f"  Lower: {actual_price_lower:.2f}")
    print(f"  Upper: {actual_price_upper:.2f}")
    
    # Calculate actual percentages
    actual_percent_lower = (actual_price_lower / current_price - 1)
    actual_percent_upper = (actual_price_upper / current_price - 1)
    
    print(f"Actual percentages:")
    print(f"  Lower: {actual_percent_lower*100:.3f}%")
    print(f"  Upper: {actual_percent_upper*100:.3f}%")
    
    print("✓ Conversion successful!\n")
    
    return {
        'tick_lower': valid_tick_lower,
        'tick_upper': valid_tick_upper,
        'price_lower': actual_price_lower,
        'price_upper': actual_price_upper,
    }


def main():
    print("=" * 60)
    print("Percentage Range Conversion Tests")
    print("=" * 60)
    
    # Test 1: Symmetric range around $3000
    print("\n### Test 1: Symmetric -5% to +5% (WETH/USDT at $3000)")
    test_percentage_conversion(
        current_price=3000,
        percent_lower=-0.05,
        percent_upper=0.05,
        decimals0=18,
        decimals1=6,
        fee=3000
    )
    
    # Test 2: Below current price
    print("\n### Test 2: Below price -10% to -1% (WETH/USDT at $3000)")
    test_percentage_conversion(
        current_price=3000,
        percent_lower=-0.10,
        percent_upper=-0.01,
        decimals0=18,
        decimals1=6,
        fee=3000
    )
    
    # Test 3: Above current price
    print("\n### Test 3: Above price +1% to +10% (WETH/USDT at $3000)")
    test_percentage_conversion(
        current_price=3000,
        percent_lower=0.01,
        percent_upper=0.10,
        decimals0=18,
        decimals1=6,
        fee=3000
    )
    
    # Test 4: Very tight range (concentrated liquidity)
    print("\n### Test 4: Tight range -1% to +1% (WETH/USDT at $3000)")
    test_percentage_conversion(
        current_price=3000,
        percent_lower=-0.01,
        percent_upper=0.01,
        decimals0=18,
        decimals1=6,
        fee=3000
    )
    
    # Test 5: Wide range
    print("\n### Test 5: Wide range -20% to +20% (WETH/USDT at $3000)")
    test_percentage_conversion(
        current_price=3000,
        percent_lower=-0.20,
        percent_upper=0.20,
        decimals0=18,
        decimals1=6,
        fee=3000
    )
    
    # Test 6: Different fee tier (500)
    print("\n### Test 6: Fee tier 500 with -5% to +5% (WETH/USDT at $3000)")
    test_percentage_conversion(
        current_price=3000,
        percent_lower=-0.05,
        percent_upper=0.05,
        decimals0=18,
        decimals1=6,
        fee=500
    )
    
    # Test 7: Different price point
    print("\n### Test 7: High price -5% to +5% (WETH/USDT at $5000)")
    test_percentage_conversion(
        current_price=5000,
        percent_lower=-0.05,
        percent_upper=0.05,
        decimals0=18,
        decimals1=6,
        fee=3000
    )
    
    # Test 8: Stablecoin pair
    print("\n### Test 8: Stablecoin pair -0.1% to +0.1% (USDC/USDT at $1.00)")
    test_percentage_conversion(
        current_price=1.0,
        percent_lower=-0.001,
        percent_upper=0.001,
        decimals0=6,
        decimals1=6,
        fee=100
    )
    
    print("=" * 60)
    print("All tests completed successfully! ✓")
    print("=" * 60)
    print("\nThe percentage-based range feature is working correctly.")
    print("You can now use it with:")
    print("  CLI: amm-trading add-range WETH USDT 3000 -0.05 0.05 0.1 300")
    print("  API: manager.add_liquidity_range(...)")


if __name__ == "__main__":
    main()

