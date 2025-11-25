import time
import threading
from .config import DIFFICULTY_PREFIX, BLOCK_REWARD
from .transaction import Transaction
from .blockchain import Block, Blockchain
from .mempool import Mempool

class Miner:
    def __init__(self, blockchain: Blockchain, mempool: Mempool, miner_address: str, p2p_node=None):
        self.blockchain = blockchain
        self.mempool = mempool
        self.miner_address = miner_address
        self.p2p_node = p2p_node
        self._stop = False

    def start(self):
        """Starts the mining loop in a background thread."""
        thread = threading.Thread(target=self.mine_forever, daemon=True)
        thread.start()

    def stop(self):
        self._stop = True

    def mine_forever(self):
        print(f"Miner started. Address: {self.miner_address}")
        while not self._stop:
            # 1. Take transactions from mempool
            # For MVP, we just take all (or up to a limit)
            txs = self.mempool.get_transactions(limit=10)
            
            # 2. Build candidate block
            # Create coinbase tx
            coinbase_tx = Transaction.create_coinbase(self.miner_address, BLOCK_REWARD)
            block_txs = [coinbase_tx] + txs
            
            last_block = self.blockchain.last_block
            new_block = Block(
                index=last_block.index + 1,
                prev_hash=last_block.hash,
                transactions=block_txs,
                nonce=0
            )
            
            # 3. Run PoW
            while not new_block.compute_hash().startswith(DIFFICULTY_PREFIX):
                new_block.nonce += 1
                if self._stop:
                    return
                # Optional: check if someone else mined a block (update last_block)
                if self.blockchain.last_block.index >= new_block.index:
                    # Chain advanced, restart mining on new tip
                    break
            
            # Check if we actually found it (and didn't just break due to chain update)
            block_hash = new_block.compute_hash()
            if block_hash.startswith(DIFFICULTY_PREFIX):
                new_block.hash = block_hash
                print(f"Mined block #{new_block.index}: {new_block.hash}")
                
                # 4. Submit to blockchain
                if self.blockchain.add_block(new_block):
                    # Remove mined txs from mempool
                    for tx in txs:
                        self.mempool.remove_transaction(tx.txid)
                    
                    # Broadcast block
                    if self.p2p_node:
                        self.p2p_node.broadcast_block(new_block)
            
            # Small sleep to avoid 100% CPU if difficulty is too low or just to be nice
            time.sleep(0.1)
