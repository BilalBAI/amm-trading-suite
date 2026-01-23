# AMM Trading Toolkit

A Python package for interacting with Uniswap V3 on Ethereum. Query positions, analyze pools, and manage liquidity programmatically.

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/amm-tools.git
cd amm-tools

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
PRIVATE_KEY=your_private_key_here
```

> **Warning:** Never commit `wallet.env` to version control!

## Usage

### Command Line

```bash
# Query all configured pools (uses cache for static data)
amm-trading query pools

# Force refresh static pool data cache
amm-trading query pools --refresh-cache

# Query specific pool
amm-trading query pools --address 0x4e68Ccd3E89f51C3074ca5072bbAC773960dFa36

# Query a position
amm-trading query position 1157630

# Query all positions for an address
amm-trading query positions --address 0x123...

# Query ETH and token balances for an address
amm-trading query balances --address 0x123...

# Add liquidity
amm-trading add WETH USDT 3000 -887220 887220 0.1 300

# Add with custom slippage (1%)
amm-trading add WETH USDT 3000 -887220 887220 0.1 300 --slippage 1.0

# Remove 50% liquidity and collect fees
amm-trading remove 1157630 50 --collect-fees

# Remove 100% and burn position
amm-trading remove 1157630 100 --collect-fees --burn

# Migrate liquidity to new range
amm-trading migrate 1157630 -887220 887220

# Migrate 50% to new range
amm-trading migrate 1157630 -887220 887220 --percentage 50

# Generate a new wallet
amm-trading wallet generate

# Generate with 5 accounts
amm-trading wallet generate --accounts 5

# Swap tokens
amm-trading swap WETH USDT WETH_USDT_30 0.1

# Swap with custom slippage (1% = 100 basis points)
amm-trading swap WETH USDT WETH_USDT_30 0.1 --slippage 100

# Swap with max gas price limit
amm-trading swap WETH USDT WETH_USDT_30 0.1 --max-gas-price 50

# Swap with custom deadline (60 minutes)
amm-trading swap WETH USDT WETH_USDT_30 0.1 --deadline 60
```

All results are automatically saved to the `results/` folder.

### Python API

```python
from amm_trading import Web3Manager, Config
from amm_trading.operations import LiquidityManager, PositionQuery, PoolQuery, generate_wallet, SwapManager, BalanceQuery
from amm_trading.contracts import ERC20, NFPM, Pool

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

# Liquidity operations (requires wallet.env)
manager = LiquidityManager()

# Add liquidity
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
swap = SwapManager()
result = swap.swap(
    token_in="WETH",
    token_out="USDT",
    pool_name="WETH_USDT_30",
    amount_in=0.1,
    slippage_bps=50,  # 0.5%
    max_gas_price_gwei=50,  # Optional
)
print(f"Tx: {result['tx_hash']}")
print(f"Swapped {result['token_in']['amount']} {result['token_in']['symbol']}")
```

### Low-level Contract Access

```python
from amm_trading import Web3Manager
from amm_trading.contracts import ERC20, NFPM, Pool

# Read-only operations
manager = Web3Manager(require_signer=False)

# Get token info
weth = ERC20(manager, "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2")
print(f"{weth.symbol}: {weth.decimals} decimals")

# Get pool info
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
amm_trading/
├── core/
│   ├── config.py        # Configuration management
│   ├── connection.py    # Web3 connection handling
│   └── exceptions.py    # Custom exceptions
├── contracts/
│   ├── erc20.py         # ERC20 token wrapper
│   ├── nfpm.py          # NonfungiblePositionManager wrapper
│   └── pool.py          # Uniswap V3 Pool wrapper
├── operations/
│   ├── balances.py      # Query token balances
│   ├── liquidity.py     # Add/remove/migrate liquidity
│   ├── pools.py         # Query pool information
│   ├── positions.py     # Query position details
│   ├── swap.py          # Token swap operations
│   └── wallet.py        # Wallet generation
├── utils/
│   ├── math.py          # Tick/price calculations
│   └── transactions.py  # Transaction helpers
└── cli/
    └── main.py          # Command-line interface
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

- **Cache file:** `pool_info.json` (root folder)
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
| `query pools` | `results/univ3_pools.json` |
| `query position <id>` | `results/univ3_position_<id>.json` |
| `query positions` | `results/positions_<address>.json` |
| `query balances` | `results/balances_<address>.json` |
| `add ...` | `results/add_liquidity_<id>.json` |
| `remove ...` | `results/remove_liquidity_<id>.json` |
| `migrate ...` | `results/migrate_<old>_to_<new>.json` |
| `wallet generate` | `results/wallet.json` |
| `swap ...` | `results/swap_<tx_hash>.json` |

## Documentation

For detailed information about ticks and prices, see [TICKS_AND_PRICES.md](TICKS_AND_PRICES.md).

## Archived Scripts

The original standalone scripts have been moved to the `archive/` folder. See [archive/README.md](archive/README.md) for migration guide.

## License

MIT
