import hashlib
import ecdsa


def sha256(data: bytes) -> str:
    """Returns the SHA-256 hash of the data as a hex string."""
    return hashlib.sha256(data).hexdigest()

def generate_keypair() -> tuple[bytes, bytes]:
    """Generates a new ECDSA keypair (private, public)."""
    sk = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
    vk = sk.get_verifying_key()
    return sk.to_string(), vk.to_string()

def pubkey_to_address(pubkey_bytes: bytes) -> str:
    """Derives a simple address from the public key."""
    # In real Bitcoin, this is SHA256 -> RIPEMD160 -> Base58Check
    # For MVP, we'll just do SHA256 -> hex (or base58 if installed, but let's stick to hex for simplicity if base58 is not in requirements)
    # The user plan said "pip install ecdsa flask", it didn't mention base58.
    # So let's stick to a simplified address: SHA256(pubkey).hexdigest()[:40] or similar.
    # Wait, the user plan said "pubkey_to_address(pubkey_bytes) -> str".
    # Let's just use the SHA256 hash of the pubkey for now, maybe truncated.
    
    sha_hash = hashlib.sha256(pubkey_bytes).hexdigest()
    return sha_hash  # Simple enough for MVP

def sign_data(private_key_bytes: bytes, data: bytes) -> str:
    """Signs data with private key, returns hex signature."""
    sk = ecdsa.SigningKey.from_string(private_key_bytes, curve=ecdsa.SECP256k1)
    sig = sk.sign(data)
    return sig.hex()

def verify_signature(public_key_bytes: bytes, data: bytes, signature_hex: str) -> bool:
    """Verifies a signature."""
    try:
        vk = ecdsa.VerifyingKey.from_string(public_key_bytes, curve=ecdsa.SECP256k1)
        sig = bytes.fromhex(signature_hex)
        return vk.verify(sig, data)
    except ecdsa.BadSignatureError:
        return False
