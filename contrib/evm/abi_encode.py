#!/usr/bin/env python3
"""Encode Ethereum contract calls for evmcall.

Usage:
  abi_encode.py <function_signature> [arg1 [arg2 ...]]

Example:
  python3 abi_encode.py transfer(address,uint256) 0x0123... 100
"""
import sys

try:
    from eth_abi import encode
    from eth_utils import keccak, to_bytes, remove_0x_prefix
except Exception as e:  # ModuleNotFoundError or similar
    sys.stderr.write("Missing dependencies: install eth_abi and eth_utils\n")
    sys.exit(1)


def main():
    if len(sys.argv) < 2:
        sys.stderr.write(__doc__)
        sys.exit(1)
    sig = sys.argv[1]
    args = sys.argv[2:]
    name, type_str = sig.split('(')
    types = type_str.rstrip(')').split(',') if type_str.rstrip(')') else []
    if len(args) != len(types):
        sys.stderr.write("Argument count mismatch\n")
        sys.exit(1)
    values = []
    for typ, val in zip(types, args):
        if typ == 'address':
            values.append(bytes.fromhex(remove_0x_prefix(val)))
        elif typ.startswith('uint') or typ.startswith('int'):
            values.append(int(val, 0))
        elif typ == 'bytes':
            values.append(bytes.fromhex(remove_0x_prefix(val)))
        else:
            values.append(val)
    data = keccak(text=sig)[:4] + encode(types, values)
    print('0x' + data.hex())


if __name__ == '__main__':
    main()
