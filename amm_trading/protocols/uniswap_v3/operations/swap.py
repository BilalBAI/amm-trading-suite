"""Token swap operations for Uniswap V3"""

import time
from web3 import Web3

from ....core.connection import Web3Manager
from ..config import UniswapV3Config
from ....core.exceptions import ConfigError, InsufficientBalanceError
from ....contracts.erc20 import ERC20
from ...base import BaseSwapManager


class SwapManager(BaseSwapManager):
    """Execute token swaps on Uniswap V3"""

    # WETH address for ETH wrapping
    WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

    def __init__(self, manager=None, require_signer=True):
        """
        Args:
            manager: Web3Manager instance (created with signer if None)
            require_signer: If True, require private key for transactions
        """
        self.manager = manager or Web3Manager(require_signer=require_signer)
        self.config = UniswapV3Config()
        self.router_address = self.manager.checksum(self.config.router_address)
        self.router = self.manager.get_contract(self.router_address, "uniswap_v3_router")
        self.quoter_address = self.manager.checksum(self.config.quoter_address)
        self.quoter = self.manager.get_contract(self.quoter_address, "uniswap_v3_quoter")

    def _parse_pool_name(self, pool_name):
        """
        Parse pool name like 'WETH_USDT_30' into (token0, token1, fee).
        Returns (token0_symbol, token1_symbol, fee)
        """
        parts = pool_name.split("_")
        if len(parts) != 3:
            raise ConfigError(f"Invalid pool name format: {pool_name}. Expected: TOKEN0_TOKEN1_FEE")

        token0_symbol = parts[0]
        token1_symbol = parts[1]
        try:
            fee = int(parts[2]) * 100  # Convert 30 -> 3000
        except ValueError:
            raise ConfigError(f"Invalid fee in pool name: {parts[2]}")

        return token0_symbol, token1_symbol, fee

    def _get_token_address(self, symbol):
        """Get token address from symbol, handling ETH -> WETH conversion"""
        if symbol.upper() == "ETH":
            return self.WETH
        return self.manager.checksum(self.config.get_token_address(symbol))

    def quote(self, token_in, token_out, amount_in, pool_name=None, **kwargs):
        """
        Get a quote for a swap without executing.

        Args:
            token_in: Token to send (symbol or address)
            token_out: Token to receive (symbol or address)
            amount_in: Amount of token_in to swap (human readable)
            pool_name: Pool name in format 'TOKEN0_TOKEN1_FEE'

        Returns:
            Dict with quote details including expected output, price, and gas estimate
        """
        if pool_name is None:
            raise ValueError("pool_name is required for Uniswap V3 quotes")

        pool_token0, pool_token1, fee = self._parse_pool_name(pool_name)

        token_in_addr = self._get_token_address(token_in)
        token_out_addr = self._get_token_address(token_out)

        token_in_contract = ERC20(self.manager, token_in_addr)
        token_out_contract = ERC20(self.manager, token_out_addr)

        amount_in_wei = token_in_contract.to_wei(amount_in)

        try:
            balance = token_in_contract.balance_of()
            has_sufficient_balance = balance >= amount_in_wei
            balance_human = token_in_contract.from_wei(balance)
        except Exception:
            balance = 0
            has_sufficient_balance = None
            balance_human = None

        quote_params = (
            token_in_addr,
            token_out_addr,
            amount_in_wei,
            fee,
            0,
        )

        try:
            result = self.quoter.functions.quoteExactInputSingle(quote_params).call()
            expected_out = result[0]
            sqrt_price_after = result[1]
            ticks_crossed = result[2]
            gas_estimate = result[3]
        except Exception as e:
            raise ValueError(f"Quote failed: {e}")

        amount_out_human = token_out_contract.from_wei(expected_out)
        price = amount_out_human / amount_in if amount_in > 0 else 0
        inverse_price = amount_in / amount_out_human if amount_out_human > 0 else 0

        gas_price = self.manager.get_gas_price()
        total_gas_estimate = gas_estimate + 50000
        gas_cost_wei = total_gas_estimate * gas_price
        gas_cost_eth = float(Web3.from_wei(gas_cost_wei, "ether"))

        return {
            "token_in": {
                "symbol": token_in_contract.symbol,
                "address": token_in_addr,
                "amount": amount_in,
                "balance": balance_human,
                "sufficient_balance": has_sufficient_balance,
            },
            "token_out": {
                "symbol": token_out_contract.symbol,
                "address": token_out_addr,
                "expected_amount": amount_out_human,
            },
            "price": {
                "rate": price,
                "rate_formatted": f"1 {token_in_contract.symbol} = {price:.6f} {token_out_contract.symbol}",
                "inverse": inverse_price,
                "inverse_formatted": f"1 {token_out_contract.symbol} = {inverse_price:.6f} {token_in_contract.symbol}",
            },
            "pool": pool_name,
            "fee": fee,
            "fee_percent": f"{fee/10000}%",
            "ticks_crossed": ticks_crossed,
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
        Swap tokens using a specific pool.

        Args:
            token_in: Token to send (symbol or address)
            token_out: Token to receive (symbol or address)
            amount_in: Amount of token_in to swap (human readable)
            pool_name: Pool name in format 'TOKEN0_TOKEN1_FEE'
            slippage_bps: Slippage tolerance in basis points (default: 50 = 0.5%)
            max_gas_price_gwei: Maximum gas price in gwei (None = use current)
            deadline_minutes: Transaction deadline in minutes (default: 30)
            dry_run: If True, simulate the swap without executing

        Returns:
            Dict with transaction details and amounts
        """
        if pool_name is None:
            raise ValueError("pool_name is required for Uniswap V3 swaps")

        pool_token0, pool_token1, fee = self._parse_pool_name(pool_name)

        token_in_addr = self._get_token_address(token_in)
        token_out_addr = self._get_token_address(token_out)

        token_in_contract = ERC20(self.manager, token_in_addr)
        token_out_contract = ERC20(self.manager, token_out_addr)

        amount_in_wei = token_in_contract.to_wei(amount_in)

        balance = token_in_contract.balance_of()
        has_sufficient_balance = balance >= amount_in_wei

        if not has_sufficient_balance and not dry_run:
            raise InsufficientBalanceError(
                f"Insufficient {token_in_contract.symbol} balance. "
                f"Have: {token_in_contract.from_wei(balance):.6f}, Need: {amount_in}"
            )

        amount_out_min = 0

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

        quote_params = (
            token_in_addr,
            token_out_addr,
            amount_in_wei,
            fee,
            0,
        )

        try:
            quote_result = self.quoter.functions.quoteExactInputSingle(quote_params).call()
            expected_out = quote_result[0]
            gas_estimate = quote_result[3]
        except Exception as e:
            raise ValueError(
                f"Failed to estimate swap output. The swap may fail due to: "
                f"insufficient liquidity, invalid pool, or token issues. Error: {e}"
            )

        if expected_out == 0:
            raise ValueError(
                "Swap would return 0 tokens. Check pool liquidity and token addresses."
            )

        slippage_multiplier = (10000 - slippage_bps) / 10000
        amount_out_min = int(expected_out * slippage_multiplier)

        if amount_out_min == 0:
            raise ValueError(
                f"Minimum output is 0 after {slippage_bps/100}% slippage. "
                f"Expected output too small or slippage too high."
            )

        gas_estimate = gas_estimate + 80000

        gas_cost_wei = gas_estimate * gas_price
        gas_cost_eth = float(Web3.from_wei(gas_cost_wei, "ether"))

        if dry_run:
            return {
                "dry_run": True,
                "status": "SIMULATION - No transaction sent",
                "token_in": {
                    "symbol": token_in_contract.symbol,
                    "address": token_in_addr,
                    "amount": amount_in,
                    "amount_wei": str(amount_in_wei),
                    "balance": token_in_contract.from_wei(balance),
                    "sufficient_balance": has_sufficient_balance,
                },
                "token_out": {
                    "symbol": token_out_contract.symbol,
                    "address": token_out_addr,
                    "expected_amount": token_out_contract.from_wei(expected_out),
                    "min_amount": token_out_contract.from_wei(amount_out_min),
                },
                "price": {
                    "rate": token_out_contract.from_wei(expected_out) / amount_in if amount_in > 0 else 0,
                    "formatted": f"1 {token_in_contract.symbol} = {token_out_contract.from_wei(expected_out) / amount_in:.6f} {token_out_contract.symbol}" if amount_in > 0 else "N/A",
                },
                "pool": pool_name,
                "fee": fee,
                "slippage_bps": slippage_bps,
                "gas": {
                    "estimate": gas_estimate,
                    "price_gwei": float(Web3.from_wei(gas_price, "gwei")),
                    "cost_eth": gas_cost_eth,
                },
            }

        token_in_contract.approve(self.router_address, amount_in_wei)

        swap_params = (
            token_in_addr,
            token_out_addr,
            fee,
            self.manager.address,
            deadline,
            amount_in_wei,
            amount_out_min,
            0,
        )

        tx = self.router.functions.exactInputSingle(swap_params).build_transaction({
            "from": self.manager.address,
            "nonce": self.manager.get_nonce(),
            "gas": int(gas_estimate * 1.2),
            "gasPrice": gas_price,
            "chainId": self.manager.chain_id,
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
                "symbol": token_in_contract.symbol,
                "address": token_in_addr,
                "amount": amount_in,
                "amount_wei": str(amount_in_wei),
            },
            "token_out": {
                "symbol": token_out_contract.symbol,
                "address": token_out_addr,
                "expected_amount": token_out_contract.from_wei(expected_out),
                "min_amount": token_out_contract.from_wei(amount_out_min),
            },
            "pool": pool_name,
            "fee": fee,
            "slippage_bps": slippage_bps,
            "gas_used": receipt.gasUsed,
            "gas_price_gwei": Web3.from_wei(gas_price, "gwei"),
        }
