"""Configuration loading and management"""

import os
import json
from pathlib import Path
from .exceptions import ConfigError


class Config:
    """Centralized configuration manager"""

    _instance = None
    _config = None
    _abis = None

    # Default paths (relative to package root or cwd)
    DEFAULT_CONFIG = "config.json"
    DEFAULT_ABIS = "abis.json"

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
        if Config._config is None:
            self._load()

    def _find_file(self, filename):
        """Find config file in common locations"""
        # Check environment variable first
        env_path = os.getenv("AMM_CONFIG_DIR")
        if env_path:
            path = Path(env_path) / filename
            if path.exists():
                return path

        # Check common locations
        locations = [
            Path.cwd() / filename,                          # Current directory
            Path(__file__).parent.parent.parent / filename, # Package parent (amm-tools/)
            Path.home() / ".amm-tools" / filename,          # Home directory
        ]

        for path in locations:
            if path.exists():
                return path

        raise ConfigError(f"Could not find {filename}. Searched: {[str(p) for p in locations]}")

    def _load(self):
        """Load configuration files"""
        config_path = self._find_file(self.DEFAULT_CONFIG)
        abis_path = self._find_file(self.DEFAULT_ABIS)

        with open(config_path) as f:
            Config._config = json.load(f)

        with open(abis_path) as f:
            Config._abis = json.load(f)

    @property
    def contracts(self):
        """Contract addresses"""
        return Config._config.get("contracts", {})

    @property
    def common_tokens(self):
        """Common token symbol -> address mapping"""
        return Config._config.get("common_tokens", {})

    @property
    def pools(self):
        """Pool name -> address mapping"""
        return Config._config.get("univ3_pools", {})

    @property
    def nfpm_address(self):
        """NonfungiblePositionManager address"""
        return self.contracts.get("uniswap_v3_nfpm")

    @property
    def factory_address(self):
        """Uniswap V3 Factory address"""
        return self.contracts.get("uniswap_v3_factory")

    def get_abi(self, name):
        """Get ABI by name"""
        if name not in Config._abis:
            raise ConfigError(f"ABI not found: {name}")
        return Config._abis[name]

    def get_token_address(self, symbol_or_address):
        """Resolve token symbol to address, or validate address"""
        token = symbol_or_address.upper()

        if token in self.common_tokens:
            return self.common_tokens[token]

        if symbol_or_address.startswith("0x") and len(symbol_or_address) == 42:
            return symbol_or_address

        raise ConfigError(f"Unknown token: {symbol_or_address}")

    def get_tick_spacing(self, fee):
        """Get tick spacing for fee tier"""
        if fee not in self.TICK_SPACING:
            raise ConfigError(f"Invalid fee tier: {fee}. Valid: {list(self.TICK_SPACING.keys())}")
        return self.TICK_SPACING[fee]
