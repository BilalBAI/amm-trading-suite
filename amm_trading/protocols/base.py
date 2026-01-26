"""Abstract base classes for AMM protocol implementations"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any


class BaseLiquidityManager(ABC):
    """Abstract base class for liquidity management operations"""

    @abstractmethod
    def add_liquidity(self, **kwargs) -> Dict[str, Any]:
        """
        Add liquidity to a pool.

        Returns:
            Dict containing transaction details and position info
        """
        pass

    @abstractmethod
    def remove_liquidity(
        self, position_id: Any, percentage: float, **kwargs
    ) -> Dict[str, Any]:
        """
        Remove liquidity from a position.

        Args:
            position_id: Identifier for the position (NFT ID, etc.)
            percentage: Percentage of liquidity to remove (0-100)

        Returns:
            Dict containing transaction details and amounts received
        """
        pass


class BaseSwapManager(ABC):
    """Abstract base class for swap operations"""

    @abstractmethod
    def swap(
        self,
        token_in: str,
        token_out: str,
        amount_in: float,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute a token swap.

        Args:
            token_in: Input token symbol or address
            token_out: Output token symbol or address
            amount_in: Amount of input token (human readable)

        Returns:
            Dict containing transaction details and swap results
        """
        pass

    @abstractmethod
    def quote(
        self,
        token_in: str,
        token_out: str,
        amount_in: float,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get a quote for a swap without executing.

        Args:
            token_in: Input token symbol or address
            token_out: Output token symbol or address
            amount_in: Amount of input token (human readable)

        Returns:
            Dict containing expected output and price info
        """
        pass


class BasePositionQuery(ABC):
    """Abstract base class for querying positions"""

    @abstractmethod
    def get_position(self, position_id: Any) -> Dict[str, Any]:
        """
        Get details for a specific position.

        Args:
            position_id: Identifier for the position

        Returns:
            Dict containing position details
        """
        pass

    @abstractmethod
    def get_positions_for_address(self, address: str) -> List[Dict[str, Any]]:
        """
        Get all positions for an address.

        Args:
            address: Wallet address to query

        Returns:
            List of position details
        """
        pass


class BasePoolQuery(ABC):
    """Abstract base class for querying pool information"""

    @abstractmethod
    def get_pool_info(self, pool_address: str) -> Dict[str, Any]:
        """
        Get information about a specific pool.

        Args:
            pool_address: Address of the pool contract

        Returns:
            Dict containing pool details
        """
        pass

    @abstractmethod
    def get_all_configured_pools(self) -> List[Dict[str, Any]]:
        """
        Get information about all configured pools.

        Returns:
            List of pool details
        """
        pass
