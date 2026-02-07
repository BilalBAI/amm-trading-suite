"""V4 action encoding for Position Manager operations"""

from typing import List, Tuple
from eth_abi import encode
from .types import Actions, PoolKey, ADDRESS_ZERO


def encode_pool_key(pool_key: PoolKey) -> bytes:
    """Encode a PoolKey struct for ABI encoding"""
    return encode(
        ["address", "address", "uint24", "int24", "address"],
        [
            pool_key.currency0,
            pool_key.currency1,
            pool_key.fee,
            pool_key.tick_spacing,
            pool_key.hooks,
        ],
    )


def encode_mint_position(
    pool_key: PoolKey,
    tick_lower: int,
    tick_upper: int,
    liquidity: int,
    amount0_max: int,
    amount1_max: int,
    recipient: str,
    hook_data: bytes = b"",
) -> Tuple[bytes, List[bytes]]:
    """
    Encode MINT_POSITION + SETTLE_PAIR actions for creating a new position.

    V4's Position Manager uses an encoded action system where:
    1. MINT_POSITION creates the position and calculates required tokens
    2. SETTLE_PAIR handles the token transfers

    Args:
        pool_key: The pool to add liquidity to
        tick_lower: Lower tick boundary
        tick_upper: Upper tick boundary
        liquidity: Amount of liquidity to add
        amount0_max: Maximum amount of token0 to spend
        amount1_max: Maximum amount of token1 to spend
        recipient: Address to receive the position NFT
        hook_data: Optional data for hooks

    Returns:
        (actions_bytes, params_list) for modifyLiquidities call
    """
    # Actions: MINT_POSITION then SETTLE_PAIR
    actions = bytes([Actions.MINT_POSITION, Actions.SETTLE_PAIR])

    # Params for MINT_POSITION
    mint_params = encode(
        [
            "(address,address,uint24,int24,address)",  # PoolKey
            "int24",      # tickLower
            "int24",      # tickUpper
            "uint256",    # liquidity
            "uint128",    # amount0Max
            "uint128",    # amount1Max
            "address",    # recipient
            "bytes",      # hookData
        ],
        [
            pool_key.to_tuple(),
            tick_lower,
            tick_upper,
            liquidity,
            amount0_max,
            amount1_max,
            recipient,
            hook_data,
        ],
    )

    # Params for SETTLE_PAIR - just the currencies
    settle_params = encode(
        ["address", "address"],
        [pool_key.currency0, pool_key.currency1],
    )

    return actions, [mint_params, settle_params]


def encode_mint_position_with_native_eth(
    pool_key: PoolKey,
    tick_lower: int,
    tick_upper: int,
    liquidity: int,
    amount0_max: int,
    amount1_max: int,
    recipient: str,
    hook_data: bytes = b"",
) -> Tuple[bytes, List[bytes]]:
    """
    Encode MINT_POSITION + SETTLE_PAIR + SWEEP for positions with native ETH.

    When using native ETH, we need to SWEEP any excess ETH back to the caller.

    Returns:
        (actions_bytes, params_list) for modifyLiquidities call
    """
    # Actions: MINT_POSITION, SETTLE_PAIR, then SWEEP excess ETH
    actions = bytes([Actions.MINT_POSITION, Actions.SETTLE_PAIR, Actions.SWEEP])

    # Params for MINT_POSITION
    mint_params = encode(
        [
            "(address,address,uint24,int24,address)",
            "int24",
            "int24",
            "uint256",
            "uint128",
            "uint128",
            "address",
            "bytes",
        ],
        [
            pool_key.to_tuple(),
            tick_lower,
            tick_upper,
            liquidity,
            amount0_max,
            amount1_max,
            recipient,
            hook_data,
        ],
    )

    # Params for SETTLE_PAIR
    settle_params = encode(
        ["address", "address"],
        [pool_key.currency0, pool_key.currency1],
    )

    # Params for SWEEP - sweep native ETH to recipient
    sweep_params = encode(
        ["address", "address"],
        [ADDRESS_ZERO, recipient],
    )

    return actions, [mint_params, settle_params, sweep_params]


def encode_decrease_liquidity(
    token_id: int,
    liquidity: int,
    amount0_min: int,
    amount1_min: int,
    recipient: str,
    hook_data: bytes = b"",
) -> Tuple[bytes, List[bytes]]:
    """
    Encode DECREASE_LIQUIDITY + TAKE_PAIR actions.

    Args:
        token_id: Position NFT token ID
        liquidity: Amount of liquidity to remove
        amount0_min: Minimum amount of token0 to receive
        amount1_min: Minimum amount of token1 to receive
        recipient: Address to receive tokens
        hook_data: Optional data for hooks

    Returns:
        (actions_bytes, params_list) for modifyLiquidities call
    """
    # Actions: DECREASE_LIQUIDITY then TAKE_PAIR
    actions = bytes([Actions.DECREASE_LIQUIDITY, Actions.TAKE_PAIR])

    # Params for DECREASE_LIQUIDITY
    decrease_params = encode(
        [
            "uint256",    # tokenId
            "uint256",    # liquidity
            "uint128",    # amount0Min
            "uint128",    # amount1Min
            "bytes",      # hookData
        ],
        [token_id, liquidity, amount0_min, amount1_min, hook_data],
    )

    # Params for TAKE_PAIR - recipient and settle flag
    take_params = encode(
        ["address", "address", "address"],
        [
            ADDRESS_ZERO,  # currency0 (resolved from position)
            ADDRESS_ZERO,  # currency1 (resolved from position)
            recipient,
        ],
    )

    return actions, [decrease_params, take_params]


def encode_collect_fees(
    token_id: int,
    recipient: str,
    hook_data: bytes = b"",
) -> Tuple[bytes, List[bytes]]:
    """
    Encode fee collection (DECREASE_LIQUIDITY with 0 liquidity).

    In V4, fee collection is done via DECREASE_LIQUIDITY with liquidity=0.

    Args:
        token_id: Position NFT token ID
        recipient: Address to receive collected fees
        hook_data: Optional data for hooks

    Returns:
        (actions_bytes, params_list) for modifyLiquidities call
    """
    return encode_decrease_liquidity(
        token_id=token_id,
        liquidity=0,
        amount0_min=0,
        amount1_min=0,
        recipient=recipient,
        hook_data=hook_data,
    )


def encode_burn_position(token_id: int) -> Tuple[bytes, List[bytes]]:
    """
    Encode BURN_POSITION action.

    Args:
        token_id: Position NFT token ID to burn

    Returns:
        (actions_bytes, params_list) for modifyLiquidities call
    """
    actions = bytes([Actions.BURN_POSITION])
    burn_params = encode(["uint256"], [token_id])
    return actions, [burn_params]


def encode_swap_exact_in_single(
    pool_key: PoolKey,
    zero_for_one: bool,
    amount_in: int,
    amount_out_minimum: int,
    sqrt_price_limit_x96: int = 0,
    hook_data: bytes = b"",
) -> bytes:
    """
    Encode parameters for V4_SWAP command in Universal Router.

    Args:
        pool_key: The pool to swap through
        zero_for_one: True if swapping currency0 for currency1
        amount_in: Exact amount of input token
        amount_out_minimum: Minimum amount of output token
        sqrt_price_limit_x96: Price limit (0 for no limit)
        hook_data: Optional data for hooks

    Returns:
        Encoded swap params for Universal Router
    """
    return encode(
        [
            "(address,address,uint24,int24,address)",  # PoolKey
            "bool",       # zeroForOne
            "int256",     # amountSpecified (negative for exact input)
            "uint160",    # sqrtPriceLimitX96
            "bytes",      # hookData
        ],
        [
            pool_key.to_tuple(),
            zero_for_one,
            -amount_in,  # Negative for exact input
            sqrt_price_limit_x96 if sqrt_price_limit_x96 else (0 if zero_for_one else 2**160 - 1),
            hook_data,
        ],
    )
