from typing import Dict, List, Optional
from .transaction import Transaction

class Mempool:
    def __init__(self):
        self.transactions: Dict[str, Transaction] = {}

    def add_transaction(self, tx: Transaction) -> bool:
        """Adds a transaction to the mempool."""
        if tx.txid in self.transactions:
            return False
        self.transactions[tx.txid] = tx
        return True

    def remove_transaction(self, txid: str):
        """Removes a transaction from the mempool."""
        self.transactions.pop(txid, None)

    def get_transactions(self, limit: Optional[int] = None) -> List[Transaction]:
        """Returns a list of transactions, optionally limited."""
        txs = list(self.transactions.values())
        if limit:
            return txs[:limit]
        return txs
