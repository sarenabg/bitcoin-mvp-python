import sys
import threading
import time
import argparse
from mini_bitcoin.blockchain import Blockchain
from mini_bitcoin.mempool import Mempool
from mini_bitcoin.p2p import P2PNode
from mini_bitcoin.api import create_app
from mini_bitcoin.miner import Miner
from mini_bitcoin.crypto_utils import generate_keypair, pubkey_to_address
from mini_bitcoin.config import P2P_PORT, API_PORT

def main():
    parser = argparse.ArgumentParser(description="Mini Bitcoin Node")
    parser.add_argument("--p2p-port", type=int, default=P2P_PORT, help="P2P port")
    parser.add_argument("--api-port", type=int, default=API_PORT, help="API port")
    parser.add_argument("--peers", type=str, default="", help="Comma-separated list of peers (host:port)")
    parser.add_argument("--miner-address", type=str, default=None, help="Miner address (optional, generates new if not provided)")
    args = parser.parse_args()

    print(f"Starting Mini Bitcoin Node on P2P:{args.p2p_port}, API:{args.api_port}")

    # Generate a miner address if not provided
    if not args.miner_address:
        sk, pk = generate_keypair()
        miner_address = pubkey_to_address(pk)
        print(f"Generated new miner address: {miner_address}")
        print(f"Private Key (SAVE THIS): {sk.hex()}")
    else:
        miner_address = args.miner_address
        print(f"Using miner address: {miner_address}")

    blockchain = Blockchain()
    mempool = Mempool()
    
    peers = args.peers.split(",") if args.peers else []
    peers = [p.strip() for p in peers if p.strip()]
    
    p2p_node = P2PNode(blockchain, mempool, port=args.p2p_port, peers=peers)
    p2p_node.start()
    
    miner = Miner(blockchain, mempool, miner_address, p2p_node)
    miner.start()
    
    app = create_app(blockchain, mempool, p2p_node, miner_address)
    
    # Run API in a separate thread so main thread can keep running (or just run app.run which blocks)
    # Flask's app.run blocks, so we should run it here.
    # But we also have the miner and p2p running in background threads.
    # So blocking on app.run is fine.
    try:
        app.run(host="0.0.0.0", port=args.api_port, use_reloader=False)
    except KeyboardInterrupt:
        print("Shutting down...")
        miner.stop()
        # p2p_node.stop() # If we implemented stop

if __name__ == "__main__":
    main()
