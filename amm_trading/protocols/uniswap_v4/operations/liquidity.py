"""Liquidity management operations for Uniswap V4"""

import time
from ....core.connection import Web3Manager
from ..config import UniswapV4Config
from ....core.exceptions import InsufficientBalanceError, PositionError
from ....contracts.erc20 import ERC20
from ..contracts.position_manager import PositionManager
from ..contracts.state_view import StateView
from ..types import PoolKey, ADDRESS_ZERO, create_pool_key, is_native_eth, sort_currencies
from ..math import (
    round_tick_to_spacing,
    calculate_slippage_amounts,
    price_to_tick,
    tick_to_price,
    calculate_liquidity_from_amounts,
)
from ...base import BaseLiquidityManager


class LiquidityManager(BaseLiquidityManager):
    """
    Manage Uniswap V4 liquidity positions.

    Key differences from V3:
    - Native ETH support (no WETH wrapping required)
    - Uses PoolKey instead of pool address
    - Requires calculating liquidity from amounts
    - Uses encoded actions for position operations
    """

    def __init__(self, manager=None):
        """
        Args:
            manager: Web3Manager instance (created with signer if None)
        """
        self.manager = manager or Web3Manager(require_signer=True)
        self.config = UniswapV4Config()
        self.position_manager = PositionManager(self.manager)
        self.state_view = StateView(self.manager)

    def _get_token_address(self, symbol_or_address):
        """
        Get token address, mapping ETH to ADDRESS_ZERO for native ETH.

        V4 supports native ETH, so we don't need WETH wrapping.
        """
        if symbol_or_address.upper() == "ETH":
            return ADDRESS_ZERO
        return self.manager.checksum(self.config.get_token_address(symbol_or_address))

    def _get_token_contract(self, address):
        """Get ERC20 contract or None for native ETH"""
        if is_native_eth(address):
            return None
        return ERC20(self.manager, address)

    def _get_token_decimals(self, address):
        """Get token decimals, 18 for native ETH"""
        if is_native_eth(address):
            return 18
        return ERC20(self.manager, address).decimals

    def _get_token_symbol(self, address):
        """Get token symbol, 'ETH' for native ETH"""
        if is_native_eth(address):
            return "ETH"
        return ERC20(self.manager, address).symbol

    def _to_wei(self, amount, address):
        """Convert human amount to wei"""
        decimals = self._get_token_decimals(address)
        return int(amount * (10 ** decimals))

    def _from_wei(self, amount_wei, address):
        """Convert wei to human amount"""
        decimals = self._get_token_decimals(address)
        return amount_wei / (10 ** decimals)

    def _get_balance(self, address):
        """Get balance in wei (native ETH or ERC20)"""
        if is_native_eth(address):
            return self.manager.w3.eth.get_balance(self.manager.address)
        return ERC20(self.manager, address).balance_of()

    def calculate_optimal_amounts(
        self,
        token0,
        token1,
        fee,
        tick_lower,
        tick_upper,
        amount0_desired=None,
        amount1_desired=None,
        hooks=ADDRESS_ZERO,
    ):
        """
        Calculate optimal token amounts for a liquidity position.

        Args:
            token0: Token0 symbol or address (or 'ETH' for native)
            token1: Token1 symbol or address
            fee: Fee tier (500, 3000, 10000)
            tick_lower: Lower tick bound
            tick_upper: Upper tick bound
            amount0_desired: Desired amount of token0 (if None, calculated from amount1)
            amount1_desired: Desired amount of token1 (if None, calculated from amount0)
            hooks: Hooks contract address (default: no hooks)

        Returns:
            Dict with optimal amounts and position details
        """
        if (amount0_desired is None and amount1_desired is None) or \
           (amount0_desired is not None and amount1_desired is not None):
            raise ValueError("Must specify exactly one of amount0_desired or amount1_desired")

        # Resolve token addresses
        token0_addr = self._get_token_address(token0)
        token1_addr = self._get_token_address(token1)

        # Ensure correct token order
        currency0, currency1 = sort_currencies(token0_addr, token1_addr)
        swapped = currency0 != token0_addr

        if swapped:
            if amount0_desired is not None:
                amount1_desired = amount0_desired
                amount0_desired = None
            else:
                amount0_desired = amount1_desired
                amount1_desired = None

        # Get token info
        decimals0 = self._get_token_decimals(currency0)
        decimals1 = self._get_token_decimals(currency1)
        symbol0 = self._get_token_symbol(currency0)
        symbol1 = self._get_token_symbol(currency1)

        # Create pool key
        tick_spacing = self.config.get_tick_spacing(fee)
        pool_key = PoolKey(
            currency0=currency0,
            currency1=currency1,
            fee=fee,
            tick_spacing=tick_spacing,
            hooks=hooks,
        )

        # Get pool state
        slot0 = self.state_view.get_slot0(pool_key)
        current_tick = slot0["tick"]
        sqrt_price_x96 = slot0["sqrt_price_x96"]

        # Calculate prices
        current_price = tick_to_price(current_tick, decimals0, decimals1)
        price_lower = tick_to_price(tick_lower, decimals0, decimals1)
        price_upper = tick_to_price(tick_upper, decimals0, decimals1)

        # Determine position type and calculate amounts
        if current_tick < tick_lower:
            position_type = "below_range"
            if amount1_desired is not None:
                raise ValueError(
                    f"Current price (${current_price:.2f}) is below range. Only {symbol0} is needed."
                )
            calculated_amount0 = amount0_desired
            calculated_amount1 = 0.0
        elif current_tick > tick_upper:
            position_type = "above_range"
            if amount0_desired is not None:
                raise ValueError(
                    f"Current price (${current_price:.2f}) is above range. Only {symbol1} is needed."
                )
            calculated_amount0 = 0.0
            calculated_amount1 = amount1_desired
        else:
            position_type = "in_range"
            sqrt_price_raw = sqrt_price_x96 / (2 ** 96)
            sqrt_pl_raw = 1.0001 ** (tick_lower / 2)
            sqrt_pu_raw = 1.0001 ** (tick_upper / 2)

            decimal_adjustment = 10 ** ((decimals0 - decimals1) / 2)
            sqrt_price = sqrt_price_raw * decimal_adjustment
            sqrt_pl = sqrt_pl_raw * decimal_adjustment
            sqrt_pu = sqrt_pu_raw * decimal_adjustment

            if amount0_desired is not None:
                calculated_amount0 = amount0_desired
                calculated_amount1 = amount0_desired * \
                    (sqrt_price - sqrt_pl) / (1/sqrt_price - 1/sqrt_pu)
            else:
                calculated_amount1 = amount1_desired
                calculated_amount0 = amount1_desired * \
                    (1/sqrt_price - 1/sqrt_pu) / (sqrt_price - sqrt_pl)

        result = {
            "token0": {
                "symbol": symbol0,
                "address": currency0,
                "amount": calculated_amount0,
                "decimals": decimals0,
                "is_native_eth": is_native_eth(currency0),
            },
            "token1": {
                "symbol": symbol1,
                "address": currency1,
                "amount": calculated_amount1,
                "decimals": decimals1,
                "is_native_eth": is_native_eth(currency1),
            },
            "current_price": current_price,
            "price_lower": price_lower,
            "price_upper": price_upper,
            "tick_lower": tick_lower,
            "tick_upper": tick_upper,
            "current_tick": current_tick,
            "ratio": f"1 {symbol0} = {current_price:.2f} {symbol1}",
            "position_type": position_type,
            "pool_key": pool_key,
        }

        if swapped:
            result["token0"], result["token1"] = result["token1"], result["token0"]

        return result

    def calculate_optimal_amounts_range(
        self,
        token0,
        token1,
        fee,
        percent_lower,
        percent_upper,
        amount0_desired=None,
        amount1_desired=None,
        hooks=ADDRESS_ZERO,
    ):
        """
        Calculate optimal amounts using percentage ranges.

        Convenience wrapper around calculate_optimal_amounts().
        """
        token0_addr = self._get_token_address(token0)
        token1_addr = self._get_token_address(token1)
        currency0, currency1 = sort_currencies(token0_addr, token1_addr)

        tick_spacing = self.config.get_tick_spacing(fee)
        pool_key = PoolKey(
            currency0=currency0,
            currency1=currency1,
            fee=fee,
            tick_spacing=tick_spacing,
            hooks=hooks,
        )

        slot0 = self.state_view.get_slot0(pool_key)
        decimals0 = self._get_token_decimals(currency0)
        decimals1 = self._get_token_decimals(currency1)

        current_price = tick_to_price(slot0["tick"], decimals0, decimals1)

        price_lower = current_price * (1 + percent_lower)
        price_upper = current_price * (1 + percent_upper)

        tick_lower = price_to_tick(price_lower, decimals0, decimals1)
        tick_upper = price_to_tick(price_upper, decimals0, decimals1)

        tick_lower = round_tick_to_spacing(tick_lower, tick_spacing)
        tick_upper = round_tick_to_spacing(tick_upper, tick_spacing)

        return self.calculate_optimal_amounts(
            token0, token1, fee, tick_lower, tick_upper,
            amount0_desired, amount1_desired, hooks
        )

    def add_liquidity(
        self,
        token0,
        token1,
        fee,
        tick_lower,
        tick_upper,
        amount0,
        amount1,
        slippage_bps=50,
        hooks=ADDRESS_ZERO,
        **kwargs
    ):
        """
        Add liquidity to a Uniswap V4 pool.

        V4 supports native ETH - no WETH wrapping needed!

        Args:
            token0: Token0 symbol or address (use 'ETH' for native ETH)
            token1: Token1 symbol or address
            fee: Fee tier (500, 3000, 10000)
            tick_lower: Lower tick bound
            tick_upper: Upper tick bound
            amount0: Amount of token0 (human readable)
            amount1: Amount of token1 (human readable)
            slippage_bps: Slippage tolerance in basis points
            hooks: Hooks contract address (default: no hooks)

        Returns:
            Dict with receipt and token_id
        """
        token0_addr = self._get_token_address(token0)
        token1_addr = self._get_token_address(token1)

        # Sort currencies
        currency0, currency1 = sort_currencies(token0_addr, token1_addr)
        swapped = currency0 != token0_addr
        if swapped:
            amount0, amount1 = amount1, amount0

        # Get token info
        decimals0 = self._get_token_decimals(currency0)
        decimals1 = self._get_token_decimals(currency1)

        # Round ticks to valid values
        tick_spacing = self.config.get_tick_spacing(fee)
        tick_lower = round_tick_to_spacing(tick_lower, tick_spacing)
        tick_upper = round_tick_to_spacing(tick_upper, tick_spacing)

        if tick_lower >= tick_upper:
            raise ValueError(f"Invalid tick range: {tick_lower} >= {tick_upper}")

        # Convert to wei
        amount0_wei = self._to_wei(amount0, currency0)
        amount1_wei = self._to_wei(amount1, currency1)

        # Check balances
        balance0 = self._get_balance(currency0)
        balance1 = self._get_balance(currency1)

        if balance0 < amount0_wei:
            raise InsufficientBalanceError(
                f"Insufficient {self._get_token_symbol(currency0)} balance"
            )
        if balance1 < amount1_wei:
            raise InsufficientBalanceError(
                f"Insufficient {self._get_token_symbol(currency1)} balance"
            )

        # Approve ERC20 tokens (not needed for native ETH)
        if not is_native_eth(currency0):
            ERC20(self.manager, currency0).approve(
                self.position_manager.address, amount0_wei
            )
        if not is_native_eth(currency1):
            ERC20(self.manager, currency1).approve(
                self.position_manager.address, amount1_wei
            )

        # Create pool key
        pool_key = PoolKey(
            currency0=currency0,
            currency1=currency1,
            fee=fee,
            tick_spacing=tick_spacing,
            hooks=hooks,
        )

        # Get current pool state for liquidity calculation
        slot0 = self.state_view.get_slot0(pool_key)

        # Calculate liquidity from amounts
        liquidity = calculate_liquidity_from_amounts(
            slot0["sqrt_price_x96"],
            tick_lower,
            tick_upper,
            amount0_wei,
            amount1_wei,
        )

        # Calculate slippage
        amount0_min, amount1_min = calculate_slippage_amounts(
            amount0_wei, amount1_wei, slippage_bps
        )

        # Mint position
        result = self.position_manager.mint(
            pool_key=pool_key,
            tick_lower=tick_lower,
            tick_upper=tick_upper,
            liquidity=liquidity,
            amount0_max=amount0_wei,
            amount1_max=amount1_wei,
            recipient=self.manager.address,
        )

        return {
            "token_id": result["token_id"],
            "receipt": result["receipt"],
            "token0": self._get_token_symbol(currency0),
            "token1": self._get_token_symbol(currency1),
            "tick_lower": tick_lower,
            "tick_upper": tick_upper,
            "tokens_swapped": swapped,
            "uses_native_eth": is_native_eth(currency0) or is_native_eth(currency1),
        }

    def add_liquidity_range(
        self,
        token0,
        token1,
        fee,
        percent_lower,
        percent_upper,
        amount0,
        amount1,
        slippage_bps=50,
        hooks=ADDRESS_ZERO,
    ):
        """
        Add liquidity using percentage ranges around current price.
        """
        if percent_lower >= percent_upper:
            raise ValueError(
                f"Invalid percentage range: {percent_lower} >= {percent_upper}"
            )

        token0_addr = self._get_token_address(token0)
        token1_addr = self._get_token_address(token1)
        currency0, currency1 = sort_currencies(token0_addr, token1_addr)

        decimals0 = self._get_token_decimals(currency0)
        decimals1 = self._get_token_decimals(currency1)

        tick_spacing = self.config.get_tick_spacing(fee)
        pool_key = PoolKey(
            currency0=currency0,
            currency1=currency1,
            fee=fee,
            tick_spacing=tick_spacing,
            hooks=hooks,
        )

        slot0 = self.state_view.get_slot0(pool_key)
        current_price = tick_to_price(slot0["tick"], decimals0, decimals1)

        price_lower = current_price * (1 + percent_lower)
        price_upper = current_price * (1 + percent_upper)

        tick_lower = price_to_tick(price_lower, decimals0, decimals1)
        tick_upper = price_to_tick(price_upper, decimals0, decimals1)

        tick_lower = round_tick_to_spacing(tick_lower, tick_spacing)
        tick_upper = round_tick_to_spacing(tick_upper, tick_spacing)

        print(f"Current price: {current_price:.6f}")
        print(f"Price range: {price_lower:.6f} to {price_upper:.6f}")
        print(f"Tick range: {tick_lower} to {tick_upper}")

        result = self.add_liquidity(
            token0_addr,
            token1_addr,
            fee,
            tick_lower,
            tick_upper,
            amount0,
            amount1,
            slippage_bps,
            hooks,
        )

        result["current_price"] = current_price
        result["price_lower"] = price_lower
        result["price_upper"] = price_upper
        result["percent_lower"] = percent_lower
        result["percent_upper"] = percent_upper

        return result

    def remove_liquidity(self, token_id, percentage, collect_fees=True, burn=False, **kwargs):
        """
        Remove liquidity from a position.

        Args:
            token_id: Position NFT token ID
            percentage: Percentage of liquidity to remove (0-100)
            collect_fees: Whether to collect fees after removal
            burn: Whether to burn the position NFT (only for 100% removal)

        Returns:
            Dict with transaction receipts
        """
        owner = self.position_manager.owner_of(token_id)
        if owner.lower() != self.manager.address.lower():
            raise PositionError(
                f"Position {token_id} not owned by {self.manager.address}"
            )

        pos = self.position_manager.get_position(token_id)
        liquidity = pos["liquidity"]

        if liquidity == 0:
            raise PositionError(f"Position {token_id} has no liquidity")

        if percentage == 100:
            liquidity_to_remove = liquidity
        else:
            liquidity_to_remove = int(liquidity * percentage / 100)

        if liquidity_to_remove == 0:
            raise ValueError("Cannot remove 0 liquidity")

        result = {"token_id": token_id}

        # Decrease liquidity
        receipt = self.position_manager.decrease_liquidity(
            token_id, liquidity_to_remove
        )
        result["decrease_receipt"] = receipt

        # In V4, collect_fees is done via decrease_liquidity with 0 liquidity
        if collect_fees:
            collect_receipt = self.position_manager.collect_fees(token_id)
            result["collect_receipt"] = collect_receipt

        if burn:
            if percentage != 100:
                result["burn_skipped"] = "Can only burn when removing 100% liquidity"
            else:
                burn_receipt = self.position_manager.burn(token_id)
                result["burn_receipt"] = burn_receipt

        return result
