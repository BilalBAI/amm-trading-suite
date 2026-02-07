"""Position query operations for Uniswap V4"""

from ....core.connection import Web3Manager
from ..config import UniswapV4Config
from ....contracts.erc20 import ERC20
from ..contracts.position_manager import PositionManager
from ..contracts.state_view import StateView
from ..types import ADDRESS_ZERO, is_native_eth
from ..math import tick_to_price, get_amounts_from_liquidity
from ...base import BasePositionQuery


class PositionQuery(BasePositionQuery):
    """Query Uniswap V4 position information"""

    def __init__(self, manager=None):
        """
        Args:
            manager: Web3Manager instance (created if None)
        """
        self.manager = manager or Web3Manager(require_signer=False)
        self.config = UniswapV4Config()
        self.position_manager = PositionManager(self.manager)
        self.state_view = StateView(self.manager)

    def _get_token_info(self, address):
        """Get token info, handling native ETH"""
        if is_native_eth(address):
            return {
                "address": ADDRESS_ZERO,
                "symbol": "ETH",
                "decimals": 18,
            }
        token = ERC20(self.manager, address)
        return token.info

    def get_position(self, token_id):
        """
        Get detailed position information.

        Args:
            token_id: Position NFT token ID

        Returns:
            Dict with position details
        """
        pos = self.position_manager.get_position(token_id)
        pool_key = pos["pool_key"]

        # Get token info (handles native ETH)
        token0_info = self._get_token_info(pool_key.currency0)
        token1_info = self._get_token_info(pool_key.currency1)

        result = {
            "token_id": token_id,
            "token0": token0_info,
            "token1": token1_info,
            "pair": f"{token0_info['symbol']}/{token1_info['symbol']}",
            "fee": pool_key.fee,
            "fee_percent": f"{pool_key.fee / 10000}%",
            "tick_lower": pos["tick_lower"],
            "tick_upper": pos["tick_upper"],
            "liquidity": pos["liquidity"],
            "pool_key": {
                "currency0": pool_key.currency0,
                "currency1": pool_key.currency1,
                "fee": pool_key.fee,
                "tick_spacing": pool_key.tick_spacing,
                "hooks": pool_key.hooks,
            },
            "has_hooks": pool_key.hooks != ADDRESS_ZERO,
        }

        # Get current pool state
        try:
            slot0 = self.state_view.get_slot0(pool_key)
            current_tick = slot0["tick"]
            sqrt_price_x96 = slot0["sqrt_price_x96"]

            # Calculate current price
            price = tick_to_price(
                current_tick,
                token0_info["decimals"],
                token1_info["decimals"]
            )

            # Determine position status
            if pos["tick_lower"] <= current_tick <= pos["tick_upper"]:
                status = "ACTIVE (earning fees)"
            elif current_tick < pos["tick_lower"]:
                status = "OUT OF RANGE (below)"
            else:
                status = "OUT OF RANGE (above)"

            # Calculate current amounts
            amount0, amount1 = get_amounts_from_liquidity(
                pos["liquidity"],
                sqrt_price_x96,
                current_tick,
                pos["tick_lower"],
                pos["tick_upper"],
                token0_info["decimals"],
                token1_info["decimals"],
            )

            # Calculate price range
            price_lower = tick_to_price(
                pos["tick_lower"],
                token0_info["decimals"],
                token1_info["decimals"]
            )
            price_upper = tick_to_price(
                pos["tick_upper"],
                token0_info["decimals"],
                token1_info["decimals"]
            )

            result.update({
                "status": status,
                "current_tick": current_tick,
                "current_price": price,
                "price_formatted": f"{price:.6f} {token1_info['symbol']}/{token0_info['symbol']}",
                "amount0": amount0,
                "amount1": amount1,
                "amount0_formatted": f"{amount0:.6f} {token0_info['symbol']}",
                "amount1_formatted": f"{amount1:.6f} {token1_info['symbol']}",
                "value_in_token1": amount0 * price + amount1,
                "price_range": {
                    "lower": price_lower,
                    "upper": price_upper,
                    "formatted": f"{price_lower:.6f} - {price_upper:.6f}",
                },
            })

        except Exception as e:
            result["status"] = f"Error fetching pool state: {e}"

        return result

    def get_positions_for_address(self, address=None):
        """
        Get all positions owned by address.

        Args:
            address: Address to query (uses manager address if None)

        Returns:
            List of position summaries
        """
        addr = address or self.manager.address
        count = self.position_manager.balance_of(addr)

        positions = []
        for i in range(count):
            token_id = self.position_manager.token_of_owner_by_index(i, addr)
            try:
                pos = self.get_position(token_id)
                positions.append(pos)
            except Exception as e:
                positions.append({"token_id": token_id, "error": str(e)})

        return positions
