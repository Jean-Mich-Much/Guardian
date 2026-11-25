"""
Protection optionnelle des fichiers sauvegardés par un mot de passe.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Tuple

from Crypto.Cipher import AES
from Crypto.Protocol.KDF import scrypt
from Crypto.Random import get_random_bytes


MAGIC = b"GUARDIAN\x01"
SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32


def derive_key(password: str, salt: bytes) -> bytes:
    """Crée une clé secrète à partir du mot de passe."""
    return scrypt(password.encode("utf-8"), salt, KEY_SIZE, N=2**15, r=8, p=1)


def encrypt_file(source: Path, destination: Path, password: str) -> dict:
    """Protège un fichier et conserve avec lui les informations nécessaires à sa lecture."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    salt = get_random_bytes(SALT_SIZE)
    nonce = get_random_bytes(NONCE_SIZE)
    key = derive_key(password, salt)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    cipher.update(MAGIC)

    data = source.read_bytes()
    encrypted, tag = cipher.encrypt_and_digest(data)
    payload = MAGIC + salt + nonce + tag + encrypted
    temporary = destination.with_name(destination.name + ".tmp")

    with open(temporary, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, destination)

    return {
        "protected": True,
        "salt_length": SALT_SIZE,
        "size": len(payload),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def decrypt_file(source: Path, destination: Path, password: str) -> bool:
    """Retrouve le contenu d'un fichier protégé après vérification du mot de passe."""
    payload = source.read_bytes()
    header_end = len(MAGIC)
    if payload[:header_end] != MAGIC:
        return False

    offset = header_end
    salt = payload[offset : offset + SALT_SIZE]
    offset += SALT_SIZE
    nonce = payload[offset : offset + NONCE_SIZE]
    offset += NONCE_SIZE
    tag = payload[offset : offset + 16]
    offset += 16
    encrypted = payload[offset:]

    key = derive_key(password, salt)
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    cipher.update(MAGIC)

    try:
        data = cipher.decrypt_and_verify(encrypted, tag)
    except ValueError:
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    with open(temporary, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, destination)
    return True


def verify_password(source: Path, password: str) -> bool:
    """Vérifie un mot de passe sans écrire le contenu déchiffré."""
    payload = source.read_bytes()
    try:
        if payload[: len(MAGIC)] != MAGIC:
            return False
        offset = len(MAGIC)
        salt = payload[offset : offset + SALT_SIZE]
        offset += SALT_SIZE
        nonce = payload[offset : offset + NONCE_SIZE]
        offset += NONCE_SIZE
        tag = payload[offset : offset + 16]
        offset += 16
        key = derive_key(password, salt)
        cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
        cipher.update(MAGIC)
        cipher.decrypt_and_verify(payload[offset:], tag)
        return True
    except (ValueError, IndexError, OSError):
        return False