"""Custom exceptions for AMM Trading"""


class AMMError(Exception):
    """Base exception for all AMM errors"""
    pass


class ConfigError(AMMError):
    """Configuration-related errors"""
    pass


class ConnectionError(AMMError):
    """Web3 connection errors"""
    pass


class TransactionError(AMMError):
    """Transaction execution errors"""
    pass


class InsufficientBalanceError(AMMError):
    """Insufficient token balance"""
    pass


class PositionError(AMMError):
    """Position-related errors (not found, not owned, etc.)"""
    pass


class PoolError(AMMError):
    """Pool-related errors (not found, not initialized, etc.)"""
    pass


class QuoteError(AMMError):
    """Quote-related errors (failed to get quote, etc.)"""
    pass
