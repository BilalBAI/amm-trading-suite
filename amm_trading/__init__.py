"""
AMM Trading - A multi-protocol toolkit for AMM liquidity management
"""

from .core.connection import Web3Manager
from .core.config import Config
from .core.exceptions import AMMError, ConfigError, ConnectionError, TransactionError

__version__ = "0.1.0"
__all__ = [
    "Web3Manager",
    "Config",
    "AMMError",
    "ConfigError",
    "ConnectionError",
    "TransactionError",
]
