"""Liquidity management operations"""

import time
from ..core.connection import Web3Manager
from ..core.config import Config
from ..core.exceptions import InsufficientBalanceError, PositionError
from ..contracts.nfpm import NFPM
from ..contracts.erc20 import ERC20
from ..utils.math import round_tick_to_spacing, calculate_slippage_amounts


class LiquidityManager:
    """Manage Uniswap V3 liquidity positions"""

    def __init__(self, manager=None):
        """
        Args:
            manager: Web3Manager instance (created with signer if None)
        """
        self.manager = manager or Web3Manager(require_signer=True)
        self.config = Config()
        self.nfpm = NFPM(self.manager)

    def _ensure_token_order(self, token0_addr, token1_addr, amount0, amount1):
        """Ensure token0 < token1 (Uniswap requirement)"""
        if int(token0_addr, 16) > int(token1_addr, 16):
            return token1_addr, token0_addr, amount1, amount0, True
        return token0_addr, token1_addr, amount0, amount1, False

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
    ):
        """
        Add liquidity to a Uniswap V3 pool.

        Args:
            token0: Token0 symbol or address
            token1: Token1 symbol or address
            fee: Fee tier (500, 3000, 10000)
            tick_lower: Lower tick bound
            tick_upper: Upper tick bound
            amount0: Amount of token0 (human readable)
            amount1: Amount of token1 (human readable)
            slippage_bps: Slippage tolerance in basis points

        Returns:
            Dict with receipt and token_id
        """
        # Resolve token addresses
        token0_addr = self.manager.checksum(self.config.get_token_address(token0))
        token1_addr = self.manager.checksum(self.config.get_token_address(token1))

        # Ensure correct token order
        token0_addr, token1_addr, amount0, amount1, swapped = self._ensure_token_order(
            token0_addr, token1_addr, amount0, amount1
        )

        # Get token contracts
        token0_contract = ERC20(self.manager, token0_addr)
        token1_contract = ERC20(self.manager, token1_addr)

        # Adjust ticks to spacing
        spacing = self.config.get_tick_spacing(fee)
        tick_lower = round_tick_to_spacing(tick_lower, spacing)
        tick_upper = round_tick_to_spacing(tick_upper, spacing)

        if tick_lower >= tick_upper:
            raise ValueError(f"Invalid tick range: {tick_lower} >= {tick_upper}")

        # Convert amounts to wei
        amount0_wei = token0_contract.to_wei(amount0)
        amount1_wei = token1_contract.to_wei(amount1)

        # Check balances
        if token0_contract.balance_of() < amount0_wei:
            raise InsufficientBalanceError(f"Insufficient {token0_contract.symbol} balance")
        if token1_contract.balance_of() < amount1_wei:
            raise InsufficientBalanceError(f"Insufficient {token1_contract.symbol} balance")

        # Approve tokens
        token0_contract.approve(self.nfpm.address, amount0_wei)
        token1_contract.approve(self.nfpm.address, amount1_wei)

        # Calculate min amounts with slippage
        amount0_min, amount1_min = calculate_slippage_amounts(
            amount0_wei, amount1_wei, slippage_bps
        )

        # Mint position
        params = {
            "token0": token0_addr,
            "token1": token1_addr,
            "fee": fee,
            "tick_lower": tick_lower,
            "tick_upper": tick_upper,
            "amount0_desired": amount0_wei,
            "amount1_desired": amount1_wei,
            "amount0_min": amount0_min,
            "amount1_min": amount1_min,
            "recipient": self.manager.address,
            "deadline": int(time.time()) + 1800,
        }

        result = self.nfpm.mint(params)

        return {
            "token_id": result["token_id"],
            "receipt": result["receipt"],
            "token0": token0_contract.symbol,
            "token1": token1_contract.symbol,
            "tick_lower": tick_lower,
            "tick_upper": tick_upper,
            "tokens_swapped": swapped,
        }

    def remove_liquidity(self, token_id, percentage, collect_fees=True, burn=False):
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
        # Verify ownership
        owner = self.nfpm.owner_of(token_id)
        if owner.lower() != self.manager.address.lower():
            raise PositionError(f"Position {token_id} not owned by {self.manager.address}")

        # Get position info
        pos = self.nfpm.get_position(token_id)
        liquidity = pos["liquidity"]

        if liquidity == 0:
            raise PositionError(f"Position {token_id} has no liquidity")

        # Calculate liquidity to remove
        if percentage == 100:
            liquidity_to_remove = liquidity
        else:
            liquidity_to_remove = int(liquidity * percentage / 100)

        if liquidity_to_remove == 0:
            raise ValueError("Cannot remove 0 liquidity")

        result = {"token_id": token_id}

        # Decrease liquidity
        receipt = self.nfpm.decrease_liquidity(token_id, liquidity_to_remove)
        result["decrease_receipt"] = receipt

        # Collect tokens and fees
        if collect_fees:
            collect_receipt = self.nfpm.collect(token_id)
            result["collect_receipt"] = collect_receipt

        # Burn position if requested and 100% removed
        if burn:
            if percentage != 100:
                result["burn_skipped"] = "Can only burn when removing 100% liquidity"
            else:
                burn_receipt = self.nfpm.burn(token_id)
                result["burn_receipt"] = burn_receipt

        return result

    def migrate_liquidity(
        self,
        token_id,
        new_tick_lower,
        new_tick_upper,
        percentage=100,
        collect_fees=True,
        burn_old=False,
        slippage_bps=50,
    ):
        """
        Migrate liquidity to a new tick range.

        Args:
            token_id: Position NFT token ID
            new_tick_lower: New lower tick
            new_tick_upper: New upper tick
            percentage: Percentage of liquidity to migrate
            collect_fees: Whether to collect fees before migration
            burn_old: Whether to burn old position (only for 100%)
            slippage_bps: Slippage tolerance

        Returns:
            Dict with old and new position info
        """
        # Get old position info
        pos = self.nfpm.get_position(token_id)

        # Verify ownership
        owner = self.nfpm.owner_of(token_id)
        if owner.lower() != self.manager.address.lower():
            raise PositionError(f"Position {token_id} not owned by {self.manager.address}")

        # Get tokens
        token0 = ERC20(self.manager, pos["token0"])
        token1 = ERC20(self.manager, pos["token1"])

        # Adjust new ticks to spacing
        spacing = self.config.get_tick_spacing(pos["fee"])
        new_tick_lower = round_tick_to_spacing(new_tick_lower, spacing)
        new_tick_upper = round_tick_to_spacing(new_tick_upper, spacing)

        # Remove from old position
        remove_result = self.remove_liquidity(
            token_id,
            percentage,
            collect_fees=collect_fees,
            burn=burn_old and percentage == 100,
        )

        # Get current token balances (what we collected)
        balance0 = token0.balance_human()
        balance1 = token1.balance_human()

        # Add to new position
        add_result = self.add_liquidity(
            token0.address,
            token1.address,
            pos["fee"],
            new_tick_lower,
            new_tick_upper,
            balance0,
            balance1,
            slippage_bps,
        )

        return {
            "old_token_id": token_id,
            "new_token_id": add_result["token_id"],
            "old_range": (pos["tick_lower"], pos["tick_upper"]),
            "new_range": (new_tick_lower, new_tick_upper),
            "percentage_migrated": percentage,
            "remove_result": remove_result,
            "add_result": add_result,
        }
