# Understanding Ticks and Prices in Uniswap V3

## What is a Tick?

In Uniswap V3, a **tick** is a discrete price point that defines where liquidity can be concentrated. Unlike Uniswap V2 where liquidity is distributed evenly across all prices, V3 allows liquidity providers to choose specific price ranges using ticks.

### Key Concepts:

1. **Tick as Price Boundary**: Each tick represents a specific price boundary in the price range
2. **Tick Spacing**: Not all ticks are valid - they must be multiples of the tick spacing for a given fee tier
3. **Price Range**: A liquidity position is defined by two ticks: `tickLower` and `tickUpper`

## Relationship Between Ticks and Prices

### The Core Formula

The relationship between a tick and its corresponding price is:

```
price = 1.0001^tick
```

Where:
- `price` is the price of token1 in terms of token0
- `tick` is the tick value (an integer)
- `1.0001` is Uniswap V3's fixed base multiplier

### Price Direction

- **Price of token1 in token0**: `price = 1.0001^tick`
- **Price of token0 in token1**: `price = 1 / (1.0001^tick) = 1.0001^(-tick)`

### Examples

For a WETH/USDT pair:
- If `tick = 0`, then `price = 1.0001^0 = 1` (1 USDT per WETH, or 1:1 ratio)
- If `tick = 69314`, then `price = 1.0001^69314 ≈ 1000` (1000 USDT per WETH)
- If `tick = -69314`, then `price = 1.0001^(-69314) ≈ 0.001` (0.001 USDT per WETH)

### Converting Price to Tick

To find the tick for a desired price:

```
tick = log(price) / log(1.0001)
```

Or equivalently:

```
tick = log(price) * log10(e) / log10(1.0001)
tick ≈ log(price) * 230258.5
```

**Note**: The calculated tick must then be rounded to the nearest valid tick based on tick spacing.

## Tick Range and Full Range Positions

### Full Range Positions

Uniswap V3 defines the maximum possible tick range as:
- **Lower bound**: `-887272` (practical minimum)
- **Upper bound**: `887272` (practical maximum)
- **Common full range**: `-887220` to `887220`

A position spanning this entire range behaves similarly to a Uniswap V2 position, providing liquidity across all possible prices.

### Concentrated Liquidity

By using narrower tick ranges, you can:
- Provide more liquidity in a specific price range
- Earn more fees when the price stays within your range
- Face impermanent loss if the price moves outside your range

## Tick Spacing by Fee Tier

Not all tick values are valid. Each fee tier has a specific tick spacing requirement:

| Fee Tier | Fee Percentage | Tick Spacing | Description |
|----------|----------------|--------------|-------------|
| 100      | 0.01%          | 1            | Extremely tight spacing (rarely used) |
| 500      | 0.05%          | 10           | Low fee, tight spacing |
| 3000     | 0.3%           | 60           | Medium fee (most common) |
| 10000    | 1%             | 200          | High fee, wider spacing |

### Valid Ticks

For a tick to be valid, it must be a multiple of the tick spacing:

- **Fee 500 (spacing 10)**: Valid ticks are ..., -20, -10, 0, 10, 20, ...
- **Fee 3000 (spacing 60)**: Valid ticks are ..., -120, -60, 0, 60, 120, ...
- **Fee 10000 (spacing 200)**: Valid ticks are ..., -400, -200, 0, 200, 400, ...

### Tick Adjustment Formula

When calculating ticks from prices, you must round to the nearest valid tick:

```
valid_tick = floor(tick / spacing) * spacing
```

For negative ticks, this rounds towards negative infinity to ensure valid ticks.

## Token Decimals and Price Calculation

When working with token prices, you must account for token decimals. The decimal factor determines how many smallest units (wei) make up one whole token.

### Common Token Decimals

| Token | Symbol | Decimals | Decimal Factor | Address |
|-------|--------|----------|----------------|---------|
| Wrapped Ether | WETH | 18 | 10^18 | 0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2 |
| USD Coin | USDC | 6 | 10^6 | 0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48 |
| Tether USD | USDT | 6 | 10^6 | 0xdAC17F958D2ee523a2206206994597C13D831ec7 |
| Dai Stablecoin | DAI | 18 | 10^18 | 0x6B175474E89094C44Da98b954EedeAC495271d0F |
| Wrapped BTC | WBTC | 8 | 10^8 | 0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599 |
| Uniswap | UNI | 18 | 10^18 | 0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984 |
| Chainlink | LINK | 18 | 10^18 | 0x514910771AF9Ca656af840dff83E8264EcF986CA |
| Aave | AAVE | 18 | 10^18 | 0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9 |
| Maker | MKR | 18 | 10^18 | 0x9f8F72aA9304c8B593d555F12eF6589cC3A579A2 |
| Compound | COMP | 18 | 10^18 | 0xc00e94Cb662C3520282E6f5717214004A7f26888 |

### Calculating Human-Readable Prices

When converting between raw amounts and human-readable prices, use the decimal factor:

**From raw amount to human-readable:**
```
human_amount = raw_amount / (10 ** decimals)
```

**From human-readable to raw amount:**
```
raw_amount = human_amount * (10 ** decimals)
```

**Example with WETH/USDT:**
- WETH has 18 decimals
- USDT has 6 decimals
- If 1 WETH = 3000 USDT:
  - Raw WETH amount: `1 * 10^18 = 1,000,000,000,000,000,000`
  - Raw USDT amount: `3000 * 10^6 = 3,000,000,000`
  - Price in terms of token1/token0: `3000 / 1 = 3000`

## Practical Examples

### Example 1: Calculating Price from Tick

Given `tick = 69314`:
```
price = 1.0001^69314 ≈ 1000
```

This means 1 token0 = 1000 token1 (approximately).

### Example 2: Finding Valid Ticks for a Price Range

For a WETH/USDT pool with fee tier 3000 (spacing 60):
- Desired price range: $2900 - $3100 per WETH
- Lower price: 2900 USDT per WETH
- Upper price: 3100 USDT per WETH

Calculate ticks:
```
tick_lower = log(2900) * 230258.5 ≈ 68968
tick_upper = log(3100) * 230258.5 ≈ 69529
```

Round to valid ticks:
```
valid_tick_lower = floor(68968 / 60) * 60 = 68940
valid_tick_upper = floor(69529 / 60) * 60 = 69540
```

### Example 3: Full Range Position

Using the full range with fee tier 3000:
- `tick_lower = -887220` (must be multiple of 60) ✓
- `tick_upper = 887220` (must be multiple of 60) ✓

Both ticks are valid because `887220 / 60 = 14787` (exact multiple).

## Summary

- **Tick**: Discrete price point in Uniswap V3's price range
- **Price Formula**: `price = 1.0001^tick`
- **Tick Spacing**: Ticks must be multiples of spacing (1, 10, 60, or 200 depending on fee tier)
- **Decimal Factors**: Essential for converting between raw blockchain amounts and human-readable values
- **Full Range**: Approximately -887220 to 887220 covers all possible prices

Understanding these concepts is crucial for:
- Creating liquidity positions with the correct price ranges
- Calculating token amounts in positions
- Understanding impermanent loss
- Optimizing fee collection strategies

