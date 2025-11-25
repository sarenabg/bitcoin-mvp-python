#!/usr/bin/env python3
"""
Wallet CLI for Mini Bitcoin
"""
import argparse
import requests
import sys
from mini_bitcoin.crypto_utils import generate_keypair, pubkey_to_address

def main():
    parser = argparse.ArgumentParser(description="Mini Bitcoin Wallet CLI")
    parser.add_argument("--node", default="http://localhost:8000", help="Node API URL")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # new_address command
    new_parser = subparsers.add_parser("new_address", help="Generate a new address and private key")
    
    # balance command
    balance_parser = subparsers.add_parser("balance", help="Check balance of an address")
    balance_parser.add_argument("address", help="Address to check")
    
    # send command
    send_parser = subparsers.add_parser("send", help="Send coins")
    send_parser.add_argument("private_key", help="Sender's private key (hex)")
    send_parser.add_argument("to_address", help="Recipient address")
    send_parser.add_argument("amount", type=int, help="Amount to send")
    
    # chain command
    chain_parser = subparsers.add_parser("chain", help="Get chain info")
    
    args = parser.parse_args()
    
    if args.command == "new_address":
        sk, pk = generate_keypair()
        address = pubkey_to_address(pk)
        print(f"New Address: {address}")
        print(f"Private Key: {sk.hex()}")
        print("\n⚠️  SAVE YOUR PRIVATE KEY! You need it to spend coins.")
        
    elif args.command == "balance":
        try:
            response = requests.get(f"{args.node}/balance/{args.address}")
            response.raise_for_status()
            data = response.json()
            print(f"Address: {data['address']}")
            print(f"Balance: {data['balance']} coins")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
            
    elif args.command == "send":
        try:
            payload = {
                "from_private_key": args.private_key,
                "to_address": args.to_address,
                "amount": args.amount
            }
            response = requests.post(f"{args.node}/send", json=payload)
            response.raise_for_status()
            data = response.json()
            print(f"Transaction sent!")
            print(f"TXID: {data['txid']}")
            print("\nWait for the next block to be mined for confirmation.")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
            
    elif args.command == "chain":
        try:
            response = requests.get(f"{args.node}/chain")
            response.raise_for_status()
            data = response.json()
            print(f"Chain Length: {data['length']} blocks")
            print(f"\nLast 5 blocks:")
            for block in data['chain'][-5:]:
                print(f"  Block #{block['index']}: {block['hash'][:16]}... ({block['tx_count']} txs)")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
            
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
