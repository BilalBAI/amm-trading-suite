"""Uniswap V4 specific configuration"""

import os
import json
from pathlib import Path

from ...core.config import Config
from ...core.exceptions import ConfigError


# Chain ID to network name mapping
CHAIN_NAMES = {
    1: "mainnet",
    42161: "arbitrum",
    10: "optimism",
    8453: "base",
    137: "polygon",
}


class UniswapV4Config:
    """Configuration manager for Uniswap V4 protocol"""

    _instance = None
    _addresses = None
    _pools = None
    _abis = None

    # Package files (not user-configurable)
    ADDRESSES_FILE = Path(__file__).parent / "addresses.json"
    ABIS_FILE = Path(__file__).parent / "abis.json"

    # V4 fee tier to tick spacing mapping (same as V3, but V4 allows custom)
    TICK_SPACING = {
        100: 1,      # 0.01% fee
        500: 10,     # 0.05% fee
        3000: 60,    # 0.30% fee
        10000: 200,  # 1.00% fee
    }

    # Constants (same as V3)
    Q96 = 2 ** 96
    Q128 = 2 ** 128
    MAX_UINT128 = 2 ** 128 - 1
    MAX_UINT256 = 2 ** 256 - 1

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if UniswapV4Config._addresses is None:
            self._load()
        # Also get shared config for common_tokens
        self._shared_config = Config()

    def _find_config_dir(self):
        """Find user config directory"""
        env_path = os.getenv("AMM_CONFIG_DIR")
        if env_path:
            path = Path(env_path)
            if path.exists():
                return path

        locations = [
            Path.cwd() / "config",
            Path(__file__).parent.parent.parent.parent / "config",
            Path.home() / ".amm-trading" / "config",
        ]

        for path in locations:
            if path.exists():
                return path

        return None

    def _load(self):
        """Load V4-specific configuration files"""
        # Load addresses from package
        if not self.ADDRESSES_FILE.exists():
            raise ConfigError(f"V4 addresses not found: {self.ADDRESSES_FILE}")
        with open(self.ADDRESSES_FILE) as f:
            UniswapV4Config._addresses = json.load(f)

        # Load ABIs from package
        if not self.ABIS_FILE.exists():
            raise ConfigError(f"V4 ABIs not found: {self.ABIS_FILE}")
        with open(self.ABIS_FILE) as f:
            UniswapV4Config._abis = json.load(f)

        # Load pools from user config
        config_dir = self._find_config_dir()
        if config_dir:
            pools_file = config_dir / "uniswap_v4" / "pools.json"
            if pools_file.exists():
                with open(pools_file) as f:
                    UniswapV4Config._pools = json.load(f)
            else:
                UniswapV4Config._pools = {}
        else:
            UniswapV4Config._pools = {}

    def _get_network(self, chain_id=None):
        """Get network name from chain ID"""
        if chain_id is None:
            return "mainnet"
        return CHAIN_NAMES.get(chain_id, "mainnet")

    def get_contracts(self, chain_id=None):
        """Get contract addresses for a specific chain"""
        network = self._get_network(chain_id)
        return UniswapV4Config._addresses.get(
            network, UniswapV4Config._addresses.get("mainnet", {})
        )

    @property
    def contracts(self):
        """V4 contract addresses (mainnet by default)"""
        return self.get_contracts()

    @property
    def pools(self):
        """V4 pool name -> PoolKey config mapping"""
        return UniswapV4Config._pools or {}

    @property
    def pool_manager_address(self):
        """PoolManager singleton address"""
        return self.contracts.get("poolManager")

    @property
    def position_manager_address(self):
        """Position Manager address"""
        return self.contracts.get("positionManager")

    @property
    def state_view_address(self):
        """StateView read-only contract address"""
        return self.contracts.get("stateView")

    @property
    def quoter_address(self):
        """V4 Quoter address"""
        return self.contracts.get("quoter")

    @property
    def universal_router_address(self):
        """Universal Router address"""
        return self.contracts.get("universalRouter")

    @property
    def permit2_address(self):
        """Permit2 contract address"""
        return self.contracts.get("permit2")

    @property
    def common_tokens(self):
        """Delegate to shared config for common tokens"""
        return self._shared_config.common_tokens

    def get_abi(self, name):
        """
        Get V4-specific ABI by name.

        Supports both short names ("poolManager", "positionManager") and
        legacy names ("uniswap_v4_pool_manager").
        """
        # Handle legacy names with uniswap_v4_ prefix
        if name.startswith("uniswap_v4_"):
            short_name = name.replace("uniswap_v4_", "")
        else:
            short_name = name

        if short_name in UniswapV4Config._abis:
            return UniswapV4Config._abis[short_name]

        # Check events sub-dict
        events = UniswapV4Config._abis.get("events", {})
        if short_name in events:
            return events[short_name]

        raise ConfigError(f"V4 ABI not found: {name}")

    def get_token_address(self, symbol_or_address):
        """Delegate to shared config for token resolution"""
        return self._shared_config.get_token_address(symbol_or_address)

    def get_tick_spacing(self, fee):
        """Get tick spacing for fee tier"""
        if fee not in self.TICK_SPACING:
            raise ConfigError(
                f"Invalid fee tier: {fee}. Valid: {list(self.TICK_SPACING.keys())}"
            )
        return self.TICK_SPACING[fee]

    def is_native_eth(self, address):
        """Check if address represents native ETH (address zero)"""
        from .types import ADDRESS_ZERO
        return address.lower() == ADDRESS_ZERO.lower()
