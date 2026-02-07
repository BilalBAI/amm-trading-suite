"""
Math utilities for Uniswap V4 calculations.

V4 uses the same concentrated liquidity math as V3.
This module re-exports V3 math functions for V4 use.
"""

# V4 uses the same math as V3 for concentrated liquidity
from ..uniswap_v3.math import (
    Q96,
    tick_to_price,
    price_to_tick,
    tick_to_sqrt_price,
    sqrt_price_x96_to_price,
    round_tick_to_spacing,
    get_amounts_from_liquidity,
    calculate_slippage_amounts,
)


def calculate_liquidity_from_amounts(
    sqrt_price_x96: int,
    tick_lower: int,
    tick_upper: int,
    amount0: int,
    amount1: int,
) -> int:
    """
    Calculate liquidity from token amounts.

    This is needed for V4's MINT_POSITION which requires liquidity amount.

    Args:
        sqrt_price_x96: Current sqrt price in X96 format
        tick_lower: Lower tick of the range
        tick_upper: Upper tick of the range
        amount0: Amount of token0 in wei
        amount1: Amount of token1 in wei

    Returns:
        Liquidity amount
    """
    sqrt_price_lower = tick_to_sqrt_price(tick_lower) * Q96
    sqrt_price_upper = tick_to_sqrt_price(tick_upper) * Q96
    sqrt_price_current = sqrt_price_x96

    # Clamp current price to range
    if sqrt_price_current < sqrt_price_lower:
        sqrt_price_current = sqrt_price_lower
    elif sqrt_price_current > sqrt_price_upper:
        sqrt_price_current = sqrt_price_upper

    # Calculate liquidity from each token
    liquidity0 = 0
    liquidity1 = 0

    if amount0 > 0 and sqrt_price_current < sqrt_price_upper:
        # L = amount0 * sqrt(P_current) * sqrt(P_upper) / (sqrt(P_upper) - sqrt(P_current))
        liquidity0 = (
            amount0
            * sqrt_price_current
            * sqrt_price_upper
            // ((sqrt_price_upper - sqrt_price_current) * Q96)
        )

    if amount1 > 0 and sqrt_price_current > sqrt_price_lower:
        # L = amount1 / (sqrt(P_current) - sqrt(P_lower))
        liquidity1 = amount1 * Q96 // (sqrt_price_current - sqrt_price_lower)

    # Return the minimum (limiting factor)
    if liquidity0 == 0:
        return liquidity1
    if liquidity1 == 0:
        return liquidity0
    return min(liquidity0, liquidity1)


__all__ = [
    "Q96",
    "tick_to_price",
    "price_to_tick",
    "tick_to_sqrt_price",
    "sqrt_price_x96_to_price",
    "round_tick_to_spacing",
    "get_amounts_from_liquidity",
    "calculate_slippage_amounts",
    "calculate_liquidity_from_amounts",
]
