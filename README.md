# AMM Trading Toolkit

A Python package for interacting with AMM protocols on Ethereum. Currently supports Uniswap V3, with a multi-protocol architecture designed for future expansion (Uniswap V4, Curve, etc.).

## Installation

```bash
# Clone the repository
git clone https://github.com/BilalBAI/amm-trading-suite.git
cd amm-trading-suite

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install the package
pip install -e .
```

## Configuration

1. Create a `.env` file with your RPC URL:
```env
RPC_URL=https://mainnet.infura.io/v3/YOUR_API_KEY
```

2. For transactions, create a `wallet.env` file:
```env
PUBLIC_KEY=your_public_key_here
PRIVATE_KEY=your_private_key_here
```

> **Warning:** Never commit `wallet.env` to version control!

3. The `config/` folder contains user-configurable settings:
```
config/
├── tokens.json              # Common token addresses
├── gas.json                 # Gas parameters
└── uniswap_v3/
    └── pools.json           # V3 pool addresses
```

## Gas Management

Gas parameters are configured in `config/gas.json`:

```json
{
    "maxFeePerGas": null,
    "maxPriorityFeePerGas": 1.5,
    "gasLimit": {
        "approve": 65000,
        "mint": 500000,
        "swap": 200000,
        "default": 500000
    }
}
```

### EIP-1559 Parameters Explained

| Parameter | Description | Example |
|-----------|-------------|---------|
| `gasLimit` | Maximum gas units per transaction type. Transaction fails if exceeded. | `500000` |
| `maxFeePerGas` | Maximum total fee (base + priority) per gas unit in Gwei. Set to `null` for no limit. | `50` (50 Gwei max) |
| `maxPriorityFeePerGas` | Tip to validators in Gwei. Higher = faster inclusion. | `1.5` (1.5 Gwei tip) |

### How Gas Cost Is Calculated

```
Maximum Cost = gasLimit × maxFeePerGas
Actual Cost  = gasUsed × (baseFee + priorityFee)
```

Where:
- `baseFee` is set by the network (you cannot control it)
- `priorityFee` = min(maxPriorityFeePerGas, maxFeePerGas - baseFee)

### Protection Mechanisms

1. **Transaction rejection**: If `baseFee > maxFeePerGas`, the transaction is rejected before sending (your funds are safe).
2. **Cost ceiling**: Your maximum spend is always `gasLimit × maxFeePerGas`.
3. **Unused gas refund**: You only pay for `gasUsed`, not the full `gasLimit`.


## Usage

### Command Line

#### General

```bash
# Query ETH and token balances (defaults to wallet.env address)
amm-trading query balances
amm-trading query balances --address 0x123...

# Wrap ETH to WETH
amm-trading wrap 0.1

# Unwrap WETH to ETH
amm-trading unwrap 0.1

# Generate a new wallet
amm-trading wallet generate
amm-trading wallet generate --accounts 5
```

#### Uniswap V3 - Queries

```bash
# Query all configured pools (uses cache for static data)
amm-trading univ3 query pools
amm-trading univ3 query pools --refresh-cache
amm-trading univ3 query pools --address 0x4e68Ccd3E89f51C3074ca5072bbAC773960dFa36

# Query a position by NFT token ID
amm-trading univ3 query position 1157630

# Query all positions (defaults to wallet.env address)
amm-trading univ3 query positions
amm-trading univ3 query positions --address 0x123...

# Calculate optimal token amounts before adding liquidity
amm-trading univ3 calculate amounts-range WETH USDT 3000 -0.05 0.05 --amount0 0.1
amm-trading univ3 calculate amounts-range WETH USDT 3000 -0.05 0.05 --amount1 300
```

#### Uniswap V3 - Liquidity

```bash
# Add liquidity (using ticks)
amm-trading univ3 add WETH USDT 3000 -887220 887220 0.1 300
amm-trading univ3 add WETH USDT 3000 -887220 887220 0.1 300 --slippage 1.0

# Add liquidity using percentage range around current price
amm-trading univ3 add-range WETH USDT 3000 -0.05 0.05 0.1 300    # -5% to +5%
amm-trading univ3 add-range WETH USDT 3000 -0.10 -0.01 0.1 300   # -10% to -1% (below)
amm-trading univ3 add-range WETH USDT 3000 0.01 0.10 0.1 300      # +1% to +10% (above)

# Remove liquidity
amm-trading univ3 remove 1157630 50 --collect-fees
amm-trading univ3 remove 1157630 100 --collect-fees --burn

# Migrate liquidity to new range
amm-trading univ3 migrate 1157630 -887220 887220
amm-trading univ3 migrate 1157630 -887220 887220 --percentage 50
```

#### Uniswap V3 - Swaps

```bash
amm-trading univ3 swap WETH USDT WETH_USDT_30 0.1
amm-trading univ3 swap WETH USDT WETH_USDT_30 0.1 --slippage 100
amm-trading univ3 swap WETH USDT WETH_USDT_30 0.1 --deadline 60
```

> **Note:** Gas parameters (maxFeePerGas, maxPriorityFeePerGas, gasLimit) are controlled via `gas_config.json`. See [Gas Management](#gas-management).

All results are automatically saved to the `results/` folder.

### Python API

```python
from amm_trading import Web3Manager, Config
from amm_trading.protocols.uniswap_v3 import (
    LiquidityManager, PositionQuery, PoolQuery, SwapManager,
)
from amm_trading.contracts import ERC20, WETH
from amm_trading.core import BalanceQuery, generate_wallet

# Query operations (read-only, no wallet needed)
query = PositionQuery()
position = query.get_position(1157630)
print(f"Position status: {position['status']}")
print(f"Current value: {position['value_in_token1']:.2f} {position['token1']['symbol']}")

# Query all pools
pool_query = PoolQuery()
pools = pool_query.get_all_configured_pools()

# Query token balances
balance_query = BalanceQuery()
balances = balance_query.get_all_balances("0x123...")
for bal in balances["balances"]:
    if bal["balance"] > 0:
        print(f"{bal['symbol']}: {bal['balance']}")

# Calculate optimal amounts BEFORE adding liquidity
web3_manager = Web3Manager(require_signer=False)
calc_manager = LiquidityManager(manager=web3_manager)

# I have 0.1 WETH, how much USDT do I need?
result = calc_manager.calculate_optimal_amounts_range(
    token0="WETH", token1="USDT", fee=3000,
    percent_lower=-0.05, percent_upper=0.05,
    amount0_desired=0.1,  # What I have
    amount1_desired=None,  # Calculate this
)
print(f"Need: {result['token0']['amount']} WETH and {result['token1']['amount']} USDT")
print(f"Position type: {result['position_type']}")  # in_range, below_range, or above_range

# Liquidity operations (requires wallet.env)
manager = LiquidityManager()

# Add liquidity (using ticks)
result = manager.add_liquidity(
    token0="WETH",
    token1="USDT",
    fee=3000,
    tick_lower=-887220,
    tick_upper=887220,
    amount0=0.1,
    amount1=300,
    slippage_bps=50,  # 0.5%
)
print(f"New position ID: {result['token_id']}")

# Add liquidity using percentage range
# Automatically converts percentages to ticks based on current pool price
result = manager.add_liquidity_range(
    token0="WETH",
    token1="USDT",
    fee=3000,
    percent_lower=-0.05,  # -5% below current price
    percent_upper=0.05,   # +5% above current price
    amount0=0.1,
    amount1=300,
    slippage_bps=50,  # 0.5%
)
print(f"New position ID: {result['token_id']}")
print(f"Current price: {result['current_price']:.2f}")
print(f"Price range: {result['price_lower']:.2f} to {result['price_upper']:.2f}")

# Remove liquidity
result = manager.remove_liquidity(
    token_id=1157630,
    percentage=50,
    collect_fees=True,
)

# Migrate to new range
result = manager.migrate_liquidity(
    token_id=1157630,
    new_tick_lower=-887220,
    new_tick_upper=887220,
    percentage=100,
    burn_old=True,
)
print(f"New position ID: {result['new_token_id']}")

# Generate a new wallet (no RPC connection needed)
wallet = generate_wallet(num_accounts=3)
print(f"Mnemonic: {wallet['mnemonic']}")
for acc in wallet["accounts"]:
    print(f"Account {acc['index']}: {acc['address']}")

# Swap tokens (requires wallet.env)
# Gas params loaded from gas_config.json
swap = SwapManager()
result = swap.swap(
    token_in="WETH",
    token_out="USDT",
    pool_name="WETH_USDT_30",
    amount_in=0.1,
    slippage_bps=50,  # 0.5%
)
print(f"Tx: {result['tx_hash']}")
print(f"Swapped {result['token_in']['amount']} {result['token_in']['symbol']}")

# Wrap/Unwrap ETH (requires wallet.env)
w3 = Web3Manager(require_signer=True)
weth = WETH(w3)
weth.deposit(0.1)   # Wrap 0.1 ETH to WETH
weth.withdraw(0.1)  # Unwrap 0.1 WETH to ETH
```

### Low-level Contract Access

```python
from amm_trading import Web3Manager
from amm_trading.contracts import ERC20
from amm_trading.protocols.uniswap_v3 import NFPM, Pool

# Read-only operations
manager = Web3Manager(require_signer=False)

# Get token info
weth = ERC20(manager, "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
print(f"{weth.symbol}: {weth.decimals} decimals")

# Get pool info (Uniswap V3)
pool = Pool(manager, "0x4e68Ccd3E89f51C3074ca5072bbAC773960dFa36")
print(f"Current tick: {pool.current_tick}")
print(f"Price: {pool.get_price(18, 6):.2f}")

# Transaction operations (requires signer)
manager = Web3Manager(require_signer=True)
nfpm = NFPM(manager)

# Get position
pos = nfpm.get_position(1157630)
print(f"Liquidity: {pos['liquidity']}")
```

## Package Structure

```
amm-trading-suite/
├── config/                         # User-configurable settings
│   ├── tokens.json                 # Common token addresses
│   ├── gas.json                    # Gas parameters (all protocols)
│   └── uniswap_v3/
│       └── pools.json              # V3 pool addresses
├── univ3_pool_cache.json           # V3 pool cache (auto-generated)
└── amm_trading/
    ├── abis.json                   # Shared ABIs (ERC20, WETH)
    ├── core/                       # Shared infrastructure
    │   ├── config.py               # Shared configuration management
    │   ├── connection.py           # Web3 connection handling
    │   ├── exceptions.py           # Custom exceptions
    │   ├── balances.py             # Query token balances
    │   └── wallet.py               # Wallet generation
    ├── contracts/                  # Shared contract wrappers
    │   ├── erc20.py                # ERC20 token wrapper
    │   └── weth.py                 # WETH wrap/unwrap operations
    ├── protocols/                  # Protocol implementations
    │   ├── base.py                 # Abstract base classes
    │   └── uniswap_v3/             # Uniswap V3 protocol
    │       ├── addresses.json      # V3 contract addresses (multi-chain)
    │       ├── abis.json           # V3-specific ABIs
    │       ├── config.py           # UniswapV3Config class
    │       ├── math.py             # Tick/price calculations
    │       ├── contracts/
    │       │   ├── nfpm.py         # NonfungiblePositionManager
    │       │   └── pool.py         # Pool contract wrapper
    │       └── operations/
    │           ├── liquidity.py    # Add/remove/migrate liquidity
    │           ├── pools.py        # Query pool information
    │           ├── positions.py    # Query position details
    │           └── swap.py         # Token swap operations
    ├── utils/                      # Shared utilities
    │   ├── gas.py                  # EIP-1559 gas management
    │   └── transactions.py         # Transaction helpers
    └── cli/
        └── main.py                 # Command-line interface
```

## Fee Tiers

| Fee | Percentage | Tick Spacing | Use Case |
|-----|------------|--------------|----------|
| 100 | 0.01% | 1 | Stable pairs |
| 500 | 0.05% | 10 | Stable pairs |
| 3000 | 0.3% | 60 | Most pairs |
| 10000 | 1% | 200 | Exotic pairs |

## Caching

Pool queries use a cache for static data (token info, fee tier, tick spacing) to reduce RPC calls.

- **Cache file:** `univ3_pool_cache.json` (working directory)
- **First query:** ~6 RPC calls per pool
- **Subsequent queries:** ~2 RPC calls per pool (~70% reduction)

Static data cached:
- `pool_name`, `address`, `token0`, `token1`, `pair`, `fee`, `fee_percent`, `tick_spacing`

Dynamic data (always fetched fresh):
- `current_tick`, `current_price`, `liquidity`

Use `--refresh-cache` to force update the cache.

## Output Files

All CLI commands save results to the `results/` folder:

| Command | Output File |
|---------|-------------|
| `query balances` | `results/balances_<address>.json` |
| `wallet generate` | `results/wallet.json` |
| `univ3 query pools` | `results/univ3_pools.json` |
| `univ3 query position <id>` | `results/univ3_position_<id>.json` |
| `univ3 query positions` | `results/positions_<address>.json` |
| `univ3 add ...` | `results/add_liquidity_<id>.json` |
| `univ3 remove ...` | `results/remove_liquidity_<id>.json` |
| `univ3 migrate ...` | `results/migrate_<old>_to_<new>.json` |
| `univ3 swap ...` | `results/swap_<tx_hash>.json` |

## Documentation

- **[TICKS_AND_PRICES.md](docs/TICKS_AND_PRICES.md)** - Understanding ticks, prices, and the math behind Uniswap V3
- **[PERCENTAGE_RANGES.md](docs/PERCENTAGE_RANGES.md)** - Guide to adding liquidity using percentage ranges
- **[TOKEN_AMOUNTS_GUIDE.md](docs/TOKEN_AMOUNTS_GUIDE.md)** - Understanding token ratios and calculating optimal amounts

## Archived Scripts

The original standalone scripts have been moved to the `archive/` folder. See [archive/README.md](archive/README.md) for migration guide.

## License

MIT
