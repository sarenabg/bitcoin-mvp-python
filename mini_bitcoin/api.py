from flask import Flask, jsonify, request, send_file
import os
from .blockchain import Blockchain
from .mempool import Mempool
from .p2p import P2PNode
from .transaction import Transaction, TxInput, TxOutput
from .crypto_utils import sign_data, generate_keypair, pubkey_to_address

def create_app(blockchain: Blockchain, mempool: Mempool, p2p_node: P2PNode, miner_address: str):
    app = Flask(__name__)

    @app.route('/address', methods=['GET'])
    def get_address():
        return jsonify({"address": miner_address})

    @app.route('/balance/<address>', methods=['GET'])
    def get_balance(address):
        balance = blockchain.get_balance(address)
        return jsonify({"address": address, "balance": balance})

    @app.route('/chain', methods=['GET'])
    def get_chain():
        chain_data = []
        for block in blockchain.chain:
            chain_data.append({
                "index": block.index,
                "hash": block.hash,
                "prev_hash": block.prev_hash,
                "tx_count": len(block.transactions),
                "timestamp": block.timestamp
            })
        return jsonify({
            "length": len(blockchain.chain),
            "chain": chain_data
        })

    @app.route('/send', methods=['POST'])
    def send_coins():
        # Body: {"from_private_key": "hex", "to_address": "addr", "amount": 10}
        data = request.get_json()
        priv_key_hex = data.get('from_private_key')
        to_address = data.get('to_address')
        amount = int(data.get('amount'))

        if not priv_key_hex or not to_address or not amount:
            return jsonify({"error": "Missing fields"}), 400

        # 1. Recover keys
        try:
            priv_key_bytes = bytes.fromhex(priv_key_hex)
            # We need to regenerate public key to derive address
            # This is a bit inefficient but works for MVP
            # In real wallet, we'd store address with key
            import ecdsa
            sk = ecdsa.SigningKey.from_string(priv_key_bytes, curve=ecdsa.SECP256k1)
            vk = sk.get_verifying_key()
            from_address = pubkey_to_address(vk.to_string())
        except Exception as e:
             return jsonify({"error": f"Invalid private key: {str(e)}"}), 400

        # 2. Select UTXOs
        # Simple selection: just take enough to cover amount
        # We don't handle change in this simple MVP unless we want to be fancy
        # Let's try to handle change if possible, or just fail if exact match not found?
        # The user plan said "Better UTXO selection & change output" is optional Phase 10.
        # So for now, let's just consume ALL UTXOs for the address and send the remainder back as change.
        
        input_sum = 0
        inputs = []
        utxos_to_spend = []
        
        # Find UTXOs for from_address
        for (txid, idx), utxo in blockchain.utxo_set.items():
            if utxo['address'] == from_address:
                utxos_to_spend.append((txid, idx, utxo['value']))
                input_sum += utxo['value']
        
        if input_sum < amount:
            return jsonify({"error": "Insufficient balance"}), 400

        # Create inputs
        for txid, idx, val in utxos_to_spend:
            # Sign the input
            # For MVP we sign the whole new tx hash usually, but here we construct input first
            # Simplified: we just put the signature in the input.
            # In real Bitcoin, we sign the tx with the input script empty, etc.
            # Here we will just sign a placeholder or the txid of the previous tx?
            # Let's just sign the string "txid:index" for now to prove ownership?
            # Or better, let's follow the plan: "Sign inputs with from_private_key"
            # We'll just put the signature of the txid we are spending.
            sig = sign_data(priv_key_bytes, bytes.fromhex(txid)) 
            inp = TxInput(txid=txid, index=idx, signature=sig, pubkey=vk.to_string().hex())
            inputs.append(inp)

        # Create outputs
        outputs = [TxOutput(value=amount, address=to_address)]
        change = input_sum - amount
        if change > 0:
            outputs.append(TxOutput(value=change, address=from_address))

        tx = Transaction(inputs=inputs, outputs=outputs)
        tx.txid = tx.compute_hash()

        # Add to mempool and broadcast
        if mempool.add_transaction(tx):
            p2p_node.broadcast_transaction(tx)
            return jsonify({"txid": tx.txid})
        else:
            return jsonify({"error": "Transaction rejected (already in mempool?)"}), 400

    # Block Explorer Endpoints
    @app.route('/explorer', methods=['GET'])
    def explorer():
        # Serve the explorer HTML file
        explorer_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'explorer.html')
        if os.path.exists(explorer_path):
            return send_file(explorer_path)
        return "Explorer not found", 404

    @app.route('/wallet', methods=['GET'])
    def wallet():
        # Serve the wallet HTML file
        wallet_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'wallet.html')
        if os.path.exists(wallet_path):
            return send_file(wallet_path)
        return "Wallet not found", 404


    @app.route('/api/stats', methods=['GET'])
    def get_stats():
        total_supply = sum(utxo['value'] for utxo in blockchain.utxo_set.values())
        return jsonify({
            "chain_height": len(blockchain.chain) - 1,
            "total_blocks": len(blockchain.chain),
            "total_supply": total_supply,
            "mempool_size": len(mempool.transactions),
            "difficulty": blockchain.chain[0].hash[:4] if blockchain.chain else "0000"
        })

    @app.route('/api/recent_blocks', methods=['GET'])
    def get_recent_blocks():
        recent = blockchain.chain[-10:]  # Last 10 blocks
        blocks_data = []
        for block in reversed(recent):  # Show newest first
            blocks_data.append({
                "index": block.index,
                "hash": block.hash,
                "prev_hash": block.prev_hash,
                "timestamp": block.timestamp,
                "tx_count": len(block.transactions),
                "nonce": block.nonce
            })
        return jsonify(blocks_data)

    @app.route('/api/block/<int:index>', methods=['GET'])
    def get_block_details(index):
        if index < 0 or index >= len(blockchain.chain):
            return jsonify({"error": "Block not found"}), 404
        
        block = blockchain.chain[index]
        txs_data = []
        for tx in block.transactions:
            txs_data.append({
                "txid": tx.txid,
                "is_coinbase": tx.is_coinbase,
                "inputs": [inp.to_dict() for inp in tx.inputs],
                "outputs": [out.to_dict() for out in tx.outputs],
                "timestamp": tx.timestamp
            })
        
        return jsonify({
            "index": block.index,
            "hash": block.hash,
            "prev_hash": block.prev_hash,
            "timestamp": block.timestamp,
            "nonce": block.nonce,
            "transactions": txs_data
        })

    @app.route('/api/transaction/<txid>', methods=['GET'])
    def get_transaction_details(txid):
        # Search through all blocks for the transaction
        for block in blockchain.chain:
            for tx in block.transactions:
                if tx.txid == txid:
                    return jsonify({
                        "txid": tx.txid,
                        "block_index": block.index,
                        "block_hash": block.hash,
                        "is_coinbase": tx.is_coinbase,
                        "inputs": [inp.to_dict() for inp in tx.inputs],
                        "outputs": [out.to_dict() for out in tx.outputs],
                        "timestamp": tx.timestamp
                    })
        return jsonify({"error": "Transaction not found"}), 404

    @app.route('/api/mempool', methods=['GET'])
    def get_mempool():
        txs_data = []
        for tx in mempool.get_transactions():
            txs_data.append({
                "txid": tx.txid,
                "inputs": len(tx.inputs),
                "outputs": len(tx.outputs),
                "timestamp": tx.timestamp
            })
        return jsonify(txs_data)

    return app
