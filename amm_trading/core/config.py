"""Configuration loading and management"""

import os
import json
from pathlib import Path
from .exceptions import ConfigError


class Config:
    """Centralized configuration manager for shared settings"""

    _instance = None
    _tokens = None
    _abis = None

    # Shared ABIs are inside the package (not user-configurable)
    PACKAGE_ABIS = Path(__file__).parent.parent / "abis.json"

    # Constants (shared across protocols)
    Q96 = 2 ** 96
    Q128 = 2 ** 128
    MAX_UINT128 = 2 ** 128 - 1

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if Config._tokens is None:
            self._load()

    def _find_config_dir(self):
        """Find config directory"""
        # Check environment variable first
        env_path = os.getenv("AMM_CONFIG_DIR")
        if env_path:
            path = Path(env_path)
            if path.exists():
                return path

        # Check common locations
        locations = [
            Path.cwd() / "config",                              # Current directory
            Path(__file__).parent.parent.parent / "config",     # Package parent
            Path.home() / ".amm-trading" / "config",            # Home directory
        ]

        for path in locations:
            if path.exists():
                return path

        raise ConfigError(f"Could not find config directory. Searched: {[str(p) for p in locations]}")

    def _load(self):
        """Load configuration files"""
        config_dir = self._find_config_dir()

        # Load tokens
        tokens_path = config_dir / "tokens.json"
        if not tokens_path.exists():
            raise ConfigError(f"tokens.json not found in {config_dir}")
        with open(tokens_path) as f:
            Config._tokens = json.load(f)

        # Load shared ABIs from package
        if not self.PACKAGE_ABIS.exists():
            raise ConfigError(f"Shared ABIs not found: {self.PACKAGE_ABIS}")
        with open(self.PACKAGE_ABIS) as f:
            Config._abis = json.load(f)

    @property
    def common_tokens(self):
        """Common token symbol -> address mapping"""
        return Config._tokens or {}

    def get_abi(self, name):
        """
        Get ABI by name.

        First checks shared ABIs, then delegates to protocol-specific configs
        for protocol-prefixed names (e.g., "uniswap_v3_pool").
        """
        # Check shared ABIs first
        if name in Config._abis:
            return Config._abis[name]

        # Delegate to protocol-specific configs for prefixed names
        if name.startswith("uniswap_v3_"):
            from ..protocols.uniswap_v3.config import UniswapV3Config
            return UniswapV3Config().get_abi(name)

        raise ConfigError(f"ABI not found: {name}")

    def get_token_address(self, symbol_or_address):
        """Resolve token symbol to address, or validate address"""
        token = symbol_or_address.upper()

        if token in self.common_tokens:
            return self.common_tokens[token]

        if symbol_or_address.startswith("0x") and len(symbol_or_address) == 42:
            return symbol_or_address

        raise ConfigError(f"Unknown token: {symbol_or_address}")
