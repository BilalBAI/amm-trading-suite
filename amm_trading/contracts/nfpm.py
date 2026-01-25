"""Uniswap V3 NonfungiblePositionManager contract wrapper"""

import time
from web3 import Web3
from ..core.config import Config
from ..core.exceptions import PositionError


class NFPM:
    """Wrapper for NonfungiblePositionManager interactions"""

    def __init__(self, manager):
        """
        Args:
            manager: Web3Manager instance
        """
        self.manager = manager
        self.config = Config()
        self.address = manager.checksum(self.config.nfpm_address)
        self.contract = manager.get_contract(self.address, "uniswap_v3_nfpm")

    def get_position(self, token_id):
        """
        Get position data by token ID.
        Returns dict with position fields.
        """
        try:
            pos = self.contract.functions.positions(token_id).call()
        except Exception as e:
            raise PositionError(f"Position {token_id} not found: {e}")

        return {
            "nonce": pos[0],
            "operator": pos[1],
            "token0": pos[2],
            "token1": pos[3],
            "fee": pos[4],
            "tick_lower": pos[5],
            "tick_upper": pos[6],
            "liquidity": pos[7],
            "fee_growth_inside_0_last": pos[8],
            "fee_growth_inside_1_last": pos[9],
            "tokens_owed_0": pos[10],
            "tokens_owed_1": pos[11],
        }

    def owner_of(self, token_id):
        """Get owner of position NFT"""
        return self.contract.functions.ownerOf(token_id).call()

    def balance_of(self, address=None):
        """Get number of positions owned by address"""
        addr = address or self.manager.address
        return self.contract.functions.balanceOf(addr).call()

    def token_of_owner_by_index(self, index, address=None):
        """Get token ID at index for owner"""
        addr = address or self.manager.address
        return self.contract.functions.tokenOfOwnerByIndex(addr, index).call()

    def mint(self, params, gas_buffer=1.2):
        """
        Mint new liquidity position.

        Args:
            params: dict with token0, token1, fee, tickLower, tickUpper,
                   amount0Desired, amount1Desired, amount0Min, amount1Min,
                   recipient, deadline
            gas_buffer: multiplier for gas estimate
        """
        mint_params = (
            Web3.to_checksum_address(params["token0"]),
            Web3.to_checksum_address(params["token1"]),
            params["fee"],
            params["tick_lower"],
            params["tick_upper"],
            params["amount0_desired"],
            params["amount1_desired"],
            params["amount0_min"],
            params["amount1_min"],
            params["recipient"],
            params.get("deadline", int(time.time()) + 1800),
        )

        try:
            gas = self.contract.functions.mint(mint_params).estimate_gas(
                {"from": self.manager.address}
            )
        except Exception:
            gas = 1000000

        tx = self.contract.functions.mint(mint_params).build_transaction({
            "from": self.manager.address,
            "nonce": self.manager.get_nonce(),
            "gas": int(gas * gas_buffer),
            "gasPrice": self.manager.get_gas_price(),
            "chainId": self.manager.chain_id,
        })

        signed = self.manager.account.sign_transaction(tx)
        tx_hash = self.manager.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.manager.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status != 1:
            raise Exception(f"Mint failed: {tx_hash.hex()}")

        # Parse token ID from event
        events = self.contract.events.IncreaseLiquidity().process_receipt(receipt)
        token_id = events[0]["args"]["tokenId"] if events else None

        return {"receipt": receipt, "token_id": token_id}

    def decrease_liquidity(self, token_id, liquidity, amount0_min=0, amount1_min=0, deadline=None):
        """Decrease liquidity from position"""
        params = {
            "tokenId": token_id,
            "liquidity": liquidity,
            "amount0Min": amount0_min,
            "amount1Min": amount1_min,
            "deadline": deadline or int(time.time()) + 1800,
        }

        try:
            gas = self.contract.functions.decreaseLiquidity(params).estimate_gas(
                {"from": self.manager.address}
            )
        except Exception:
            gas = 500000

        tx = self.contract.functions.decreaseLiquidity(params).build_transaction({
            "from": self.manager.address,
            "nonce": self.manager.get_nonce(),
            "gas": int(gas * 1.2),
            "gasPrice": self.manager.get_gas_price(),
            "chainId": self.manager.chain_id,
        })

        signed = self.manager.account.sign_transaction(tx)
        tx_hash = self.manager.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.manager.w3.eth.wait_for_transaction_receipt(tx_hash)

        if receipt.status != 1:
            raise Exception(f"Decrease liquidity failed: {tx_hash.hex()}")

        return receipt

    def collect(self, token_id, recipient=None, amount0_max=None, amount1_max=None):
        """Collect fees and tokens from position"""
        params = {
            "tokenId": token_id,
            "recipient": recipient or self.manager.address,
            "amount0Max": amount0_max or self.config.MAX_UINT128,
            "amount1Max": amount1_max or self.config.MAX_UINT128,
        }

        tx = self.contract.functions.collect(params).build_transaction({
            "from": self.manager.address,
            "nonce": self.manager.get_nonce(),
            "gas": 300000,
            "gasPrice": self.manager.get_gas_price(),
            "chainId": self.manager.chain_id,
        })

        signed = self.manager.account.sign_transaction(tx)
        tx_hash = self.manager.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.manager.w3.eth.wait_for_transaction_receipt(tx_hash)

        return receipt

    def burn(self, token_id):
        """Burn position NFT (must have 0 liquidity and collected all fees)"""
        tx = self.contract.functions.burn(token_id).build_transaction({
            "from": self.manager.address,
            "nonce": self.manager.get_nonce(),
            "gas": 200000,
            "gasPrice": self.manager.get_gas_price(),
            "chainId": self.manager.chain_id,
        })

        signed = self.manager.account.sign_transaction(tx)
        tx_hash = self.manager.w3.eth.send_raw_transaction(signed.raw_transaction)
        receipt = self.manager.w3.eth.wait_for_transaction_receipt(tx_hash)

        return receipt
