"""Pool query operations for Uniswap V4"""

import json
from pathlib import Path

from ....core.connection import Web3Manager
from ..config import UniswapV4Config
from ....contracts.erc20 import ERC20
from ..contracts.state_view import StateView
from ..types import PoolKey, ADDRESS_ZERO, create_pool_key, is_native_eth
from ..math import tick_to_price
from ...base import BasePoolQuery

# Cache file in working directory (V4-specific)
CACHE_FILE = Path.cwd() / "univ4_pool_cache.json"


class PoolQuery(BasePoolQuery):
    """Query Uniswap V4 pool information"""

    def __init__(self, manager=None):
        """
        Args:
            manager: Web3Manager instance (created if None)
        """
        self.manager = manager or Web3Manager(require_signer=False)
        self.config = UniswapV4Config()
        self.state_view = StateView(self.manager)
        self._cache = None

    def _load_cache(self):
        """Load static pool data from cache file"""
        if self._cache is not None:
            return self._cache

        if CACHE_FILE.exists():
            with open(CACHE_FILE) as f:
                cache_list = json.load(f)
                # Convert list to dict for fast lookup by pool name
                self._cache = {item["pool_name"]: item for item in cache_list}
        else:
            self._cache = {}

        return self._cache

    def _save_cache(self):
        """Save cache to file as list format"""
        cache_list = list(self._cache.values())
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_list, f, indent=2)

    def _get_pool_key_from_config(self, pool_name):
        """
        Get PoolKey from config by pool name.

        Config format:
        {
            "ETH_USDC_30": {
                "currency0": "0x0000...",  # ADDRESS_ZERO for ETH
                "currency1": "0xA0b8...",  # USDC
                "fee": 3000,
                "tickSpacing": 60,
                "hooks": "0x0000..."  # optional
            }
        }
        """
        pools = self.config.pools
        if pool_name not in pools:
            raise ValueError(f"Pool {pool_name} not found in config")

        pool_config = pools[pool_name]

        return PoolKey(
            currency0=pool_config.get("currency0", ADDRESS_ZERO),
            currency1=pool_config["currency1"],
            fee=pool_config["fee"],
            tick_spacing=pool_config["tickSpacing"],
            hooks=pool_config.get("hooks", ADDRESS_ZERO),
        )

    def _get_token_info(self, address):
        """Get token info, handling native ETH"""
        if is_native_eth(address):
            return {
                "address": ADDRESS_ZERO,
                "symbol": "ETH",
                "decimals": 18,
            }
        token = ERC20(self.manager, address)
        return {
            "address": address,
            "symbol": token.symbol,
            "decimals": token.decimals,
        }

    def get_pool_info(self, pool_identifier):
        """
        Get detailed pool information.

        In V4, pools are identified by PoolKey (not address).
        This method accepts either a pool name (from config) or a PoolKey.

        Args:
            pool_identifier: Pool name (string) or PoolKey

        Returns:
            Dict with pool details
        """
        if isinstance(pool_identifier, str):
            pool_key = self._get_pool_key_from_config(pool_identifier)
            pool_name = pool_identifier
        elif isinstance(pool_identifier, PoolKey):
            pool_key = pool_identifier
            pool_name = None
        else:
            raise ValueError(
                f"pool_identifier must be pool name or PoolKey, got {type(pool_identifier)}"
            )

        # Get token info
        token0_info = self._get_token_info(pool_key.currency0)
        token1_info = self._get_token_info(pool_key.currency1)

        # Generate pool name if not provided
        if pool_name is None:
            pool_name = f"{token0_info['symbol']}_{token1_info['symbol']}_{pool_key.fee // 100}"

        # Get dynamic data from state view
        try:
            slot0 = self.state_view.get_slot0(pool_key)
            liquidity = self.state_view.get_liquidity(pool_key)

            current_tick = slot0["tick"]
            sqrt_price_x96 = slot0["sqrt_price_x96"]

            # Calculate current price
            price = tick_to_price(
                current_tick,
                token0_info["decimals"],
                token1_info["decimals"]
            )

            return {
                "pool_name": pool_name,
                "pool_key": {
                    "currency0": pool_key.currency0,
                    "currency1": pool_key.currency1,
                    "fee": pool_key.fee,
                    "tick_spacing": pool_key.tick_spacing,
                    "hooks": pool_key.hooks,
                },
                "token0": token0_info,
                "token1": token1_info,
                "pair": f"{token0_info['symbol']}/{token1_info['symbol']}",
                "fee": pool_key.fee,
                "fee_percent": f"{pool_key.fee / 10000}%",
                "tick_spacing": pool_key.tick_spacing,
                "hooks": pool_key.hooks,
                "has_hooks": pool_key.hooks != ADDRESS_ZERO,
                "current_tick": current_tick,
                "current_price": price,
                "price_formatted": f"{price:.6f} {token1_info['symbol']}/{token0_info['symbol']}",
                "liquidity": liquidity,
                "protocol_fee": slot0["protocol_fee"],
                "lp_fee": slot0["lp_fee"],
            }

        except Exception as e:
            return {
                "pool_name": pool_name,
                "pool_key": {
                    "currency0": pool_key.currency0,
                    "currency1": pool_key.currency1,
                    "fee": pool_key.fee,
                    "tick_spacing": pool_key.tick_spacing,
                    "hooks": pool_key.hooks,
                },
                "error": str(e),
            }

    def get_all_configured_pools(self):
        """
        Query all pools defined in config.

        Returns:
            List of pool info dicts
        """
        results = []

        for name in self.config.pools.keys():
            try:
                results.append(self.get_pool_info(name))
            except Exception as e:
                results.append({"pool_name": name, "error": str(e)})

        return results

    def refresh_cache(self, pool_name=None):
        """
        Force refresh cache for a pool or all configured pools.

        Args:
            pool_name: Specific pool to refresh, or None for all
        """
        self._cache = {}
        self.state_view.clear_cache()

        if pool_name:
            try:
                info = self.get_pool_info(pool_name)
                self._cache[pool_name] = info
            except Exception:
                pass
        else:
            for name in self.config.pools.keys():
                try:
                    info = self.get_pool_info(name)
                    self._cache[name] = info
                except Exception:
                    pass

        self._save_cache()
