"""EIP-1559 Gas management with user-configurable limits"""

import json
from pathlib import Path


class GasPriceTooHighError(Exception):
    """Raised when current gas price exceeds the user-specified maximum"""
    pass


class GasConfig:
    """Load and manage gas configuration from JSON file"""

    DEFAULT_GAS_LIMITS = {
        "approve": 65000,
        "transfer": 65000,
        "mint": 500000,
        "increaseLiquidity": 400000,
        "decreaseLiquidity": 200000,
        "collect": 150000,
        "burn": 100000,
        "swap": 200000,
        "swapMultihop": 350000,
        "wrap": 50000,
        "unwrap": 50000,
        "default": 500000,
    }

    def __init__(self, config_path=None):
        """
        Load gas configuration from JSON file.

        Args:
            config_path: Path to gas_config.json (searches default locations if None)
        """
        self._config = self._load_config(config_path)

    def _load_config(self, config_path=None):
        """Load config from file or return defaults"""
        search_paths = [
            config_path,
            Path.cwd() / "gas_config.json",
            Path.home() / ".amm-tools" / "gas_config.json",
            Path(__file__).parent.parent.parent / "gas_config.json",
        ]

        for path in search_paths:
            if path and Path(path).exists():
                with open(path) as f:
                    return json.load(f)

        # Return defaults if no config found
        return {
            "maxFeePerGas": None,
            "maxPriorityFeePerGas": 1.5,
            "gasLimit": self.DEFAULT_GAS_LIMITS.copy(),
        }

    @property
    def maxFeePerGas(self):
        """Max fee per gas in Gwei (None = no limit)"""
        return self._config.get("maxFeePerGas")

    @property
    def maxPriorityFeePerGas(self):
        """Priority fee (tip) in Gwei"""
        return self._config.get("maxPriorityFeePerGas", 1.5)

    def getGasLimit(self, operation_type):
        """
        Get gas limit for operation type.

        Args:
            operation_type: Transaction type (e.g., "mint", "swap", "approve")

        Returns:
            Gas limit in units
        """
        gas_limits = self._config.get("gasLimit", self.DEFAULT_GAS_LIMITS)
        return gas_limits.get(operation_type, gas_limits.get("default", 500000))


class GasManager:
    """
    EIP-1559 compliant gas management.

    Supports:
    - maxFeePerGas: Maximum total fee per gas unit (base + priority)
    - maxPriorityFeePerGas: Tip to validators for faster inclusion
    - gasLimit: Maximum gas units per transaction type
    """

    def __init__(self, manager, maxFeePerGas=None, maxPriorityFeePerGas=None, config=None):
        """
        Args:
            manager: Web3Manager instance
            maxFeePerGas: Max fee per gas in Gwei (overrides config)
            maxPriorityFeePerGas: Priority fee in Gwei (overrides config)
            config: GasConfig instance (created if None)
        """
        self.manager = manager
        self.config = config or GasConfig()

        # CLI overrides take precedence over config file
        self._maxFeePerGas = maxFeePerGas
        self._maxPriorityFeePerGas = maxPriorityFeePerGas

    @property
    def maxFeePerGas(self):
        """Get maxFeePerGas in Gwei (CLI override > config > None)"""
        if self._maxFeePerGas is not None:
            return self._maxFeePerGas
        return self.config.maxFeePerGas

    @property
    def maxPriorityFeePerGas(self):
        """Get maxPriorityFeePerGas in Gwei (CLI override > config)"""
        if self._maxPriorityFeePerGas is not None:
            return self._maxPriorityFeePerGas
        return self.config.maxPriorityFeePerGas

    def getGasLimit(self, operation_type=None):
        """Get gas limit for operation type"""
        return self.config.getGasLimit(operation_type or "default")

    def getBaseFee(self):
        """
        Get current base fee from latest block.

        Returns:
            Base fee in Wei
        """
        latest_block = self.manager.w3.eth.get_block("latest")
        return latest_block.get("baseFeePerGas", 0)

    def getGasParams(self, operation_type=None, gas_buffer=1.2):
        """
        Get EIP-1559 gas parameters for a transaction.

        Args:
            operation_type: Transaction type for gas limit lookup
            gas_buffer: Multiplier for gas limit (default 1.2 = +20%)

        Returns:
            Dict with maxFeePerGas, maxPriorityFeePerGas, gas (all in Wei)

        Raises:
            GasPriceTooHighError: If base fee exceeds maxFeePerGas
        """
        base_fee = self.getBaseFee()
        base_fee_gwei = base_fee / 1e9

        # Get priority fee in Wei
        priority_fee_gwei = self.maxPriorityFeePerGas or 1.5
        priority_fee_wei = int(priority_fee_gwei * 1e9)

        # Calculate maxFeePerGas
        if self.maxFeePerGas is not None:
            max_fee_gwei = self.maxFeePerGas
            max_fee_wei = int(max_fee_gwei * 1e9)

            # Validate: maxFeePerGas must be >= baseFee for transaction to be included
            if max_fee_wei < base_fee:
                raise GasPriceTooHighError(
                    f"Current base fee ({base_fee_gwei:.2f} Gwei) exceeds your "
                    f"maxFeePerGas ({max_fee_gwei} Gwei). Transaction cannot be included. "
                    f"Either increase maxFeePerGas or wait for lower network congestion."
                )
        else:
            # No limit set - use base fee + priority fee with buffer
            max_fee_wei = int((base_fee + priority_fee_wei) * 1.2)

        # Get gas limit
        gas_limit = self.getGasLimit(operation_type)
        gas_limit = int(gas_limit * gas_buffer)

        return {
            "maxFeePerGas": max_fee_wei,
            "maxPriorityFeePerGas": priority_fee_wei,
            "gas": gas_limit,
        }

    def estimateGas(self, contract_func, from_address, operation_type=None):
        """
        Estimate gas for a contract function call.

        Args:
            contract_func: Contract function to estimate
            from_address: Address to estimate from
            operation_type: Type of operation for fallback

        Returns:
            Estimated gas amount
        """
        fallback = self.getGasLimit(operation_type)

        try:
            return contract_func.estimate_gas({"from": from_address})
        except Exception:
            return fallback

    def calculateMaxCost(self, operation_type=None, gas_buffer=1.2):
        """
        Calculate maximum possible transaction cost.

        Args:
            operation_type: Transaction type for gas limit
            gas_buffer: Multiplier for gas limit

        Returns:
            Dict with cost breakdown
        """
        params = self.getGasParams(operation_type, gas_buffer)
        max_cost_wei = params["gas"] * params["maxFeePerGas"]

        return {
            "gasLimit": params["gas"],
            "maxFeePerGas_gwei": params["maxFeePerGas"] / 1e9,
            "maxPriorityFeePerGas_gwei": params["maxPriorityFeePerGas"] / 1e9,
            "maxCost_wei": max_cost_wei,
            "maxCost_eth": max_cost_wei / 1e18,
            "baseFee_gwei": self.getBaseFee() / 1e9,
        }

    def formatSummary(self, operation_type=None, gas_buffer=1.2):
        """
        Format a human-readable gas summary.

        Args:
            operation_type: Transaction type
            gas_buffer: Multiplier for gas limit

        Returns:
            Formatted string summary
        """
        cost = self.calculateMaxCost(operation_type, gas_buffer)
        return (
            f"Gas Summary:\n"
            f"  Base Fee:     {cost['baseFee_gwei']:.2f} Gwei\n"
            f"  Max Fee:      {cost['maxFeePerGas_gwei']:.2f} Gwei\n"
            f"  Priority Fee: {cost['maxPriorityFeePerGas_gwei']:.2f} Gwei\n"
            f"  Gas Limit:    {cost['gasLimit']:,}\n"
            f"  Max Cost:     {cost['maxCost_eth']:.6f} ETH"
        )
