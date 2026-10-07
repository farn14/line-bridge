# -*- coding: utf-8 -*-
"""
Pure-Python X25519 agreement implementation using `cryptography`
Provides drop-in compatibility for axolotl_curve25519 on any platform (Linux/Windows/Docker)
"""
from cryptography.hazmat.primitives.asymmetric import x25519
import os

def generatePrivateKey(random_bytes=None):
    if not random_bytes or len(random_bytes) != 32:
        random_bytes = os.urandom(32)
    b = bytearray(random_bytes)
    b[0] &= 248
    b[31] &= 127
    b[31] |= 64
    return bytes(b)

def generatePublicKey(private_key):
    priv = x25519.X25519PrivateKey.from_private_bytes(bytes(private_key))
    return priv.public_key().public_bytes_raw()

def calculateAgreement(private_key, public_key):
    priv = x25519.X25519PrivateKey.from_private_bytes(bytes(private_key))
    pub = x25519.X25519PublicKey.from_public_bytes(bytes(public_key))
    return priv.exchange(pub)
