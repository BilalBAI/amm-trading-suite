# Onchain Automated Market Maker Trading Toolkit

A comprehensive toolkit for interacting with Uniswap V3 and other onchain Automated Market Makers (AMMs). Query positions, analyze pools, execute trades, and manage liquidity positions programmatically.

## Overview

This toolkit provides a suite of Python scripts for interacting with onchain AMMs, specifically Uniswap V3:

- **Asset Querying**: Query ETH, ERC20 tokens, and NFTs held by any Ethereum address
- **Position Analysis**: Detailed analysis of Uniswap V3 liquidity positions including fees, impermanent loss, and deposit history
- **Pool Monitoring**: Real-time price, tick, and fee tier information for Uniswap V3 pools
- **Liquidity Management**: Add liquidity to Uniswap V3 pools with automatic tick spacing adjustments and slippage protection
- **Wallet Management**: Generate secure wallets with BIP39 recovery phrases and BIP44 account derivation

## Setup

1. **Create and activate virtual environment:**
```bash
# Create venv (if not already created)
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Or use the activation script
source activate.sh
```

2. **Install dependencies:**
```bash
pip install -r requirements.txt
```

3. **Create a `.env` file with your RPC URL:**
```env
RPC_URL=https://mainnet.infura.io/v3/YOUR_API_KEY
```

4. **Create a `wallet.env` file with your private key (for transactions):**
```env
PRIVATE_KEY=your_private_key_here
```

**⚠️ Security:** Never commit `wallet.env` to version control!

Or use any Ethereum RPC endpoint:
- Infura: `https://mainnet.infura.io/v3/YOUR_API_KEY`
- Alchemy: `https://eth-mainnet.g.alchemy.com/v2/YOUR_API_KEY`
- Public: `https://eth.llamarpc.com`

## Usage

**Important:** Always activate the virtual environment first:
```bash
source venv/bin/activate
# or
source activate.sh
```

Then run scripts:

### Query all assets for an address:
```bash
python query_positions.py <ethereum_address>
```

### Query Uniswap V3 position details:
```bash
python query_univ3_position.py <token_id>
```

### Generate a new wallet:
```bash
python generate_wallet.py
```

### Query Uniswap V3 pool information:
```bash
python query_univ3_pools.py
```

**Example:**
```bash
# Query all pools defined in config.json
python query_univ3_pools.py
```

### Add liquidity to Uniswap V3 pool:
```bash
python exe_univ3_add_liq.py <token0> <token1> <fee> <tick_lower> <tick_upper> <amount0> <amount1> [slippage]
```

**Example:**
```bash
# Add liquidity to WETH/USDT pool with 0.3% fee
python exe_univ3_add_liq.py WETH USDT 3000 -887220 887220 0.1 300

# With custom slippage (1%)
python exe_univ3_add_liq.py WETH USDT 3000 -887220 887220 0.1 300 1.0
```

### Remove liquidity from Uniswap V3 position:
```bash
python exe_univ3_remove_liq.py <token_id> <liquidity_percentage> [--collect-fees] [--burn]
```

**Example:**
```bash
# Remove 50% of liquidity and collect fees
python exe_univ3_remove_liq.py 1157630 50 --collect-fees

# Remove 100% of liquidity, collect fees, and burn the position
python exe_univ3_remove_liq.py 1157630 100 --collect-fees --burn

# Remove 25% without collecting fees
python exe_univ3_remove_liq.py 1157630 25
```

**Note:** Requires `wallet.env` file with `PRIVATE_KEY` for signing transactions.

### Examples

```bash
# Activate venv
source venv/bin/activate

# Query all assets for an address
python query_positions.py 0x5bd19Ea9E14205Bce413994D2640E4e9fb204DD3

# Query detailed Uniswap V3 position information
python query_univ3_position.py 1157630

# Generate a new wallet with 12-word recovery phrase
python generate_wallet.py
```

## Scripts

### query_positions.py
Queries all assets for an Ethereum address:
1. ETH balance
2. Common tokens (WETH, USDC, USDT, DAI, WBTC, UNI, LINK, AAVE, MKR, COMP)
3. Uniswap V3 positions (via direct NFPM query)
4. Other NFTs (via Transfer events, last ~10,000 blocks)
5. Saves results to: `assets_<address>.json`

### query_univ3_position.py
Queries detailed information for a Uniswap V3 position:
1. Position metadata (tokens, fee tier, tick range, liquidity)
2. Current price and amounts
3. Accumulated fees
4. Impermanent loss calculation
5. Deposit history
6. Saves results to: `results/univ3_position_<token_id>.json`

### query_univ3_pools.py
Queries information for Uniswap V3 pools:
1. Current tick and price
2. Token pair information
3. Fee tier detection
4. Human-readable prices (both directions)
5. Saves results to: `results/univ3_pools.json`

### generate_wallet.py
Generates a new Ethereum wallet:
1. Creates a 12-word recovery phrase (BIP39 mnemonic)
2. Derives the first 3 Ethereum accounts using BIP44 paths
3. Displays addresses and private keys for each account
4. Saves wallet data to: `results/wallet.json`

**⚠️ Security Warning:** Never share your mnemonic or private keys!

### exe_univ3_add_liq.py
Adds liquidity to a Uniswap V3 pool:
1. Supports token symbols (WETH, USDT, etc.) or addresses
2. Automatically checks token balances
3. Approves tokens if needed
4. Creates new liquidity position via NonfungiblePositionManager
5. Supports slippage protection
6. Returns position token ID for tracking

**Required:**
- `wallet.env` file with `PRIVATE_KEY`
- Sufficient token balances
- Correct tick range and fee tier

**Fee Tiers:**
- 500 = 0.05%
- 3000 = 0.3%
- 10000 = 1%

### exe_univ3_remove_liq.py
Removes liquidity from a Uniswap V3 position:
1. Fetches position information (current liquidity, tokens, fees)
2. Removes specified percentage of liquidity (0-100%)
3. Optional fee collection after removing liquidity
4. Optional position burning (when removing 100% liquidity)
5. Ownership verification before removal
6. Displays amounts received

**Required:**
- `wallet.env` file with `PRIVATE_KEY`
- Ownership of the position NFT
- Valid position with liquidity > 0

**Options:**
- `--collect-fees`: Collect accumulated fees and tokens after removal
- `--burn`: Burn the position NFT (only valid when removing 100% liquidity)

## Features

### query_positions.py
- ✅ ETH balance query
- ✅ Common ERC20 token balances
- ✅ Uniswap V3 position detection (direct query)
- ✅ NFT detection via Transfer events
- ✅ JSON export of all results

### query_univ3_position.py
- ✅ Complete position details
- ✅ Current token amounts and value
- ✅ Accumulated fees calculation
- ✅ Impermanent loss calculation
- ✅ Deposit history with timestamps
- ✅ JSON export matching standard format

### query_univ3_pools.py
- ✅ Current tick and price queries
- ✅ Automatic fee tier detection
- ✅ Token pair information
- ✅ Human-readable price calculations
- ✅ Summary table display
- ✅ JSON export

### generate_wallet.py
- ✅ 12-word BIP39 mnemonic generation
- ✅ BIP44 Ethereum account derivation (m/44'/60'/0'/0/0, 1, 2)
- ✅ Private key and address generation
- ✅ Secure JSON export

### exe_univ3_add_liq.py
- ✅ Token symbol or address support
- ✅ Automatic balance checking
- ✅ Token approval handling
- ✅ Slippage protection
- ✅ Gas estimation and cost display
- ✅ Transaction status tracking
- ✅ Position token ID retrieval

### exe_univ3_remove_liq.py
- ✅ Position information fetching
- ✅ Percentage-based liquidity removal (0-100%)
- ✅ Ownership verification
- ✅ Fee collection support
- ✅ Position burning support
- ✅ Gas estimation and cost display
- ✅ Transaction status tracking

## Shared Configuration

All scripts use shared configuration files:
- `config.json` - Contract addresses and common tokens
- `abis.json` - All contract ABIs

## Documentation

### Understanding Ticks and Prices

For detailed information about:
- What ticks are in Uniswap V3
- How ticks relate to human-readable prices
- Token decimal factors
- Fee tier and tick spacing tables
- Practical examples and calculations

See: **[TICKS_AND_PRICES.md](TICKS_AND_PRICES.md)**

## Limitations

- NFT detection (other than Uniswap V3) searches last ~10,000 blocks (~1.4 days)
- Some non-enumerable NFTs may not show token IDs
- Only queries predefined common tokens (add more in `config.json`)
- Historical price queries require archive node support

