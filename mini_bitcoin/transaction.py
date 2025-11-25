import json
import time
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from .crypto_utils import sha256

@dataclass
class TxOutput:
    value: int
    address: str

    def to_dict(self):
        return asdict(self)

@dataclass
class TxInput:
    txid: str
    index: int
    signature: str = ""
    pubkey: str = ""  # Hex string

    def to_dict(self):
        return asdict(self)

@dataclass
class Transaction:
    inputs: List[TxInput]
    outputs: List[TxOutput]
    txid: str = ""
    is_coinbase: bool = False
    timestamp: int = field(default_factory=lambda: int(time.time()))

    def to_dict(self):
        return {
            "inputs": [i.to_dict() for i in self.inputs],
            "outputs": [o.to_dict() for o in self.outputs],
            "is_coinbase": self.is_coinbase,
            "timestamp": self.timestamp
        }

    def compute_hash(self) -> str:
        """Computes the SHA-256 hash of the transaction content."""
        # We exclude the txid itself from the hash, and signature from inputs if we were doing strict signing (but for simplicity we hash the whole dict structure minus txid)
        # For a real blockchain, we'd zero out signatures before hashing for signing, but for txid we hash the fully signed tx.
        # Let's keep it simple: hash the dict representation.
        tx_data = self.to_dict()
        tx_json = json.dumps(tx_data, sort_keys=True).encode()
        return sha256(tx_json)

    @classmethod
    def create_coinbase(cls, miner_address: str, block_reward: int) -> 'Transaction':
        # Coinbase has no inputs
        output = TxOutput(value=block_reward, address=miner_address)
        tx = cls(inputs=[], outputs=[output], is_coinbase=True)
        tx.txid = tx.compute_hash()
        return tx
