import time
import json
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Tuple, Optional
from copy import deepcopy
from .crypto_utils import sha256, pubkey_to_address, verify_signature
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
        
        return self.validate_block_transactions(block, deepcopy(self.utxo_set))

    def validate_transaction(self, tx: Transaction) -> bool:
        """Checks if a transaction is valid."""
        return self._validate_transaction_against_utxos(tx, deepcopy(self.utxo_set), allow_coinbase=True)

    def validate_block_transactions(self, block: Block, utxo_set: Dict[Tuple[str, int], Dict]) -> bool:
        """Validates block transaction ordering and spends against a working UTXO set."""
        if not block.transactions:
            print("Block has no transactions")
            return False

        coinbase_count = sum(1 for tx in block.transactions if tx.is_coinbase)
        if coinbase_count != 1 or not block.transactions[0].is_coinbase:
            print("Block must contain exactly one leading coinbase transaction")
            return False

        for tx in block.transactions:
            if not self._validate_transaction_against_utxos(tx, utxo_set, allow_coinbase=tx is block.transactions[0]):
                print(f"Invalid transaction: {tx.txid}")
                return False
            self._apply_transaction_to_utxos(tx, utxo_set)

        return True

    def _validate_transaction_against_utxos(
        self,
        tx: Transaction,
        utxo_set: Dict[Tuple[str, int], Dict],
        allow_coinbase: bool = False
    ) -> bool:
        if tx.txid != tx.compute_hash():
            print(f"Invalid txid: {tx.txid} != {tx.compute_hash()}")
            return False

        if tx.is_coinbase:
            if not allow_coinbase:
                print("Coinbase transaction is not allowed here")
                return False
            if tx.inputs:
                print("Coinbase transaction cannot have inputs")
                return False
            if len(tx.outputs) != 1:
                print("Coinbase transaction must have exactly one output")
                return False
            output = tx.outputs[0]
            if output.value <= 0 or output.value > BLOCK_REWARD:
                print(f"Invalid coinbase reward: {output.value}")
                return False
            if not output.address:
                print("Coinbase output address is required")
                return False
            return True

        if not tx.inputs:
            print("Transaction must have at least one input")
            return False
        if not tx.outputs:
            print("Transaction must have at least one output")
            return False

        input_sum = 0
        output_sum = 0
        spent_inputs = set()

        for out in tx.outputs:
            if out.value <= 0:
                print(f"Invalid output value: {out.value}")
                return False
            if not out.address:
                print("Output address is required")
                return False
            output_sum += out.value

        for inp in tx.inputs:
            utxo_key = (inp.txid, inp.index)
            if utxo_key in spent_inputs:
                print(f"Duplicate input in transaction: {utxo_key}")
                return False
            spent_inputs.add(utxo_key)

            if utxo_key not in utxo_set:
                print(f"Input not found in UTXO set: {utxo_key}")
                return False

            utxo = utxo_set[utxo_key]
            input_sum += utxo['value']

            try:
                pubkey_bytes = bytes.fromhex(inp.pubkey)
                signed_data = bytes.fromhex(inp.txid)
            except ValueError:
                print("Input contains invalid hex data")
                return False

            if pubkey_to_address(pubkey_bytes) != utxo['address']:
                print("Input public key does not match UTXO owner")
                return False

            if not verify_signature(pubkey_bytes, signed_data, inp.signature):
                print("Invalid input signature")
                return False
            
        if input_sum < output_sum:
            print(f"Insufficient funds: {input_sum} < {output_sum}")
            return False
            
        return True

    def _apply_transaction_to_utxos(self, tx: Transaction, utxo_set: Dict[Tuple[str, int], Dict]):
        if not tx.is_coinbase:
            for inp in tx.inputs:
                del utxo_set[(inp.txid, inp.index)]

        for i, out in enumerate(tx.outputs):
            utxo_set[(tx.txid, i)] = out.to_dict()

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
        if not chain:
            return False

        if chain[0].compute_hash() != self.chain[0].compute_hash():
            return False
        if chain[0].hash != chain[0].compute_hash():
            return False

        rebuilt_utxos: Dict[Tuple[str, int], Dict] = {}
        if not self.validate_block_transactions(chain[0], rebuilt_utxos):
            return False

        for i in range(1, len(chain)):
            block = chain[i]
            prev_block = chain[i-1]

            if block.prev_hash != prev_block.hash:
                return False
            if block.index != prev_block.index + 1:
                return False
            if not block.hash.startswith(DIFFICULTY_PREFIX):
                return False
            if block.hash != block.compute_hash():
                return False
            if not self.validate_block_transactions(block, rebuilt_utxos):
                return False
            
        return True

    def replace_chain(self, new_chain: List[Block]) -> bool:
        """Replaces the current chain with a new one if it's valid and longer."""
        if len(new_chain) <= len(self.chain):
            return False
        
        if not self.is_valid_chain(new_chain):
            return False
            
        print(f"Replacing chain with new chain of length {len(new_chain)}")
        self.chain = new_chain
        self.utxo_set = {}

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
