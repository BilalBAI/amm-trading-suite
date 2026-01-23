"""Pool query operations"""

import json
from pathlib import Path

from ..core.connection import Web3Manager
from ..core.config import Config
from ..contracts.pool import Pool
from ..contracts.erc20 import ERC20
from ..utils.math import tick_to_price

# Cache file in root folder
CACHE_FILE = Path.cwd() / "pool_info.json"


class PoolQuery:
    """Query Uniswap V3 pool information"""

    def __init__(self, manager=None):
        """
        Args:
            manager: Web3Manager instance (created if None)
        """
        self.manager = manager or Web3Manager(require_signer=False)
        self.config = Config()
        self._cache = None  # Internal dict for fast lookup

    def _load_cache(self):
        """Load static pool data from cache file (list format)"""
        if self._cache is not None:
            return self._cache

        if CACHE_FILE.exists():
            with open(CACHE_FILE) as f:
                cache_list = json.load(f)
                # Convert list to dict for fast lookup
                self._cache = {item["address"].lower(): item for item in cache_list}
        else:
            self._cache = {}

        return self._cache

    def _save_cache(self):
        """Save cache to file as list format"""
        # Convert dict to list for saving
        cache_list = list(self._cache.values())
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_list, f, indent=2)

    def _get_static_info(self, pool_address):
        """Get static pool info from cache or fetch from chain"""
        cache = self._load_cache()
        address_lower = pool_address.lower()

        if address_lower in cache:
            return cache[address_lower]

        # Fetch static data from chain
        pool = Pool(self.manager, pool_address)
        token0_addr = pool.token0
        token1_addr = pool.token1
        token0 = ERC20(self.manager, token0_addr)
        token1 = ERC20(self.manager, token1_addr)
        fee = pool.fee

        static_info = {
            "pool_name": f"{token0.symbol}_{token1.symbol}_{fee // 100}",
            "address": pool_address,
            "token0": {
                "address": token0_addr,
                "symbol": token0.symbol,
                "decimals": token0.decimals,
            },
            "token1": {
                "address": token1_addr,
                "symbol": token1.symbol,
                "decimals": token1.decimals,
            },
            "pair": f"{token0.symbol}/{token1.symbol}",
            "fee": fee,
            "fee_percent": f"{fee / 10000}%",
            "tick_spacing": self.config.get_tick_spacing(fee),
        }

        # Save to cache
        cache[address_lower] = static_info
        self._cache = cache
        self._save_cache()

        return static_info

    def get_pool_info(self, pool_address):
        """
        Get detailed pool information.
        Uses cache for static data, fetches dynamic data fresh.

        Args:
            pool_address: Pool contract address

        Returns:
            Dict with pool details
        """
        # Get static info (from cache or chain)
        static = self._get_static_info(pool_address)

        # Get dynamic info (always from chain)
        pool = Pool(self.manager, pool_address)
        current_tick = pool.current_tick
        price = pool.get_price(static["token0"]["decimals"], static["token1"]["decimals"])

        # Merge static and dynamic
        return {
            **static,
            "current_tick": current_tick,
            "current_price": price,
            "price_formatted": f"{price:.6f} {static['token1']['symbol']}/{static['token0']['symbol']}",
            "liquidity": pool.liquidity,
        }

    def get_all_configured_pools(self):
        """
        Query all pools defined in config.

        Returns:
            List of pool info dicts
        """
        results = []

        for name, address in self.config.pools.items():
            try:
                results.append(self.get_pool_info(address))
            except Exception as e:
                results.append({"pool_name": name, "address": address, "error": str(e)})

        return results

    def refresh_cache(self, pool_address=None):
        """
        Force refresh cache for a pool or all configured pools.

        Args:
            pool_address: Specific pool to refresh, or None for all
        """
        self._cache = {}

        if pool_address:
            self._get_static_info(pool_address)
        else:
            for address in self.config.pools.values():
                try:
                    self._get_static_info(address)
                except Exception:
                    pass

        self._save_cache()
