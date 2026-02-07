"""Uniswap V4 Quoter contract wrapper"""

from web3 import Web3
from ..config import UniswapV4Config
from ..types import PoolKey
from ....core.exceptions import QuoteError


class Quoter:
    """
    Wrapper for Uniswap V4 Quoter contract.

    Provides swap quotes without executing transactions.
    """

    def __init__(self, manager):
        """
        Args:
            manager: Web3Manager instance
        """
        self.manager = manager
        self.config = UniswapV4Config()
        self.address = manager.checksum(self.config.quoter_address)
        self.contract = manager.get_contract(self.address, "quoter")

    def quote_exact_input_single(
        self,
        pool_key: PoolKey,
        zero_for_one: bool,
        amount_in: int,
        sqrt_price_limit_x96: int = 0,
        hook_data: bytes = b"",
    ):
        """
        Quote exact input swap for a single pool.

        Args:
            pool_key: The pool to swap through
            zero_for_one: True if swapping currency0 for currency1
            amount_in: Exact amount of input token (in wei)
            sqrt_price_limit_x96: Price limit (0 for no limit)
            hook_data: Optional data for hooks

        Returns:
            dict with amountOut and gasEstimate
        """
        params = (
            pool_key.to_tuple(),
            zero_for_one,
            amount_in,
            sqrt_price_limit_x96 if sqrt_price_limit_x96 else (0 if zero_for_one else 2**160 - 1),
            hook_data,
        )

        try:
            result = self.contract.functions.quoteExactInputSingle(params).call()
            return {
                "amount_out": result[0],
                "gas_estimate": result[1],
            }
        except Exception as e:
            raise QuoteError(f"Failed to get quote: {e}")

    def quote_exact_output_single(
        self,
        pool_key: PoolKey,
        zero_for_one: bool,
        amount_out: int,
        sqrt_price_limit_x96: int = 0,
        hook_data: bytes = b"",
    ):
        """
        Quote exact output swap for a single pool.

        Args:
            pool_key: The pool to swap through
            zero_for_one: True if swapping currency0 for currency1
            amount_out: Exact amount of output token wanted (in wei)
            sqrt_price_limit_x96: Price limit (0 for no limit)
            hook_data: Optional data for hooks

        Returns:
            dict with amountIn and gasEstimate
        """
        params = (
            pool_key.to_tuple(),
            zero_for_one,
            amount_out,
            sqrt_price_limit_x96 if sqrt_price_limit_x96 else (0 if zero_for_one else 2**160 - 1),
            hook_data,
        )

        try:
            result = self.contract.functions.quoteExactOutputSingle(params).call()
            return {
                "amount_in": result[0],
                "gas_estimate": result[1],
            }
        except Exception as e:
            raise QuoteError(f"Failed to get quote: {e}")
