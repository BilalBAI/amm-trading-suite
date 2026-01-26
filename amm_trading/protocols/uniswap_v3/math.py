"""Math utilities for Uniswap V3 calculations"""

import math

Q96 = 2 ** 96


def tick_to_price(tick, decimals0, decimals1):
    """
    Convert tick to human-readable price.

    Args:
        tick: Uniswap V3 tick value
        decimals0: Token0 decimals
        decimals1: Token1 decimals

    Returns:
        Price as token1/token0
    """
    return (1.0001 ** tick) * (10 ** decimals0) / (10 ** decimals1)


def price_to_tick(price, decimals0, decimals1):
    """
    Convert price to nearest tick.

    Args:
        price: Price as token1/token0
        decimals0: Token0 decimals
        decimals1: Token1 decimals

    Returns:
        Tick value (not rounded to spacing)
    """
    adjusted_price = price * (10 ** decimals1) / (10 ** decimals0)
    return int(math.log(adjusted_price) / math.log(1.0001))


def tick_to_sqrt_price(tick):
    """Convert tick to sqrt price (not X96 format)"""
    return 1.0001 ** (tick / 2)


def sqrt_price_x96_to_price(sqrt_price_x96, decimals0, decimals1):
    """Convert sqrtPriceX96 to human-readable price"""
    price = (sqrt_price_x96 / Q96) ** 2
    return price * (10 ** decimals0) / (10 ** decimals1)


def round_tick_to_spacing(tick, spacing):
    """
    Round tick to valid tick for given spacing.

    Args:
        tick: Raw tick value
        spacing: Tick spacing for fee tier

    Returns:
        Valid tick aligned to spacing
    """
    if tick >= 0:
        return (tick // spacing) * spacing
    else:
        return math.floor(tick / spacing) * spacing


def get_amounts_from_liquidity(liquidity, sqrt_price_x96, tick, tick_lower, tick_upper, decimals0, decimals1):
    """
    Calculate token amounts from liquidity.

    Args:
        liquidity: Position liquidity
        sqrt_price_x96: Current sqrt price (X96 format)
        tick: Current tick
        tick_lower: Position lower tick
        tick_upper: Position upper tick
        decimals0: Token0 decimals
        decimals1: Token1 decimals

    Returns:
        (amount0, amount1) in human-readable format
    """
    sqrt_pl = tick_to_sqrt_price(tick_lower)
    sqrt_pu = tick_to_sqrt_price(tick_upper)

    # Determine current sqrt price based on range
    if tick < tick_lower:
        sqrt_pc = sqrt_pl
    elif tick > tick_upper:
        sqrt_pc = sqrt_pu
    else:
        sqrt_pc = sqrt_price_x96 / Q96

    # Calculate amounts based on position relative to current price
    if tick < tick_lower:
        # Price below range: all token0
        amount0 = liquidity * (1 / sqrt_pl - 1 / sqrt_pu) / (10 ** decimals0)
        amount1 = 0
    elif tick > tick_upper:
        # Price above range: all token1
        amount0 = 0
        amount1 = liquidity * (sqrt_pu - sqrt_pl) / (10 ** decimals1)
    else:
        # Price in range: mix of both
        amount0 = liquidity * (1 / sqrt_pc - 1 / sqrt_pu) / (10 ** decimals0)
        amount1 = liquidity * (sqrt_pc - sqrt_pl) / (10 ** decimals1)

    return amount0, amount1


def calculate_slippage_amounts(amount0, amount1, slippage_bps):
    """
    Calculate minimum amounts with slippage protection.

    Args:
        amount0: Desired amount0 in wei
        amount1: Desired amount1 in wei
        slippage_bps: Slippage in basis points (50 = 0.5%)

    Returns:
        (amount0_min, amount1_min) in wei
    """
    multiplier = (10000 - slippage_bps) / 10000
    return int(amount0 * multiplier), int(amount1 * multiplier)
