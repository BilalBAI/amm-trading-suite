"""Uniswap V4 PoolManager contract wrapper"""

from web3 import Web3
from ..config import UniswapV4Config
from ..types import PoolKey, compute_pool_id
from ....core.exceptions import PoolError


class PoolManager:
    """
    Wrapper for Uniswap V4 PoolManager interactions.

    V4 uses a singleton PoolManager contract that holds state for all pools.
    Pools are identified by PoolKey (hash) rather than individual contract addresses.
    """

    def __init__(self, manager):
        """
        Args:
            manager: Web3Manager instance
        """
        self.manager = manager
        self.config = UniswapV4Config()
        self.address = manager.checksum(self.config.pool_manager_address)
        self.contract = manager.get_contract(self.address, "poolManager")

    def get_pool_id(self, pool_key: PoolKey) -> bytes:
        """
        Compute pool ID from PoolKey.

        Args:
            pool_key: The pool's key

        Returns:
            32-byte pool ID (keccak256 hash of encoded PoolKey)
        """
        return compute_pool_id(pool_key)

    def initialize(self, pool_key: PoolKey, sqrt_price_x96: int) -> int:
        """
        Initialize a new pool with the given starting price.

        In V4, pool creation is just a state update (no new contract deployment).
        This is ~99% cheaper than V3 pool creation.

        Args:
            pool_key: The pool's key
            sqrt_price_x96: Initial sqrt(price) * 2^96

        Returns:
            Initial tick

        Raises:
            PoolError: If pool already exists or initialization fails
        """
        try:
            tx = self.contract.functions.initialize(
                pool_key.to_tuple(),
                sqrt_price_x96
            ).transact({'from': self.manager.address})
            receipt = self.manager.w3.eth.wait_for_transaction_receipt(tx)

            if receipt.status != 1:
                raise PoolError(f"Pool initialization failed: {tx.hex()}")

            # Return the initial tick from return value
            # Note: In practice, we'd decode this from the receipt
            return 0  # Placeholder - actual implementation would decode

        except Exception as e:
            if "already initialized" in str(e).lower():
                raise PoolError(f"Pool already exists: {pool_key}")
            raise PoolError(f"Failed to initialize pool: {e}")
