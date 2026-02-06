"""Uniswap V3 specific configuration"""

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


class UniswapV3Config:
    """Configuration manager for Uniswap V3 protocol"""

    _instance = None
    _addresses = None
    _pools = None
    _abis = None

    # Package files (not user-configurable)
    ADDRESSES_FILE = Path(__file__).parent / "addresses.json"
    ABIS_FILE = Path(__file__).parent / "abis.json"

    # Fee tier to tick spacing mapping
    TICK_SPACING = {
        100: 1,
        500: 10,
        3000: 60,
        10000: 200,
    }

    # Constants
    Q96 = 2 ** 96
    Q128 = 2 ** 128
    MAX_UINT128 = 2 ** 128 - 1

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if UniswapV3Config._addresses is None:
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
        """Load V3-specific configuration files"""
        # Load addresses from package
        if not self.ADDRESSES_FILE.exists():
            raise ConfigError(f"V3 addresses not found: {self.ADDRESSES_FILE}")
        with open(self.ADDRESSES_FILE) as f:
            UniswapV3Config._addresses = json.load(f)

        # Load ABIs from package
        if not self.ABIS_FILE.exists():
            raise ConfigError(f"V3 ABIs not found: {self.ABIS_FILE}")
        with open(self.ABIS_FILE) as f:
            UniswapV3Config._abis = json.load(f)

        # Load pools from user config
        config_dir = self._find_config_dir()
        if config_dir:
            pools_file = config_dir / "uniswap_v3" / "pools.json"
            if pools_file.exists():
                with open(pools_file) as f:
                    UniswapV3Config._pools = json.load(f)
            else:
                UniswapV3Config._pools = {}
        else:
            UniswapV3Config._pools = {}

    def _get_network(self, chain_id=None):
        """Get network name from chain ID"""
        if chain_id is None:
            # Default to mainnet
            return "mainnet"
        return CHAIN_NAMES.get(chain_id, "mainnet")

    def get_contracts(self, chain_id=None):
        """Get contract addresses for a specific chain"""
        network = self._get_network(chain_id)
        return UniswapV3Config._addresses.get(network, UniswapV3Config._addresses.get("mainnet", {}))

    @property
    def contracts(self):
        """V3 contract addresses (mainnet by default)"""
        return self.get_contracts()

    @property
    def pools(self):
        """V3 pool name -> address mapping"""
        return UniswapV3Config._pools or {}

    @property
    def nfpm_address(self):
        """NonfungiblePositionManager address"""
        return self.contracts.get("nfpm")

    @property
    def factory_address(self):
        """Uniswap V3 Factory address"""
        return self.contracts.get("factory")

    @property
    def router_address(self):
        """Uniswap V3 SwapRouter address"""
        return self.contracts.get("router")

    @property
    def quoter_address(self):
        """Uniswap V3 QuoterV2 address"""
        return self.contracts.get("quoter")

    @property
    def common_tokens(self):
        """Delegate to shared config for common tokens"""
        return self._shared_config.common_tokens

    def get_abi(self, name):
        """
        Get V3-specific ABI by name.

        Supports both short names ("nfpm", "pool") and legacy names ("uniswap_v3_nfpm").
        """
        # Handle legacy names with uniswap_v3_ prefix
        if name.startswith("uniswap_v3_"):
            short_name = name.replace("uniswap_v3_", "")
        else:
            short_name = name

        if short_name in UniswapV3Config._abis:
            return UniswapV3Config._abis[short_name]

        # Check events sub-dict
        events = UniswapV3Config._abis.get("events", {})
        if short_name in events:
            return events[short_name]

        raise ConfigError(f"V3 ABI not found: {name}")

    def get_token_address(self, symbol_or_address):
        """Delegate to shared config for token resolution"""
        return self._shared_config.get_token_address(symbol_or_address)

    def get_tick_spacing(self, fee):
        """Get tick spacing for fee tier"""
        if fee not in self.TICK_SPACING:
            raise ConfigError(f"Invalid fee tier: {fee}. Valid: {list(self.TICK_SPACING.keys())}")
        return self.TICK_SPACING[fee]
