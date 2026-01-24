"""Token swap operations"""

import time
from web3 import Web3

from ..core.connection import Web3Manager
from ..core.config import Config
from ..core.exceptions import ConfigError, InsufficientBalanceError
from ..contracts.erc20 import ERC20


class SwapManager:
    """Execute token swaps on Uniswap V3"""

    # WETH address for ETH wrapping
    WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"

    def __init__(self, manager=None):
        """
        Args:
            manager: Web3Manager instance (created with signer if None)
        """
        self.manager = manager or Web3Manager(require_signer=True)
        self.config = Config()
        self.router_address = self.manager.checksum(self.config.router_address)
        self.router = self.manager.get_contract(self.router_address, "uniswap_v3_router")

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

    def swap(
        self,
        token_in,
        token_out,
        pool_name,
        amount_in,
        slippage_bps=50,
        max_gas_price_gwei=None,
        deadline_minutes=30,
    ):
        """
        Swap tokens using a specific pool.

        Args:
            token_in: Token to send (symbol like 'ETH', 'WETH', 'USDT' or address)
            token_out: Token to receive (symbol or address)
            pool_name: Pool name in format 'TOKEN0_TOKEN1_FEE' (e.g., 'WETH_USDT_30')
            amount_in: Amount of token_in to swap (human readable)
            slippage_bps: Slippage tolerance in basis points (default: 50 = 0.5%)
            max_gas_price_gwei: Maximum gas price in gwei (None = use current)
            deadline_minutes: Transaction deadline in minutes (default: 30)

        Returns:
            Dict with transaction details and amounts
        """
        # Parse pool name to get fee
        pool_token0, pool_token1, fee = self._parse_pool_name(pool_name)

        # Resolve token addresses
        token_in_addr = self._get_token_address(token_in)
        token_out_addr = self._get_token_address(token_out)

        # Create token contracts
        token_in_contract = ERC20(self.manager, token_in_addr)
        token_out_contract = ERC20(self.manager, token_out_addr)

        # Convert amount to wei
        amount_in_wei = token_in_contract.to_wei(amount_in)

        # Check balance
        balance = token_in_contract.balance_of()
        if balance < amount_in_wei:
            raise InsufficientBalanceError(
                f"Insufficient {token_in_contract.symbol} balance. "
                f"Have: {token_in_contract.from_wei(balance):.6f}, Need: {amount_in}"
            )

        # Get current price to estimate output
        # For now, we'll set amountOutMinimum based on slippage
        # In production, you'd want to get the actual price from the pool
        amount_out_min = 0  # Will be set after we estimate

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

        # Approve router to spend tokens
        approval = token_in_contract.approve(self.router_address, amount_in_wei)

        # Build swap params
        deadline = int(time.time()) + (deadline_minutes * 60)

        swap_params = (
            token_in_addr,           # tokenIn
            token_out_addr,          # tokenOut
            fee,                     # fee
            self.manager.address,    # recipient
            deadline,                # deadline
            amount_in_wei,           # amountIn
            amount_out_min,          # amountOutMinimum (0 for now, will estimate)
            0,                       # sqrtPriceLimitX96 (0 = no limit)
        )

        # Estimate gas and get expected output
        # First, simulate the swap to get expected output
        try:
            expected_out = self.router.functions.exactInputSingle(swap_params).call({
                "from": self.manager.address
            })
        except Exception as e:
            raise ValueError(
                f"Failed to estimate swap output. The swap may fail due to: "
                f"insufficient liquidity, invalid pool, or token issues. Error: {e}"
            )

        if expected_out == 0:
            raise ValueError(
                "Swap would return 0 tokens. Check pool liquidity and token addresses."
            )

        # Calculate minimum output with slippage protection
        slippage_multiplier = (10000 - slippage_bps) / 10000
        amount_out_min = int(expected_out * slippage_multiplier)

        if amount_out_min == 0:
            raise ValueError(
                f"Minimum output is 0 after {slippage_bps/100}% slippage. "
                f"Expected output too small or slippage too high."
            )

        # Rebuild params with actual minimum
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

        # Estimate gas
        try:
            gas_estimate = self.router.functions.exactInputSingle(swap_params).estimate_gas({
                "from": self.manager.address
            })
        except Exception as e:
            raise ValueError(
                f"Failed to estimate gas. The swap may revert. Error: {e}"
            )

        # Build transaction
        tx = self.router.functions.exactInputSingle(swap_params).build_transaction({
            "from": self.manager.address,
            "nonce": self.manager.get_nonce(),
            "gas": int(gas_estimate * 1.2),
            "gasPrice": gas_price,
            "chainId": self.manager.chain_id,
        })

        # Sign and send
        signed = self.manager.account.sign_transaction(tx)
        tx_hash = self.manager.w3.eth.send_raw_transaction(signed.rawTransaction)

        # Wait for receipt
        receipt = self.manager.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status != 1:
            raise Exception(f"Swap failed: {tx_hash.hex()}")

        # Get actual output from logs (Swap event)
        # For simplicity, return the expected output
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
