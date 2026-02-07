"""Token swap operations for Uniswap V4"""

import time
from web3 import Web3

from ....core.connection import Web3Manager
from ..config import UniswapV4Config
from ....core.exceptions import ConfigError, InsufficientBalanceError
from ....contracts.erc20 import ERC20
from ..contracts.quoter import Quoter
from ..types import PoolKey, ADDRESS_ZERO, create_pool_key, is_native_eth, sort_currencies
from ...base import BaseSwapManager


class SwapManager(BaseSwapManager):
    """
    Execute token swaps on Uniswap V4.

    Key differences from V3:
    - Native ETH support (no WETH wrapping required)
    - Uses PoolKey for pool identification
    - Swaps go through Universal Router
    """

    def __init__(self, manager=None, require_signer=True):
        """
        Args:
            manager: Web3Manager instance
            require_signer: If True, require private key for transactions
        """
        self.manager = manager or Web3Manager(require_signer=require_signer)
        self.config = UniswapV4Config()
        self.quoter = Quoter(self.manager)
        self.router_address = self.manager.checksum(self.config.universal_router_address)
        self.router = self.manager.get_contract(self.router_address, "universalRouter")

    def _parse_pool_name(self, pool_name):
        """
        Parse pool name like 'ETH_USDC_30' into PoolKey.

        Returns PoolKey
        """
        parts = pool_name.split("_")
        if len(parts) < 3:
            raise ConfigError(
                f"Invalid pool name format: {pool_name}. Expected: TOKEN0_TOKEN1_FEE"
            )

        token0_symbol = parts[0]
        token1_symbol = parts[1]
        try:
            fee = int(parts[2]) * 100  # Convert 30 -> 3000
        except ValueError:
            raise ConfigError(f"Invalid fee in pool name: {parts[2]}")

        token0_addr = self._get_token_address(token0_symbol)
        token1_addr = self._get_token_address(token1_symbol)

        return create_pool_key(token0_addr, token1_addr, fee)

    def _get_token_address(self, symbol):
        """Get token address, handling ETH -> ADDRESS_ZERO"""
        if symbol.upper() == "ETH":
            return ADDRESS_ZERO
        return self.manager.checksum(self.config.get_token_address(symbol))

    def _get_token_info(self, address):
        """Get token info, handling native ETH"""
        if is_native_eth(address):
            return {"symbol": "ETH", "decimals": 18, "address": ADDRESS_ZERO}
        token = ERC20(self.manager, address)
        return {
            "symbol": token.symbol,
            "decimals": token.decimals,
            "address": address,
        }

    def _to_wei(self, amount, decimals):
        """Convert human amount to wei"""
        return int(amount * (10 ** decimals))

    def _from_wei(self, amount_wei, decimals):
        """Convert wei to human amount"""
        return amount_wei / (10 ** decimals)

    def _get_balance(self, address):
        """Get balance in wei (native ETH or ERC20)"""
        if is_native_eth(address):
            return self.manager.w3.eth.get_balance(self.manager.address)
        return ERC20(self.manager, address).balance_of()

    def quote(self, token_in, token_out, amount_in, pool_name=None, **kwargs):
        """
        Get a quote for a swap without executing.

        Args:
            token_in: Token to send (symbol or address, 'ETH' for native)
            token_out: Token to receive
            amount_in: Amount of token_in to swap (human readable)
            pool_name: Pool name in format 'TOKEN0_TOKEN1_FEE'

        Returns:
            Dict with quote details
        """
        if pool_name is None:
            raise ValueError("pool_name is required for Uniswap V4 quotes")

        pool_key = self._parse_pool_name(pool_name)

        token_in_addr = self._get_token_address(token_in)
        token_out_addr = self._get_token_address(token_out)

        token_in_info = self._get_token_info(token_in_addr)
        token_out_info = self._get_token_info(token_out_addr)

        amount_in_wei = self._to_wei(amount_in, token_in_info["decimals"])

        # Determine swap direction
        zero_for_one = token_in_addr.lower() == pool_key.currency0.lower()

        # Check balance
        try:
            balance = self._get_balance(token_in_addr)
            has_sufficient_balance = balance >= amount_in_wei
            balance_human = self._from_wei(balance, token_in_info["decimals"])
        except Exception:
            balance = 0
            has_sufficient_balance = None
            balance_human = None

        # Get quote
        result = self.quoter.quote_exact_input_single(
            pool_key=pool_key,
            zero_for_one=zero_for_one,
            amount_in=amount_in_wei,
        )

        amount_out_human = self._from_wei(
            result["amount_out"], token_out_info["decimals"]
        )
        price = amount_out_human / amount_in if amount_in > 0 else 0
        inverse_price = amount_in / amount_out_human if amount_out_human > 0 else 0

        gas_price = self.manager.get_gas_price()
        total_gas_estimate = result["gas_estimate"] + 50000
        gas_cost_wei = total_gas_estimate * gas_price
        gas_cost_eth = float(Web3.from_wei(gas_cost_wei, "ether"))

        return {
            "token_in": {
                "symbol": token_in_info["symbol"],
                "address": token_in_addr,
                "amount": amount_in,
                "balance": balance_human,
                "sufficient_balance": has_sufficient_balance,
                "is_native_eth": is_native_eth(token_in_addr),
            },
            "token_out": {
                "symbol": token_out_info["symbol"],
                "address": token_out_addr,
                "expected_amount": amount_out_human,
                "is_native_eth": is_native_eth(token_out_addr),
            },
            "price": {
                "rate": price,
                "rate_formatted": f"1 {token_in_info['symbol']} = {price:.6f} {token_out_info['symbol']}",
                "inverse": inverse_price,
                "inverse_formatted": f"1 {token_out_info['symbol']} = {inverse_price:.6f} {token_in_info['symbol']}",
            },
            "pool": pool_name,
            "pool_key": {
                "currency0": pool_key.currency0,
                "currency1": pool_key.currency1,
                "fee": pool_key.fee,
                "tick_spacing": pool_key.tick_spacing,
                "hooks": pool_key.hooks,
            },
            "fee": pool_key.fee,
            "fee_percent": f"{pool_key.fee/10000}%",
            "gas": {
                "estimate": total_gas_estimate,
                "price_gwei": float(Web3.from_wei(gas_price, "gwei")),
                "cost_eth": gas_cost_eth,
            },
        }

    def swap(
        self,
        token_in,
        token_out,
        amount_in,
        pool_name=None,
        slippage_bps=50,
        max_gas_price_gwei=None,
        deadline_minutes=30,
        dry_run=False,
        **kwargs
    ):
        """
        Swap tokens using a V4 pool.

        V4 supports native ETH - no WETH wrapping needed!

        Args:
            token_in: Token to send (symbol or address, 'ETH' for native)
            token_out: Token to receive
            amount_in: Amount of token_in to swap (human readable)
            pool_name: Pool name in format 'TOKEN0_TOKEN1_FEE'
            slippage_bps: Slippage tolerance in basis points
            max_gas_price_gwei: Maximum gas price in gwei
            deadline_minutes: Transaction deadline in minutes
            dry_run: If True, simulate without executing

        Returns:
            Dict with transaction details
        """
        if pool_name is None:
            raise ValueError("pool_name is required for Uniswap V4 swaps")

        pool_key = self._parse_pool_name(pool_name)

        token_in_addr = self._get_token_address(token_in)
        token_out_addr = self._get_token_address(token_out)

        token_in_info = self._get_token_info(token_in_addr)
        token_out_info = self._get_token_info(token_out_addr)

        amount_in_wei = self._to_wei(amount_in, token_in_info["decimals"])

        # Determine swap direction
        zero_for_one = token_in_addr.lower() == pool_key.currency0.lower()

        # Check balance
        balance = self._get_balance(token_in_addr)
        has_sufficient_balance = balance >= amount_in_wei

        if not has_sufficient_balance and not dry_run:
            raise InsufficientBalanceError(
                f"Insufficient {token_in_info['symbol']} balance. "
                f"Have: {self._from_wei(balance, token_in_info['decimals']):.6f}, Need: {amount_in}"
            )

        # Check gas price
        current_gas_price = self.manager.get_gas_price()
        if max_gas_price_gwei:
            max_gas_price_wei = Web3.to_wei(max_gas_price_gwei, "gwei")
            if current_gas_price > max_gas_price_wei:
                raise ValueError(
                    f"Current gas price ({Web3.from_wei(current_gas_price, 'gwei'):.2f} gwei) "
                    f"exceeds max ({max_gas_price_gwei} gwei)"
                )
            gas_price = min(current_gas_price, max_gas_price_wei)
        else:
            gas_price = current_gas_price

        deadline = int(time.time()) + (deadline_minutes * 60)

        # Get quote for expected output
        quote_result = self.quoter.quote_exact_input_single(
            pool_key=pool_key,
            zero_for_one=zero_for_one,
            amount_in=amount_in_wei,
        )

        expected_out = quote_result["amount_out"]
        gas_estimate = quote_result["gas_estimate"]

        if expected_out == 0:
            raise ValueError(
                "Swap would return 0 tokens. Check pool liquidity and token addresses."
            )

        # Calculate slippage
        slippage_multiplier = (10000 - slippage_bps) / 10000
        amount_out_min = int(expected_out * slippage_multiplier)

        if amount_out_min == 0:
            raise ValueError(
                f"Minimum output is 0 after {slippage_bps/100}% slippage."
            )

        gas_estimate = gas_estimate + 80000
        gas_cost_wei = gas_estimate * gas_price
        gas_cost_eth = float(Web3.from_wei(gas_cost_wei, "ether"))

        if dry_run:
            return {
                "dry_run": True,
                "status": "SIMULATION - No transaction sent",
                "token_in": {
                    "symbol": token_in_info["symbol"],
                    "address": token_in_addr,
                    "amount": amount_in,
                    "amount_wei": str(amount_in_wei),
                    "balance": self._from_wei(balance, token_in_info["decimals"]),
                    "sufficient_balance": has_sufficient_balance,
                    "is_native_eth": is_native_eth(token_in_addr),
                },
                "token_out": {
                    "symbol": token_out_info["symbol"],
                    "address": token_out_addr,
                    "expected_amount": self._from_wei(expected_out, token_out_info["decimals"]),
                    "min_amount": self._from_wei(amount_out_min, token_out_info["decimals"]),
                    "is_native_eth": is_native_eth(token_out_addr),
                },
                "price": {
                    "rate": self._from_wei(expected_out, token_out_info["decimals"]) / amount_in if amount_in > 0 else 0,
                    "formatted": f"1 {token_in_info['symbol']} = {self._from_wei(expected_out, token_out_info['decimals']) / amount_in:.6f} {token_out_info['symbol']}" if amount_in > 0 else "N/A",
                },
                "pool": pool_name,
                "fee": pool_key.fee,
                "slippage_bps": slippage_bps,
                "gas": {
                    "estimate": gas_estimate,
                    "price_gwei": float(Web3.from_wei(gas_price, "gwei")),
                    "cost_eth": gas_cost_eth,
                },
            }

        # Approve ERC20 tokens (not needed for native ETH)
        if not is_native_eth(token_in_addr):
            ERC20(self.manager, token_in_addr).approve(
                self.router_address, amount_in_wei
            )

        # Build swap through Universal Router
        # V4_SWAP command = 0x10 in Universal Router
        from ..encoding import encode_swap_exact_in_single

        swap_params = encode_swap_exact_in_single(
            pool_key=pool_key,
            zero_for_one=zero_for_one,
            amount_in=amount_in_wei,
            amount_out_minimum=amount_out_min,
        )

        # Universal Router execute command
        commands = bytes([0x10])  # V4_SWAP command
        inputs = [swap_params]

        # Value to send (for native ETH input)
        value = amount_in_wei if is_native_eth(token_in_addr) else 0

        tx = self.router.functions.execute(
            commands, inputs, deadline
        ).build_transaction({
            "from": self.manager.address,
            "nonce": self.manager.get_nonce(),
            "gas": int(gas_estimate * 1.2),
            "gasPrice": gas_price,
            "chainId": self.manager.chain_id,
            "value": value,
        })

        signed = self.manager.account.sign_transaction(tx)
        tx_hash = self.manager.w3.eth.send_raw_transaction(signed.raw_transaction)

        receipt = self.manager.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status != 1:
            raise Exception(f"Swap failed: {tx_hash.hex()}")

        return {
            "tx_hash": tx_hash.hex(),
            "block": receipt.blockNumber,
            "token_in": {
                "symbol": token_in_info["symbol"],
                "address": token_in_addr,
                "amount": amount_in,
                "amount_wei": str(amount_in_wei),
                "is_native_eth": is_native_eth(token_in_addr),
            },
            "token_out": {
                "symbol": token_out_info["symbol"],
                "address": token_out_addr,
                "expected_amount": self._from_wei(expected_out, token_out_info["decimals"]),
                "min_amount": self._from_wei(amount_out_min, token_out_info["decimals"]),
                "is_native_eth": is_native_eth(token_out_addr),
            },
            "pool": pool_name,
            "fee": pool_key.fee,
            "slippage_bps": slippage_bps,
            "gas_used": receipt.gasUsed,
            "gas_price_gwei": Web3.from_wei(gas_price, "gwei"),
        }
