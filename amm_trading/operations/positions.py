"""Position query operations"""

from ..core.connection import Web3Manager
from ..core.config import Config
from ..contracts.nfpm import NFPM
from ..contracts.pool import Pool
from ..contracts.erc20 import ERC20
from ..utils.math import tick_to_price, get_amounts_from_liquidity


class PositionQuery:
    """Query Uniswap V3 position information"""

    def __init__(self, manager=None):
        """
        Args:
            manager: Web3Manager instance (created if None)
        """
        self.manager = manager or Web3Manager(require_signer=False)
        self.config = Config()
        self.nfpm = NFPM(self.manager)
        self._factory = None

    @property
    def factory(self):
        """Lazy load factory contract"""
        if self._factory is None:
            self._factory = self.manager.get_contract(
                self.config.factory_address, "uniswap_v3_factory"
            )
        return self._factory

    def get_pool_address(self, token0, token1, fee):
        """Get pool address from factory"""
        return self.factory.functions.getPool(token0, token1, fee).call()

    def get_position(self, token_id):
        """
        Get detailed position information.

        Args:
            token_id: Position NFT token ID

        Returns:
            Dict with position details
        """
        pos = self.nfpm.get_position(token_id)

        # Get token info
        token0 = ERC20(self.manager, pos["token0"])
        token1 = ERC20(self.manager, pos["token1"])

        # Get pool
        pool_address = self.get_pool_address(pos["token0"], pos["token1"], pos["fee"])
        is_valid_pool = pool_address and pool_address != "0x" + "0" * 40

        result = {
            "token_id": token_id,
            "token0": token0.info,
            "token1": token1.info,
            "pair": f"{token0.symbol}/{token1.symbol}",
            "fee": pos["fee"],
            "fee_percent": f"{pos['fee'] / 10000}%",
            "tick_lower": pos["tick_lower"],
            "tick_upper": pos["tick_upper"],
            "liquidity": pos["liquidity"],
            "tokens_owed_0": pos["tokens_owed_0"],
            "tokens_owed_1": pos["tokens_owed_1"],
            "tokens_owed_0_human": token0.from_wei(pos["tokens_owed_0"]),
            "tokens_owed_1_human": token1.from_wei(pos["tokens_owed_1"]),
            "pool_address": pool_address if is_valid_pool else None,
        }

        if not is_valid_pool:
            result["status"] = "Pool not found"
            return result

        # Get current pool state
        pool = Pool(self.manager, pool_address)
        current_tick = pool.current_tick
        sqrt_price_x96 = pool.sqrt_price_x96

        # Calculate current price and position status
        price = pool.get_price(token0.decimals, token1.decimals)

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
            token0.decimals,
            token1.decimals,
        )

        # Calculate price range
        price_lower = tick_to_price(pos["tick_lower"], token0.decimals, token1.decimals)
        price_upper = tick_to_price(pos["tick_upper"], token0.decimals, token1.decimals)

        result.update({
            "status": status,
            "current_tick": current_tick,
            "current_price": price,
            "price_formatted": f"{price:.6f} {token1.symbol}/{token0.symbol}",
            "amount0": amount0,
            "amount1": amount1,
            "amount0_formatted": f"{amount0:.6f} {token0.symbol}",
            "amount1_formatted": f"{amount1:.6f} {token1.symbol}",
            "value_in_token1": amount0 * price + amount1,
            "price_range": {
                "lower": price_lower,
                "upper": price_upper,
                "formatted": f"{price_lower:.6f} - {price_upper:.6f}",
            },
        })

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
        count = self.nfpm.balance_of(addr)

        positions = []
        for i in range(count):
            token_id = self.nfpm.token_of_owner_by_index(i, addr)
            try:
                pos = self.get_position(token_id)
                positions.append(pos)
            except Exception as e:
                positions.append({"token_id": token_id, "error": str(e)})

        return positions
