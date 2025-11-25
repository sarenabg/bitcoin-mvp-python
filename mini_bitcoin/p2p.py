import socket
import threading
import json
import time
from typing import List
from .config import P2P_PORT
from .blockchain import Blockchain, Block
from .mempool import Mempool
from .transaction import Transaction, TxInput, TxOutput

class P2PNode:
    def __init__(self, blockchain: Blockchain, mempool: Mempool, port: int = P2P_PORT, peers: List[str] = None):
        self.blockchain = blockchain
        self.mempool = mempool
        self.port = port
        self.peers = peers or []
        self.active_peers = []
        self._stop = False

    def start(self):
        """Starts the P2P server and connects to peers."""
        # Start server
        server_thread = threading.Thread(target=self.start_server, daemon=True)
        server_thread.start()
        
        # Connect to peers
        time.sleep(1) # Wait for server to start
        self.connect_to_peers()

    def start_server(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server.bind(('0.0.0.0', self.port))
            server.listen(5)
            print(f"P2P Server listening on port {self.port}")
            
            while not self._stop:
                client, addr = server.accept()
                threading.Thread(target=self.handle_client, args=(client,), daemon=True).start()
        except Exception as e:
            print(f"P2P Server error: {e}")

    def connect_to_peers(self):
        for peer in self.peers:
            try:
                host, port = peer.split(':')
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((host, int(port)))
                self.active_peers.append(s)
                print(f"Connected to peer {peer}")
                # Start listening to this peer
                threading.Thread(target=self.handle_client, args=(s,), daemon=True).start()
                
                # Request chain from new peer
                self.request_chain(s)
            except Exception as e:
                print(f"Could not connect to peer {peer}: {e}")

    def handle_client(self, conn):
        with conn:
            while not self._stop:
                try:
                    data = conn.recv(4096)
                    if not data:
                        break
                    
                    # Handle multiple JSON objects in one stream (simple split by newline)
                    # For MVP we assume messages are newline delimited or small enough
                    # Let's assume one message per line for simplicity
                    messages = data.decode().strip().split('\n')
                    for msg_str in messages:
                        if not msg_str: continue
                        try:
                            msg = json.loads(msg_str)
                            self.handle_message(msg)
                        except json.JSONDecodeError:
                            pass
                except Exception as e:
                    print(f"Connection error: {e}")
                    break

    def handle_message(self, msg):
        msg_type = msg.get('type')
        
        if msg_type == 'NEW_TX':
            tx_data = msg.get('tx')
            # Reconstruct transaction
            # Simplified: we assume valid dict structure
            # In real app, we need proper deserialization
            # For now, let's just print it
            print(f"Received NEW_TX: {tx_data.get('txid')}")
            # TODO: Validate and add to mempool
            # For MVP, we'll construct a Transaction object from dict (simplified)
            # We need a from_dict method in Transaction, but for now let's just skip full validation
            # or implement a quick from_dict
            pass
            
        elif msg_type == 'NEW_BLOCK':
            block_data = msg.get('block')
            print(f"Received NEW_BLOCK: {block_data.get('index')}")
            # TODO: Validate and add to blockchain
            # We need to reconstruct Block object
            # For MVP, skipping full reconstruction/validation in this snippet
            pass
            
        elif msg_type == 'REQUEST_CHAIN':
            print("Received REQUEST_CHAIN")
            self.send_chain()
            
        elif msg_type == 'SEND_CHAIN':
            print("Received SEND_CHAIN")
            chain_data = msg.get('chain')
            # Reconstruct chain
            new_chain = []
            for b_data in chain_data:
                # Reconstruct Block object
                # We need to reconstruct transactions too
                txs = []
                for tx_data in b_data['transactions']:
                    inputs = [TxInput(**i) for i in tx_data['inputs']]
                    outputs = [TxOutput(**o) for o in tx_data['outputs']]
                    tx = Transaction(inputs=inputs, outputs=outputs, txid=tx_data['txid'], 
                                   is_coinbase=tx_data['is_coinbase'], timestamp=tx_data['timestamp'])
                    txs.append(tx)
                
                block = Block(
                    index=b_data['index'],
                    prev_hash=b_data['prev_hash'],
                    transactions=txs,
                    nonce=b_data['nonce'],
                    timestamp=b_data['timestamp'],
                    hash=b_data['hash']
                )
                new_chain.append(block)
            
            if self.blockchain.replace_chain(new_chain):
                print("Replaced local chain with longer valid chain from peer")
            else:
                print("Received chain was not longer or invalid")

    def request_chain(self, peer_socket):
        """Requests the blockchain from a peer."""
        try:
            msg = json.dumps({"type": "REQUEST_CHAIN"}) + "\n"
            peer_socket.sendall(msg.encode())
        except Exception as e:
            print(f"Failed to request chain: {e}")

    def send_chain(self):
        """Sends the current blockchain to all peers (or the requester)."""
        # For simplicity in MVP, we broadcast to all, but ideally we reply to the specific socket.
        # Since handle_message doesn't have the socket context easily here without refactoring,
        # let's just broadcast. It's noisy but works for small MVP.
        chain_data = []
        for block in self.blockchain.chain:
            b_data = {
                "index": block.index,
                "prev_hash": block.prev_hash,
                "transactions": [tx.to_dict() for tx in block.transactions],
                "nonce": block.nonce,
                "timestamp": block.timestamp,
                "hash": block.hash
            }
            chain_data.append(b_data)
        
        self.broadcast({"type": "SEND_CHAIN", "chain": chain_data})

    def broadcast(self, message: dict):
        """Broadcasts a message to all active peers."""
        msg_str = json.dumps(message) + "\n"
        for peer in self.active_peers:
            try:
                peer.sendall(msg_str.encode())
            except Exception as e:
                print(f"Failed to send to peer: {e}")
                self.active_peers.remove(peer)

    def broadcast_transaction(self, tx: Transaction):
        self.broadcast({"type": "NEW_TX", "tx": tx.to_dict()})

    def broadcast_block(self, block: Block):
        # We need to serialize the block properly, similar to compute_hash but including hash
        block_data = {
            "index": block.index,
            "prev_hash": block.prev_hash,
            "transactions": [tx.to_dict() for tx in block.transactions],
            "nonce": block.nonce,
            "timestamp": block.timestamp,
            "hash": block.hash
        }
        self.broadcast({"type": "NEW_BLOCK", "block": block_data})
