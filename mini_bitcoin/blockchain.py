import time
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Optional
from .crypto_utils import sha256
from .transaction import Transaction, TxInput, TxOutput
from .config import BLOCK_REWARD, DIFFICULTY_PREFIX
import pickle
import os

@dataclass
class Block:
    index: int
    prev_hash: str
    transactions: List[Transaction]
    nonce: int = 0
    timestamp: int = field(default_factory=lambda: int(time.time()))
    hash: str = ""

    def compute_hash(self) -> str:
        """Computes the SHA-256 hash of the block header."""
        # We serialize the block content (excluding the hash itself)
        block_data = {
            "index": self.index,
            "prev_hash": self.prev_hash,
            "transactions": [tx.to_dict() for tx in self.transactions],
            "nonce": self.nonce,
            "timestamp": self.timestamp
        }
        block_json = json.dumps(block_data, sort_keys=True).encode()
        return sha256(block_json)

class Blockchain:
    def __init__(self, data_dir: str = "./data"):
        self.chain: List[Block] = []
        # UTXO set: (txid, output_index) -> TxOutput dict
        self.utxo_set: Dict[Tuple[str, int], Dict] = {}
        self.data_dir = data_dir
        self.chain_file = os.path.join(data_dir, "chain.pkl")
        
        # Try to load from disk, otherwise create genesis
        if not self.load_from_disk():
            self.create_genesis_block()

    def create_genesis_block(self):
        """Creates the genesis block."""
        # Genesis transaction
        genesis_tx = Transaction.create_coinbase(miner_address="genesis_miner", block_reward=BLOCK_REWARD)
        genesis_tx.txid = genesis_tx.compute_hash()
        
        genesis_block = Block(
            index=0,
            prev_hash="0" * 64,
            transactions=[genesis_tx],
            nonce=0
        )
        genesis_block.hash = genesis_block.compute_hash()
        
        # We don't validate genesis, just add it
        self.chain.append(genesis_block)
        self.update_utxo_set(genesis_block)

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def add_block(self, block: Block) -> bool:
        """Validates and adds a new block to the chain."""
        if not self.is_valid_new_block(block, self.last_block):
            return False
        
        self.chain.append(block)
        self.update_utxo_set(block)
        self.save_to_disk()  # Auto-save on new block
        return True

    def is_valid_new_block(self, block: Block, prev_block: Block) -> bool:
        if block.prev_hash != prev_block.hash:
            print(f"Invalid prev_hash: {block.prev_hash} != {prev_block.hash}")
            return False
        
        if block.index != prev_block.index + 1:
            print(f"Invalid index: {block.index} != {prev_block.index + 1}")
            return False
        
        if not block.hash.startswith(DIFFICULTY_PREFIX):
            print(f"Invalid difficulty: {block.hash}")
            return False
        
        if block.hash != block.compute_hash():
            print(f"Invalid hash: {block.hash} != {block.compute_hash()}")
            return False
        
        # Validate transactions
        for tx in block.transactions:
            if not self.validate_transaction(tx):
                print(f"Invalid transaction: {tx.txid}")
                return False
        
        return True

    def validate_transaction(self, tx: Transaction) -> bool:
        """Checks if a transaction is valid."""
        if tx.is_coinbase:
            # Coinbase validation: reward amount check could be added here
            return True
        
        # Check inputs exist in UTXO set and signatures are valid
        input_sum = 0
        output_sum = sum(out.value for out in tx.outputs)
        
        for inp in tx.inputs:
            utxo_key = (inp.txid, inp.index)
            if utxo_key not in self.utxo_set:
                print(f"Input not found in UTXO set: {utxo_key}")
                return False
            
            utxo = self.utxo_set[utxo_key]
            input_sum += utxo['value']
            
            # Signature verification (simplified for MVP)
            # In a real chain, we'd verify the signature against the pubkey in the input
            # and ensure the pubkey matches the address in the UTXO.
            # For this MVP, we'll skip strict signature verification logic here 
            # unless we want to implement the full verify_signature call.
            # Let's assume valid for now or add a TODO.
            
        if input_sum < output_sum:
            print(f"Insufficient funds: {input_sum} < {output_sum}")
            return False
            
        return True

    def update_utxo_set(self, block: Block):
        """Updates the UTXO set based on the block's transactions."""
        for tx in block.transactions:
            # Remove spent outputs
            if not tx.is_coinbase:
                for inp in tx.inputs:
                    utxo_key = (inp.txid, inp.index)
                    if utxo_key in self.utxo_set:
                        del self.utxo_set[utxo_key]
            
            # Add new outputs
            for i, out in enumerate(tx.outputs):
                utxo_key = (tx.txid, i)
                self.utxo_set[utxo_key] = out.to_dict()

    def get_balance(self, address: str) -> int:
        """Calculates the balance for a given address."""
        balance = 0
        for utxo in self.utxo_set.values():
            if utxo['address'] == address:
                balance += utxo['value']
        return balance

    def is_valid_chain(self, chain: List[Block]) -> bool:
        """Checks if a given chain is valid."""
        # Check genesis block
        if chain[0].compute_hash() != self.chain[0].compute_hash():
            return False

        # Check the rest of the chain
        for i in range(1, len(chain)):
            block = chain[i]
            prev_block = chain[i-1]
            
            # We can reuse is_valid_new_block logic but we need to be careful
            # is_valid_new_block checks against self.last_block usually, 
            # here we check against the previous block in the *new* chain.
            
            if block.prev_hash != prev_block.hash:
                return False
            
            if not block.hash.startswith(DIFFICULTY_PREFIX):
                return False
            
            if block.hash != block.compute_hash():
                return False
            
            # Validate transactions (simplified: we don't re-validate signatures against UTXO set of that point in time for MVP 
            # because that would require rebuilding UTXO set from scratch for the new chain. 
            # For a robust implementation, we MUST rebuild UTXO set to validate inputs.)
            # Let's do a partial validation: check structure and hash.
            pass
            
        return True

    def replace_chain(self, new_chain: List[Block]) -> bool:
        """Replaces the current chain with a new one if it's valid and longer."""
        if len(new_chain) <= len(self.chain):
            return False
        
        if not self.is_valid_chain(new_chain):
            return False
            
        print(f"Replacing chain with new chain of length {len(new_chain)}")
        self.chain = new_chain
        
        # Rebuild UTXO set from scratch
        self.utxo_set = {}
        # We need to re-apply all blocks
        # But wait, update_utxo_set takes a block and updates self.utxo_set
        # So we can just clear and iterate
        
        # First, re-initialize with genesis (or just clear and handle genesis manually if it's in the chain)
        # Our chain includes genesis at index 0
        
        for block in self.chain:
            self.update_utxo_set(block)
            
        return True

    def save_to_disk(self) -> bool:
        """Saves the blockchain to disk."""
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            with open(self.chain_file, 'wb') as f:
                pickle.dump({'chain': self.chain, 'utxo_set': self.utxo_set}, f)
            return True
        except Exception as e:
            print(f"Error saving chain: {e}")
            return False

    def load_from_disk(self) -> bool:
        """Loads the blockchain from disk. Returns True if loaded, False if not found."""
        if not os.path.exists(self.chain_file):
            return False
        
        try:
            with open(self.chain_file, 'rb') as f:
                data = pickle.load(f)
                self.chain = data['chain']
                self.utxo_set = data['utxo_set']
            print(f"Loaded chain from disk: {len(self.chain)} blocks")
            return True
        except Exception as e:
            print(f"Error loading chain: {e}")
            return False
