"""Uniswap V4 Position Manager contract wrapper"""

import time
from eth_abi import encode
from web3 import Web3

from ..config import UniswapV4Config
from ..types import PoolKey, ADDRESS_ZERO, is_native_eth
from ..encoding import (
    encode_mint_position,
    encode_mint_position_with_native_eth,
    encode_decrease_liquidity,
    encode_collect_fees,
    encode_burn_position,
)
from ....core.exceptions import PositionError
from ....utils.gas import GasManager
from ....utils.transactions import TransactionBuilder


class PositionManager:
    """
    Wrapper for Uniswap V4 Position Manager interactions.

    V4's Position Manager uses an encoded action system where multiple
    operations are batched together via modifyLiquidities().

    Key differences from V3:
    - Uses encoded actions instead of direct function calls
    - Supports native ETH (no WETH wrapping required)
    - Fee collection is done via DECREASE_LIQUIDITY with 0 liquidity
    """

    def __init__(self, manager):
        """
        Args:
            manager: Web3Manager instance
        """
        self.manager = manager
        self.config = UniswapV4Config()
        self.address = manager.checksum(self.config.position_manager_address)
        self.contract = manager.get_contract(self.address, "positionManager")

        self.gas_manager = GasManager(manager)
        self.tx_builder = TransactionBuilder(manager, self.gas_manager)

    def get_position(self, token_id: int):
        """
        Get position data by token ID.

        Args:
            token_id: Position NFT token ID

        Returns:
            dict with PoolKey, tickLower, tickUpper, liquidity
        """
        try:
            result = self.contract.functions.getPositionInfo(token_id).call()

            pool_key_tuple = result[0]
            return {
                "pool_key": PoolKey(
                    currency0=pool_key_tuple[0],
                    currency1=pool_key_tuple[1],
                    fee=pool_key_tuple[2],
                    tick_spacing=pool_key_tuple[3],
                    hooks=pool_key_tuple[4],
                ),
                "tick_lower": result[1],
                "tick_upper": result[2],
                "liquidity": result[3],
            }
        except Exception as e:
            raise PositionError(f"Position {token_id} not found: {e}")

    def owner_of(self, token_id: int) -> str:
        """Get owner of position NFT"""
        return self.contract.functions.ownerOf(token_id).call()

    def balance_of(self, address: str = None) -> int:
        """Get number of positions owned by address"""
        addr = address or self.manager.address
        return self.contract.functions.balanceOf(self.manager.checksum(addr)).call()

    def token_of_owner_by_index(self, index: int, address: str = None) -> int:
        """Get token ID at index for owner"""
        addr = address or self.manager.address
        return self.contract.functions.tokenOfOwnerByIndex(
            self.manager.checksum(addr), index
        ).call()

    def mint(
        self,
        pool_key: PoolKey,
        tick_lower: int,
        tick_upper: int,
        liquidity: int,
        amount0_max: int,
        amount1_max: int,
        recipient: str = None,
        deadline: int = None,
        gas_buffer: float = 1.2,
    ):
        """
        Mint a new liquidity position.

        Args:
            pool_key: The pool to add liquidity to
            tick_lower: Lower tick boundary
            tick_upper: Upper tick boundary
            liquidity: Amount of liquidity to add
            amount0_max: Maximum amount of token0 to spend
            amount1_max: Maximum amount of token1 to spend
            recipient: Address to receive the position NFT (default: sender)
            deadline: Transaction deadline (default: 30 min from now)
            gas_buffer: Multiplier for gas estimate

        Returns:
            dict with receipt and token_id
        """
        recipient = recipient or self.manager.address
        deadline = deadline or int(time.time()) + 1800

        # Check if using native ETH
        uses_native_eth = (
            is_native_eth(pool_key.currency0) or
            is_native_eth(pool_key.currency1)
        )

        if uses_native_eth:
            actions, params = encode_mint_position_with_native_eth(
                pool_key=pool_key,
                tick_lower=tick_lower,
                tick_upper=tick_upper,
                liquidity=liquidity,
                amount0_max=amount0_max,
                amount1_max=amount1_max,
                recipient=recipient,
            )
            # Calculate ETH value to send
            eth_value = amount0_max if is_native_eth(pool_key.currency0) else amount1_max
        else:
            actions, params = encode_mint_position(
                pool_key=pool_key,
                tick_lower=tick_lower,
                tick_upper=tick_upper,
                liquidity=liquidity,
                amount0_max=amount0_max,
                amount1_max=amount1_max,
                recipient=recipient,
            )
            eth_value = 0

        # Encode the unlock data
        unlock_data = encode(["bytes", "bytes[]"], [actions, params])

        contract_func = self.contract.functions.modifyLiquidities(
            unlock_data,
            deadline
        )

        receipt = self.tx_builder.build_and_send(
            contract_func,
            operation_type="mint",
            gas_buffer=gas_buffer,
            value=eth_value,
        )

        if receipt.status != 1:
            raise PositionError(f"Mint failed: {receipt.transactionHash.hex()}")

        # Parse token ID from Transfer event
        # Note: V4 position manager uses standard ERC721 Transfer event
        token_id = self._parse_token_id_from_receipt(receipt)

        return {"receipt": receipt, "token_id": token_id}

    def decrease_liquidity(
        self,
        token_id: int,
        liquidity: int,
        amount0_min: int = 0,
        amount1_min: int = 0,
        recipient: str = None,
        deadline: int = None,
    ):
        """
        Decrease liquidity from a position.

        Args:
            token_id: Position NFT token ID
            liquidity: Amount of liquidity to remove
            amount0_min: Minimum amount of token0 to receive
            amount1_min: Minimum amount of token1 to receive
            recipient: Address to receive tokens (default: sender)
            deadline: Transaction deadline

        Returns:
            Transaction receipt
        """
        recipient = recipient or self.manager.address
        deadline = deadline or int(time.time()) + 1800

        actions, params = encode_decrease_liquidity(
            token_id=token_id,
            liquidity=liquidity,
            amount0_min=amount0_min,
            amount1_min=amount1_min,
            recipient=recipient,
        )

        unlock_data = encode(["bytes", "bytes[]"], [actions, params])

        contract_func = self.contract.functions.modifyLiquidities(
            unlock_data,
            deadline
        )

        receipt = self.tx_builder.build_and_send(
            contract_func,
            operation_type="decreaseLiquidity"
        )

        if receipt.status != 1:
            raise PositionError(f"Decrease liquidity failed: {receipt.transactionHash.hex()}")

        return receipt

    def collect_fees(
        self,
        token_id: int,
        recipient: str = None,
        deadline: int = None,
    ):
        """
        Collect accumulated fees from a position.

        In V4, fee collection is done via DECREASE_LIQUIDITY with 0 liquidity.

        Args:
            token_id: Position NFT token ID
            recipient: Address to receive fees (default: sender)
            deadline: Transaction deadline

        Returns:
            Transaction receipt
        """
        recipient = recipient or self.manager.address
        deadline = deadline or int(time.time()) + 1800

        actions, params = encode_collect_fees(
            token_id=token_id,
            recipient=recipient,
        )

        unlock_data = encode(["bytes", "bytes[]"], [actions, params])

        contract_func = self.contract.functions.modifyLiquidities(
            unlock_data,
            deadline
        )

        receipt = self.tx_builder.build_and_send(
            contract_func,
            operation_type="collect"
        )

        if receipt.status != 1:
            raise PositionError(f"Collect fees failed: {receipt.transactionHash.hex()}")

        return receipt

    def burn(self, token_id: int, deadline: int = None):
        """
        Burn a position NFT.

        Position must have 0 liquidity and all fees must be collected.

        Args:
            token_id: Position NFT token ID to burn
            deadline: Transaction deadline

        Returns:
            Transaction receipt
        """
        deadline = deadline or int(time.time()) + 1800

        actions, params = encode_burn_position(token_id)
        unlock_data = encode(["bytes", "bytes[]"], [actions, params])

        contract_func = self.contract.functions.modifyLiquidities(
            unlock_data,
            deadline
        )

        receipt = self.tx_builder.build_and_send(
            contract_func,
            operation_type="burn"
        )

        if receipt.status != 1:
            raise PositionError(f"Burn failed: {receipt.transactionHash.hex()}")

        return receipt

    def _parse_token_id_from_receipt(self, receipt) -> int:
        """Parse token ID from mint receipt events"""
        # Look for Transfer event (ERC721)
        # Transfer(from=0x0, to=recipient, tokenId=...)
        try:
            for log in receipt.logs:
                # ERC721 Transfer event topic
                if log.topics[0].hex() == Web3.keccak(
                    text="Transfer(address,address,uint256)"
                ).hex():
                    # tokenId is the third topic for indexed events,
                    # or decode from data if not indexed
                    if len(log.topics) > 3:
                        return int(log.topics[3].hex(), 16)

            # Fallback: decode from event data
            return None
        except Exception:
            return None
