# Address Asset Query Tool

Query all assets (ETH, ERC20 tokens, NFTs) held by an Ethereum address.

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
python query_uniswap_v3.py <token_id>
```

### Generate a new wallet:
```bash
python generate_wallet.py
```

### Add liquidity to Uniswap V3 pool:
```bash
python univ3_add_liq.py <token0> <token1> <fee> <tick_lower> <tick_upper> <amount0> <amount1> [slippage]
```

**Example:**
```bash
# Add liquidity to WETH/USDT pool with 0.3% fee
python univ3_add_liq.py WETH USDT 3000 -887220 887220 0.1 300

# With custom slippage (1%)
python univ3_add_liq.py WETH USDT 3000 -887220 887220 0.1 300 1.0
```

**Note:** Requires `wallet.env` file with `PRIVATE_KEY` for signing transactions.

### Examples

```bash
# Activate venv
source venv/bin/activate

# Query all assets for an address
python query_positions.py 0x5bd19Ea9E14205Bce413994D2640E4e9fb204DD3

# Query detailed Uniswap V3 position information
python query_uniswap_v3.py 1157630

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

### query_uniswap_v3.py
Queries detailed information for a Uniswap V3 position:
1. Position metadata (tokens, fee tier, tick range, liquidity)
2. Current price and amounts
3. Accumulated fees
4. Impermanent loss calculation
5. Deposit history
6. Saves results to: `results/position_univ3_<token_id>.json`

### generate_wallet.py
Generates a new Ethereum wallet:
1. Creates a 12-word recovery phrase (BIP39 mnemonic)
2. Derives the first 3 Ethereum accounts using BIP44 paths
3. Displays addresses and private keys for each account
4. Saves wallet data to: `results/wallet.json`

**⚠️ Security Warning:** Never share your mnemonic or private keys!

### univ3_add_liq.py
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

## Features

### query_positions.py
- ✅ ETH balance query
- ✅ Common ERC20 token balances
- ✅ Uniswap V3 position detection (direct query)
- ✅ NFT detection via Transfer events
- ✅ JSON export of all results

### query_uniswap_v3.py
- ✅ Complete position details
- ✅ Current token amounts and value
- ✅ Accumulated fees calculation
- ✅ Impermanent loss calculation
- ✅ Deposit history with timestamps
- ✅ JSON export matching standard format

### generate_wallet.py
- ✅ 12-word BIP39 mnemonic generation
- ✅ BIP44 Ethereum account derivation (m/44'/60'/0'/0/0, 1, 2)
- ✅ Private key and address generation
- ✅ Secure JSON export

### univ3_add_liq.py
- ✅ Token symbol or address support
- ✅ Automatic balance checking
- ✅ Token approval handling
- ✅ Slippage protection
- ✅ Gas estimation and cost display
- ✅ Transaction status tracking
- ✅ Position token ID retrieval

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

