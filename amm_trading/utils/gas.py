"""Gas price and estimation management"""


class GasPriceTooHighError(Exception):
    """Raised when current gas price exceeds the user-specified maximum"""
    pass


class GasManager:
    """Centralized gas price and estimation management"""

    DEFAULT_GAS_LIMITS = {
        "approve": 65000,
        "mint": 500000,
        "decrease": 200000,
        "collect": 150000,
        "burn": 100000,
        "swap": 200000,
        "wrap": 50000,
        "unwrap": 50000,
    }

    def __init__(self, manager, max_gas_price_gwei=None):
        """
        Args:
            manager: Web3Manager instance
            max_gas_price_gwei: Maximum gas price in gwei (None = no limit)
        """
        self.manager = manager
        self.max_gas_price_gwei = max_gas_price_gwei

    def get_gas_price(self, ensure_timely=True):
        """
        Get current gas price, validating against max if set.

        Args:
            ensure_timely: If True, raises error if price exceeds max

        Returns:
            Gas price in wei

        Raises:
            GasPriceTooHighError: If ensure_timely=True and price > max
        """
        current_price = self.manager.get_gas_price()

        if self.max_gas_price_gwei is not None and ensure_timely:
            max_price_wei = int(self.max_gas_price_gwei * 1e9)
            if current_price > max_price_wei:
                current_gwei = current_price / 1e9
                raise GasPriceTooHighError(
                    f"Current gas price ({current_gwei:.2f} gwei) exceeds "
                    f"maximum ({self.max_gas_price_gwei} gwei). "
                    f"Transaction would likely be stuck pending."
                )

        return current_price

    def estimate_gas(self, contract_func, from_address, operation_type=None):
        """
        Estimate gas for a contract function call.

        Args:
            contract_func: Contract function to estimate
            from_address: Address to estimate from
            operation_type: Type of operation for fallback (e.g., "mint", "approve")

        Returns:
            Estimated gas amount
        """
        fallback = self.DEFAULT_GAS_LIMITS.get(operation_type, 500000)

        try:
            return contract_func.estimate_gas({"from": from_address})
        except Exception:
            return fallback

    def calculate_cost(self, gas_amount, gas_price=None):
        """
        Calculate gas cost in ETH.

        Args:
            gas_amount: Gas units
            gas_price: Gas price in wei (current price if None)

        Returns:
            Cost in ETH as float
        """
        if gas_price is None:
            gas_price = self.get_gas_price(ensure_timely=False)

        cost_wei = gas_amount * gas_price
        return float(self.manager.w3.from_wei(cost_wei, "ether"))

    def format_summary(self, gas_amount, gas_price=None):
        """
        Format a human-readable gas summary.

        Args:
            gas_amount: Gas units
            gas_price: Gas price in wei (current price if None)

        Returns:
            Dict with formatted gas information
        """
        if gas_price is None:
            gas_price = self.get_gas_price(ensure_timely=False)

        return {
            "gas_limit": gas_amount,
            "gas_price_wei": gas_price,
            "gas_price_gwei": gas_price / 1e9,
            "cost_eth": self.calculate_cost(gas_amount, gas_price),
            "max_gas_price_gwei": self.max_gas_price_gwei,
        }
