from mini_bitcoin.crypto_utils import generate_keypair, pubkey_to_address, sha256

sk, pk = generate_keypair()
print(f"Private: {sk.hex()}")
print(f"Public: {pk.hex()}")
print(f"Address: {pubkey_to_address(pk)}")
print(f"Hash: {sha256(b'hello')}")
