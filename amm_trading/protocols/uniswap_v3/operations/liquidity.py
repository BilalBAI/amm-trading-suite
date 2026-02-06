"""Liquidity management operations for Uniswap V3"""

import time
from ....core.connection import Web3Manager
from ..config import UniswapV3Config
from ....core.exceptions import InsufficientBalanceError, PositionError
from ....contracts.erc20 import ERC20
from ..contracts.nfpm import NFPM
from ..contracts.pool import Pool
from ..math import round_tick_to_spacing, calculate_slippage_amounts, price_to_tick, tick_to_price
from ...base import BaseLiquidityManager


class LiquidityManager(BaseLiquidityManager):
    """Manage Uniswap V3 liquidity positions"""

    # WETH address by chain - ETH symbol maps to this
    WETH_ADDRESSES = {
        1: "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",      # Mainnet
        5: "0xB4FBF271143F4FBf7B91A5ded31805e42b2208d6",      # Goerli
        11155111: "0xfFf9976782d46CC05630D1f6eBAb18b2324d6B14",  # Sepolia
        42161: "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",   # Arbitrum One
        10: "0x4200000000000000000000000000000000000006",      # Optimism
        137: "0x0d500B1d8E8eF31E21C99d1Db9A6444d3ADf1270",     # Polygon (WMATIC)
        8453: "0x4200000000000000000000000000000000000006",    # Base
    }

    def __init__(self, manager=None):
        """
        Args:
            manager: Web3Manager instance (created with signer if None)

        Gas parameters are loaded from gas_config.json.
        """
        self.manager = manager or Web3Manager(require_signer=True)
        self.config = UniswapV3Config()
        self.nfpm = NFPM(self.manager)

    def _get_token_address(self, symbol_or_address):
        """
        Get token address, mapping ETH to WETH.

        Args:
            symbol_or_address: Token symbol (e.g., "ETH", "WETH", "USDT") or address

        Returns:
            Checksummed token address
        """
        if symbol_or_address.upper() == "ETH":
            chain_id = self.manager.chain_id
            if chain_id not in self.WETH_ADDRESSES:
                raise ValueError(f"WETH address not configured for chain {chain_id}")
            return self.manager.checksum(self.WETH_ADDRESSES[chain_id])

        return self.manager.checksum(self.config.get_token_address(symbol_or_address))

    def _ensure_token_order(self, token0_addr, token1_addr, amount0, amount1):
        """Ensure token0 < token1 (Uniswap requirement)"""
        if int(token0_addr, 16) > int(token1_addr, 16):
            return token1_addr, token0_addr, amount1, amount0, True
        return token0_addr, token1_addr, amount0, amount1, False

    def calculate_optimal_amounts(
        self,
        token0,
        token1,
        fee,
        tick_lower,
        tick_upper,
        amount0_desired=None,
        amount1_desired=None,
    ):
        """
        Calculate optimal token amounts for a liquidity position.

        Given a tick range and one desired amount, calculates the optimal amount
        of the other token needed to match the current pool price ratio.

        Args:
            token0: Token0 symbol or address
            token1: Token1 symbol or address
            fee: Fee tier (500, 3000, 10000)
            tick_lower: Lower tick bound
            tick_upper: Upper tick bound
            amount0_desired: Desired amount of token0 (if None, calculated from amount1)
            amount1_desired: Desired amount of token1 (if None, calculated from amount0)

        Returns:
            Dict with optimal amounts and position details
        """
        if (amount0_desired is None and amount1_desired is None) or \
           (amount0_desired is not None and amount1_desired is not None):
            raise ValueError(
                "Must specify exactly one of amount0_desired or amount1_desired")

        # Resolve token addresses (ETH -> WETH mapping)
        token0_addr = self._get_token_address(token0)
        token1_addr = self._get_token_address(token1)

        # Ensure correct token order
        swapped = False
        if int(token0_addr, 16) > int(token1_addr, 16):
            token0_addr, token1_addr = token1_addr, token0_addr
            if amount0_desired is not None:
                amount1_desired = amount0_desired
                amount0_desired = None
            else:
                amount0_desired = amount1_desired
                amount1_desired = None
            swapped = True

        # Get token contracts
        token0_contract = ERC20(self.manager, token0_addr)
        token1_contract = ERC20(self.manager, token1_addr)

        # Get pool and current price
        factory_addr = self.config.factory_address
        factory_contract = self.manager.get_contract(
            factory_addr, "uniswap_v3_factory")
        pool_addr = factory_contract.functions.getPool(
            token0_addr, token1_addr, fee).call()

        if pool_addr == "0x0000000000000000000000000000000000000000":
            raise ValueError(
                f"Pool does not exist for {token0}/{token1} with fee {fee}")

        pool = Pool(self.manager, pool_addr)
        current_tick = pool.current_tick
        sqrt_price_x96 = pool.sqrt_price_x96

        # Calculate prices
        current_price = tick_to_price(
            current_tick, token0_contract.decimals, token1_contract.decimals)
        price_lower = tick_to_price(
            tick_lower, token0_contract.decimals, token1_contract.decimals)
        price_upper = tick_to_price(
            tick_upper, token0_contract.decimals, token1_contract.decimals)

        # Determine position type
        if current_tick < tick_lower:
            position_type = "below_range"
            if amount1_desired is not None:
                raise ValueError(
                    f"Current price (${current_price:.2f}) is below range (${price_lower:.2f}-${price_upper:.2f}). Only {token0_contract.symbol} is needed.")
            calculated_amount0 = amount0_desired
            calculated_amount1 = 0.0
        elif current_tick > tick_upper:
            position_type = "above_range"
            if amount0_desired is not None:
                raise ValueError(
                    f"Current price (${current_price:.2f}) is above range (${price_lower:.2f}-${price_upper:.2f}). Only {token1_contract.symbol} is needed.")
            calculated_amount0 = 0.0
            calculated_amount1 = amount1_desired
        else:
            position_type = "in_range"
            sqrt_price_raw = sqrt_price_x96 / (2 ** 96)
            sqrt_pl_raw = 1.0001 ** (tick_lower / 2)
            sqrt_pu_raw = 1.0001 ** (tick_upper / 2)

            decimal_adjustment = 10 ** ((token0_contract.decimals - token1_contract.decimals) / 2)
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
                "symbol": token0_contract.symbol,
                "address": token0_addr,
                "amount": calculated_amount0,
                "decimals": token0_contract.decimals,
            },
            "token1": {
                "symbol": token1_contract.symbol,
                "address": token1_addr,
                "amount": calculated_amount1,
                "decimals": token1_contract.decimals,
            },
            "current_price": current_price,
            "price_lower": price_lower,
            "price_upper": price_upper,
            "tick_lower": tick_lower,
            "tick_upper": tick_upper,
            "current_tick": current_tick,
            "ratio": f"1 {token0_contract.symbol} = {current_price:.2f} {token1_contract.symbol}",
            "position_type": position_type,
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
    ):
        """
        Calculate optimal amounts using percentage ranges.

        Convenience wrapper around calculate_optimal_amounts() that accepts
        percentage ranges instead of ticks.
        """
        token0_addr = self._get_token_address(token0)
        token1_addr = self._get_token_address(token1)

        if int(token0_addr, 16) > int(token1_addr, 16):
            token0_addr, token1_addr = token1_addr, token0_addr

        factory_addr = self.config.factory_address
        factory_contract = self.manager.get_contract(
            factory_addr, "uniswap_v3_factory")
        pool_addr = factory_contract.functions.getPool(
            token0_addr, token1_addr, fee).call()

        if pool_addr == "0x0000000000000000000000000000000000000000":
            raise ValueError(
                f"Pool does not exist for {token0}/{token1} with fee {fee}")

        pool = Pool(self.manager, pool_addr)
        token0_contract = ERC20(self.manager, token0_addr)
        token1_contract = ERC20(self.manager, token1_addr)

        current_price = pool.get_price(
            token0_contract.decimals, token1_contract.decimals)

        price_lower = current_price * (1 + percent_lower)
        price_upper = current_price * (1 + percent_upper)

        tick_lower = price_to_tick(
            price_lower, token0_contract.decimals, token1_contract.decimals)
        tick_upper = price_to_tick(
            price_upper, token0_contract.decimals, token1_contract.decimals)

        spacing = self.config.get_tick_spacing(fee)
        tick_lower = round_tick_to_spacing(tick_lower, spacing)
        tick_upper = round_tick_to_spacing(tick_upper, spacing)

        return self.calculate_optimal_amounts(
            token0, token1, fee, tick_lower, tick_upper,
            amount0_desired, amount1_desired
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
        **kwargs
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
        token0_addr = self._get_token_address(token0)
        token1_addr = self._get_token_address(token1)

        token0_addr, token1_addr, amount0, amount1, swapped = self._ensure_token_order(
            token0_addr, token1_addr, amount0, amount1
        )

        token0_contract = ERC20(self.manager, token0_addr)
        token1_contract = ERC20(self.manager, token1_addr)

        spacing = self.config.get_tick_spacing(fee)
        tick_lower = round_tick_to_spacing(tick_lower, spacing)
        tick_upper = round_tick_to_spacing(tick_upper, spacing)

        if tick_lower >= tick_upper:
            raise ValueError(
                f"Invalid tick range: {tick_lower} >= {tick_upper}")

        amount0_wei = token0_contract.to_wei(amount0)
        amount1_wei = token1_contract.to_wei(amount1)

        if token0_contract.balance_of() < amount0_wei:
            raise InsufficientBalanceError(
                f"Insufficient {token0_contract.symbol} balance")
        if token1_contract.balance_of() < amount1_wei:
            raise InsufficientBalanceError(
                f"Insufficient {token1_contract.symbol} balance")

        token0_contract.approve(self.nfpm.address, amount0_wei)
        token1_contract.approve(self.nfpm.address, amount1_wei)

        amount0_min, amount1_min = calculate_slippage_amounts(
            amount0_wei, amount1_wei, slippage_bps
        )

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
    ):
        """
        Add liquidity using percentage ranges around current price.
        """
        if percent_lower >= percent_upper:
            raise ValueError(
                f"Invalid percentage range: {percent_lower} >= {percent_upper}")

        token0_addr = self._get_token_address(token0)
        token1_addr = self._get_token_address(token1)

        if int(token0_addr, 16) > int(token1_addr, 16):
            token0_addr, token1_addr = token1_addr, token0_addr

        factory_addr = self.config.factory_address
        factory_contract = self.manager.get_contract(
            factory_addr, "uniswap_v3_factory")
        pool_addr = factory_contract.functions.getPool(
            token0_addr, token1_addr, fee).call()

        if pool_addr == "0x0000000000000000000000000000000000000000":
            raise ValueError(
                f"Pool does not exist for {token0}/{token1} with fee {fee}")

        pool = Pool(self.manager, pool_addr)
        token0_contract = ERC20(self.manager, token0_addr)
        token1_contract = ERC20(self.manager, token1_addr)

        current_price = pool.get_price(
            token0_contract.decimals, token1_contract.decimals)

        price_lower = current_price * (1 + percent_lower)
        price_upper = current_price * (1 + percent_upper)

        tick_lower = price_to_tick(
            price_lower, token0_contract.decimals, token1_contract.decimals)
        tick_upper = price_to_tick(
            price_upper, token0_contract.decimals, token1_contract.decimals)

        spacing = self.config.get_tick_spacing(fee)
        tick_lower = round_tick_to_spacing(tick_lower, spacing)
        tick_upper = round_tick_to_spacing(tick_upper, spacing)

        print(
            f"Current price: {current_price:.6f} {token1_contract.symbol}/{token0_contract.symbol}")
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
        owner = self.nfpm.owner_of(token_id)
        if owner.lower() != self.manager.address.lower():
            raise PositionError(
                f"Position {token_id} not owned by {self.manager.address}")

        pos = self.nfpm.get_position(token_id)
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

        receipt = self.nfpm.decrease_liquidity(token_id, liquidity_to_remove)
        result["decrease_receipt"] = receipt

        if collect_fees:
            collect_receipt = self.nfpm.collect(token_id)
            result["collect_receipt"] = collect_receipt

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
        """
        pos = self.nfpm.get_position(token_id)

        owner = self.nfpm.owner_of(token_id)
        if owner.lower() != self.manager.address.lower():
            raise PositionError(
                f"Position {token_id} not owned by {self.manager.address}")

        token0 = ERC20(self.manager, pos["token0"])
        token1 = ERC20(self.manager, pos["token1"])

        spacing = self.config.get_tick_spacing(pos["fee"])
        new_tick_lower = round_tick_to_spacing(new_tick_lower, spacing)
        new_tick_upper = round_tick_to_spacing(new_tick_upper, spacing)

        remove_result = self.remove_liquidity(
            token_id,
            percentage,
            collect_fees=collect_fees,
            burn=burn_old and percentage == 100,
        )

        balance0 = token0.balance_human()
        balance1 = token1.balance_human()

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
