"""Uniswap V4 StateView contract wrapper for read-only queries"""

from web3 import Web3
from ..config import UniswapV4Config
from ..types import PoolKey, compute_pool_id
from ....core.exceptions import PoolError


class StateView:
    """
    Wrapper for Uniswap V4 StateView read-only queries.

    StateView provides efficient read-only access to pool state
    without requiring write access to PoolManager.
    """

    def __init__(self, manager):
        """
        Args:
            manager: Web3Manager instance
        """
        self.manager = manager
        self.config = UniswapV4Config()
        self.address = manager.checksum(self.config.state_view_address)
        self.contract = manager.get_contract(self.address, "stateView")
        self._slot0_cache = {}

    def get_slot0(self, pool_key: PoolKey, use_cache: bool = False):
        """
        Get slot0 data for a pool.

        Args:
            pool_key: The pool's key
            use_cache: Whether to use cached value if available

        Returns:
            dict with sqrtPriceX96, tick, protocolFee, lpFee
        """
        cache_key = str(pool_key.to_tuple())

        if use_cache and cache_key in self._slot0_cache:
            return self._slot0_cache[cache_key]

        try:
            result = self.contract.functions.getSlot0(pool_key.to_tuple()).call()
            slot0 = {
                "sqrt_price_x96": result[0],
                "tick": result[1],
                "protocol_fee": result[2],
                "lp_fee": result[3],
            }
            self._slot0_cache[cache_key] = slot0
            return slot0

        except Exception as e:
            raise PoolError(f"Failed to get slot0 for pool: {e}")

    def get_liquidity(self, pool_key: PoolKey) -> int:
        """
        Get total liquidity for a pool.

        Args:
            pool_key: The pool's key

        Returns:
            Total liquidity in the pool
        """
        try:
            return self.contract.functions.getLiquidity(pool_key.to_tuple()).call()
        except Exception as e:
            raise PoolError(f"Failed to get liquidity: {e}")

    def get_tick_info(self, pool_key: PoolKey, tick: int):
        """
        Get tick information.

        Args:
            pool_key: The pool's key
            tick: The tick to query

        Returns:
            dict with liquidityGross, liquidityNet, feeGrowthOutside0X128, feeGrowthOutside1X128
        """
        try:
            result = self.contract.functions.getTickInfo(
                pool_key.to_tuple(),
                tick
            ).call()
            return {
                "liquidity_gross": result[0],
                "liquidity_net": result[1],
                "fee_growth_outside_0_x128": result[2],
                "fee_growth_outside_1_x128": result[3],
            }
        except Exception as e:
            raise PoolError(f"Failed to get tick info: {e}")

    def get_position_info(
        self,
        pool_key: PoolKey,
        owner: str,
        tick_lower: int,
        tick_upper: int,
        salt: bytes = b"\x00" * 32
    ):
        """
        Get position information from state.

        Note: This is different from Position Manager's position tracking.
        This queries the underlying pool state.

        Args:
            pool_key: The pool's key
            owner: Position owner address
            tick_lower: Lower tick
            tick_upper: Upper tick
            salt: Position salt (for multiple positions at same range)

        Returns:
            dict with liquidity and fee growth values
        """
        pool_id = compute_pool_id(pool_key)

        try:
            result = self.contract.functions.getPositionInfo(
                pool_id,
                self.manager.checksum(owner),
                tick_lower,
                tick_upper,
                salt
            ).call()
            return {
                "liquidity": result[0],
                "fee_growth_inside_0_last_x128": result[1],
                "fee_growth_inside_1_last_x128": result[2],
            }
        except Exception as e:
            raise PoolError(f"Failed to get position info: {e}")

    @property
    def sqrt_price_x96(self):
        """Get current sqrt price (requires pool_key to be set)"""
        raise NotImplementedError("Use get_slot0(pool_key) instead")

    @property
    def current_tick(self):
        """Get current tick (requires pool_key to be set)"""
        raise NotImplementedError("Use get_slot0(pool_key) instead")

    def clear_cache(self):
        """Clear the slot0 cache"""
        self._slot0_cache = {}
