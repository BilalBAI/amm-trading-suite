"""Uniswap V4 type definitions and helpers"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Tuple
from eth_abi import encode

# Native ETH is represented by address zero in V4
ADDRESS_ZERO = "0x0000000000000000000000000000000000000000"


@dataclass
class PoolKey:
    """
    Identifies a V4 pool.

    In V4, pools are identified by a PoolKey rather than a contract address.
    The PoolKey is hashed to produce the pool ID used in PoolManager.

    Attributes:
        currency0: Lower address token (use ADDRESS_ZERO for native ETH)
        currency1: Higher address token
        fee: Fee in hundredths of a bip (e.g., 3000 = 0.30%)
        tick_spacing: Tick spacing for the pool
        hooks: Address of hooks contract (ADDRESS_ZERO for no hooks)
    """

    currency0: str
    currency1: str
    fee: int
    tick_spacing: int
    hooks: str = ADDRESS_ZERO

    def __post_init__(self):
        # Ensure currency0 < currency1
        if self.currency0.lower() > self.currency1.lower():
            raise ValueError(
                f"currency0 must be < currency1. Got: {self.currency0} > {self.currency1}"
            )

    def to_tuple(self) -> tuple:
        """Convert to tuple for ABI encoding"""
        return (
            self.currency0,
            self.currency1,
            self.fee,
            self.tick_spacing,
            self.hooks,
        )


class Actions(IntEnum):
    """
    V4 Position Manager action codes.

    V4 uses an encoded action system where multiple operations
    are batched together in a single transaction.
    """

    # Position operations
    INCREASE_LIQUIDITY = 0x00
    DECREASE_LIQUIDITY = 0x01
    MINT_POSITION = 0x02
    BURN_POSITION = 0x03

    # Token settling/taking
    SETTLE = 0x09
    SETTLE_ALL = 0x10
    SETTLE_PAIR = 0x11
    TAKE = 0x12
    TAKE_ALL = 0x13
    TAKE_PAIR = 0x14
    TAKE_PORTION = 0x15

    # Special
    CLOSE_CURRENCY = 0x17
    CLEAR_OR_TAKE = 0x19
    SWEEP = 0x18


# Fee tier to tick spacing mapping (same as V3 but V4 allows custom)
DEFAULT_TICK_SPACING = {
    100: 1,      # 0.01% fee
    500: 10,     # 0.05% fee
    3000: 60,    # 0.30% fee
    10000: 200,  # 1.00% fee
}


def sort_currencies(token_a: str, token_b: str) -> Tuple[str, str]:
    """
    Sort two token addresses to get (currency0, currency1).

    In V4, currency0 must always be the lower address.
    Use ADDRESS_ZERO for native ETH.

    Args:
        token_a: First token address
        token_b: Second token address

    Returns:
        (currency0, currency1) tuple with currency0 < currency1
    """
    if token_a.lower() < token_b.lower():
        return (token_a, token_b)
    return (token_b, token_a)


def create_pool_key(
    token_a: str,
    token_b: str,
    fee: int,
    tick_spacing: Optional[int] = None,
    hooks: str = ADDRESS_ZERO,
) -> PoolKey:
    """
    Create a PoolKey with properly sorted currencies.

    Args:
        token_a: First token address (or ADDRESS_ZERO for ETH)
        token_b: Second token address
        fee: Fee in hundredths of a bip (e.g., 3000 = 0.30%)
        tick_spacing: Tick spacing (defaults based on fee tier)
        hooks: Hooks contract address (default: no hooks)

    Returns:
        PoolKey with currency0 < currency1
    """
    currency0, currency1 = sort_currencies(token_a, token_b)

    if tick_spacing is None:
        tick_spacing = DEFAULT_TICK_SPACING.get(fee)
        if tick_spacing is None:
            raise ValueError(
                f"Unknown fee tier: {fee}. Specify tick_spacing explicitly or use "
                f"one of: {list(DEFAULT_TICK_SPACING.keys())}"
            )

    return PoolKey(
        currency0=currency0,
        currency1=currency1,
        fee=fee,
        tick_spacing=tick_spacing,
        hooks=hooks,
    )


def is_native_eth(address: str) -> bool:
    """Check if address represents native ETH (address zero)"""
    return address.lower() == ADDRESS_ZERO.lower()


def compute_pool_id(pool_key: PoolKey) -> bytes:
    """
    Compute the pool ID from a PoolKey.

    The pool ID is the keccak256 hash of the ABI-encoded PoolKey.

    Args:
        pool_key: The PoolKey to hash

    Returns:
        32-byte pool ID
    """
    from web3 import Web3

    # ABI encode the PoolKey struct
    encoded = encode(
        ["address", "address", "uint24", "int24", "address"],
        [
            pool_key.currency0,
            pool_key.currency1,
            pool_key.fee,
            pool_key.tick_spacing,
            pool_key.hooks,
        ],
    )

    return Web3.keccak(encoded)
