from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="amm-trading",
    version="0.1.0",
    author="Your Name",
    description="A toolkit for Uniswap V3 liquidity management",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/amm-tools",
    packages=find_packages(exclude=["archive", "results", "venv"]),
    python_requires=">=3.8",
    install_requires=[
        "web3>=6.0.0",
        "python-dotenv>=1.0.0",
        "mnemonic>=0.20",
        "eth-account>=0.9.0",
    ],
    entry_points={
        "console_scripts": [
            "amm-trading=amm_trading.cli.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
