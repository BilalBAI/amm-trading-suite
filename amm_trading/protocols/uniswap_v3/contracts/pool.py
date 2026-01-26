"""Uniswap V3 Pool contract wrapper"""

from ....core.config import Config


class Pool:
    """Wrapper for Uniswap V3 Pool interactions"""

    def __init__(self, manager, address):
        """
        Args:
            manager: Web3Manager instance
            address: Pool contract address
        """
        self.manager = manager
        self.address = manager.checksum(address)
        self.contract = manager.get_contract(address, "uniswap_v3_pool")
        self.config = Config()
        self._slot0_cache = None

    def slot0(self, use_cache=False):
        """
        Get slot0 data (current state).
        Returns: (sqrtPriceX96, tick, observationIndex, ...)
        """
        if use_cache and self._slot0_cache:
            return self._slot0_cache
        self._slot0_cache = self.contract.functions.slot0().call()
        return self._slot0_cache

    @property
    def sqrt_price_x96(self):
        """Current sqrt price"""
        return self.slot0()[0]

    @property
    def current_tick(self):
        """Current tick"""
        return self.slot0()[1]

    @property
    def fee(self):
        """Pool fee tier"""
        return self.contract.functions.fee().call()

    @property
    def token0(self):
        """Token0 address"""
        return self.contract.functions.token0().call()

    @property
    def token1(self):
        """Token1 address"""
        return self.contract.functions.token1().call()

    @property
    def liquidity(self):
        """Current pool liquidity"""
        return self.contract.functions.liquidity().call()

    def fee_growth_global(self):
        """Get global fee growth"""
        return (
            self.contract.functions.feeGrowthGlobal0X128().call(),
            self.contract.functions.feeGrowthGlobal1X128().call(),
        )

    def ticks(self, tick):
        """Get tick data"""
        return self.contract.functions.ticks(tick).call()

    def get_price(self, decimals0, decimals1):
        """Calculate human-readable price from sqrtPriceX96"""
        sqrt_price = self.sqrt_price_x96
        price = (sqrt_price / self.config.Q96) ** 2
        return price * (10 ** decimals0) / (10 ** decimals1)
