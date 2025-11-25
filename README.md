# Mini Bitcoin MVP 🪙

A fully functional, educational implementation of a Bitcoin-like blockchain in Python. This project demonstrates core blockchain concepts including Proof of Work (PoW) mining, UTXO-based transactions, P2P networking, and a web-based block explorer/wallet.

![Block Explorer](https://github.com/sarenabg/bitcoin-mvp-python/assets/placeholder/explorer.png)

## Features 🚀

- **Core Blockchain**: 
  - SHA-256 Proof of Work mining
  - UTXO (Unspent Transaction Output) model
  - Difficulty adjustment (simplified)
  - Longest chain consensus rule
  - Persistent storage (saves chain to disk)

- **Networking**:
  - P2P node discovery and chain synchronization
  - HTTP API for interaction

- **Interfaces**:
  - **Block Explorer**: Real-time visualization of blocks and transactions
  - **Web Wallet**: Create wallets, send coins, and monitor balances
  - **CLI Wallet**: Command-line tool for power users

## Quick Start 🏃‍♂️

### Prerequisites
- Python 3.8+
- `pip` (Python package manager)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/sarenabg/bitcoin-mvp-python.git
   cd bitcoin-mvp-python
   ```

2. **Install dependencies**
   ```bash
   pip install flask requests ecdsa
   ```

### Running the Node

Start a full node (miner + API + P2P server):

```bash
python3 -m mini_bitcoin.main --p2p-port 5005 --api-port 8005
```

You will see logs indicating the node has started mining and is listening for connections.

### Using the Web Interface

Once the node is running, open your browser:

- **Block Explorer**: [http://localhost:8005/explorer](http://localhost:8005/explorer)
  - View real-time blocks, transactions, and chain stats.
  - Click on any block to see detailed transaction info.

- **Web Wallet**: [http://localhost:8005/wallet](http://localhost:8005/wallet)
  - **My Wallet**: Import your private key (found in node logs) to send coins.
  - **Balance Monitor**: Watch any address in real-time.

### Using the CLI Wallet

You can also interact via the command line:

```bash
# Check balance
python3 wallet_cli.py --node http://localhost:8005 balance <address>

# Send coins
python3 wallet_cli.py --node http://localhost:8005 send <private_key> <recipient> <amount>

# View chain info
python3 wallet_cli.py --node http://localhost:8005 chain
```

## Architecture 🏗️

- `mini_bitcoin/blockchain.py`: Core chain logic, validation, and storage.
- `mini_bitcoin/miner.py`: Proof of Work mining loop.
- `mini_bitcoin/transaction.py`: Transaction structure and signing.
- `mini_bitcoin/p2p.py`: Peer-to-peer networking logic.
- `mini_bitcoin/api.py`: Flask REST API and web routes.
- `explorer.html`: Single-page block explorer app.
- `wallet.html`: Single-page web wallet app.

## License

MIT
