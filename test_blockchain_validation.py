import tempfile

from mini_bitcoin.blockchain import Block, Blockchain
from mini_bitcoin.config import BLOCK_REWARD, DIFFICULTY_PREFIX
from mini_bitcoin.crypto_utils import generate_keypair, pubkey_to_address, sign_data
from mini_bitcoin.transaction import Transaction, TxInput, TxOutput


def mine_block(prev_block, transactions):
    block = Block(
        index=prev_block.index + 1,
        prev_hash=prev_block.hash,
        transactions=transactions,
    )
    while True:
        block_hash = block.compute_hash()
        if block_hash.startswith(DIFFICULTY_PREFIX):
            block.hash = block_hash
            return block
        block.nonce += 1


def create_funded_chain():
    data_dir = tempfile.mkdtemp()
    blockchain = Blockchain(data_dir=data_dir)
    private_key, public_key = generate_keypair()
    address = pubkey_to_address(public_key)

    coinbase = Transaction.create_coinbase(address, BLOCK_REWARD)
    funding_block = mine_block(blockchain.last_block, [coinbase])
    assert blockchain.add_block(funding_block)

    return blockchain, private_key, public_key, address, coinbase


def create_signed_spend(private_key, public_key, funding_tx, recipient, amount, change_address=None):
    change_address = change_address or pubkey_to_address(public_key)
    tx_input = TxInput(
        txid=funding_tx.txid,
        index=0,
        signature=sign_data(private_key, bytes.fromhex(funding_tx.txid)),
        pubkey=public_key.hex(),
    )
    outputs = [TxOutput(amount, recipient)]
    change = BLOCK_REWARD - amount
    if change:
        outputs.append(TxOutput(change, change_address))

    tx = Transaction(inputs=[tx_input], outputs=outputs)
    tx.txid = tx.compute_hash()
    return tx


def test_valid_signed_transaction_updates_utxo_balances():
    blockchain, private_key, public_key, sender, funding_tx = create_funded_chain()
    recipient = "recipient-address"

    spend = create_signed_spend(private_key, public_key, funding_tx, recipient, 15)
    reward = Transaction.create_coinbase(sender, BLOCK_REWARD)
    spend_block = mine_block(blockchain.last_block, [reward, spend])

    assert blockchain.add_block(spend_block)
    assert blockchain.get_balance(recipient) == 15
    assert blockchain.get_balance(sender) == 85


def test_rejects_spend_signed_by_wrong_key():
    blockchain, _, _, sender, funding_tx = create_funded_chain()
    attacker_private_key, attacker_public_key = generate_keypair()
    recipient = "recipient-address"

    forged = create_signed_spend(
        attacker_private_key,
        attacker_public_key,
        funding_tx,
        recipient,
        15,
        change_address=sender,
    )
    reward = Transaction.create_coinbase(sender, BLOCK_REWARD)
    forged_block = mine_block(blockchain.last_block, [reward, forged])

    assert not blockchain.add_block(forged_block)
    assert blockchain.get_balance(recipient) == 0
    assert blockchain.get_balance(sender) == BLOCK_REWARD


def test_rejects_double_spend_inside_single_block():
    blockchain, private_key, public_key, sender, funding_tx = create_funded_chain()
    first_spend = create_signed_spend(private_key, public_key, funding_tx, "recipient-one", 10)
    second_spend = create_signed_spend(private_key, public_key, funding_tx, "recipient-two", 20)
    reward = Transaction.create_coinbase(sender, BLOCK_REWARD)
    double_spend_block = mine_block(blockchain.last_block, [reward, first_spend, second_spend])

    assert not blockchain.add_block(double_spend_block)
    assert blockchain.get_balance("recipient-one") == 0
    assert blockchain.get_balance("recipient-two") == 0
    assert blockchain.get_balance(sender) == BLOCK_REWARD


def test_replacement_chain_rebuilds_utxo_set_and_rejects_invalid_spend():
    blockchain, _, _, sender, funding_tx = create_funded_chain()
    attacker_private_key, attacker_public_key = generate_keypair()

    forged = create_signed_spend(
        attacker_private_key,
        attacker_public_key,
        funding_tx,
        "recipient-address",
        15,
        change_address=sender,
    )
    reward = Transaction.create_coinbase(sender, BLOCK_REWARD)
    forged_block = mine_block(blockchain.last_block, [reward, forged])
    new_chain = blockchain.chain + [forged_block]

    assert not blockchain.replace_chain(new_chain)
    assert len(blockchain.chain) == 2
    assert blockchain.get_balance("recipient-address") == 0
