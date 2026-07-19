"""Sign and verify fw-catalog/1 documents (Ed25519, detached signature).

Usage:
    python tools/sign_catalog.py keygen  --out-dir keys/
    python tools/sign_catalog.py sign    catalog/catalog.json --key keys/catalog-signing.key
    python tools/sign_catalog.py verify  catalog/catalog.json --pub keys/catalog-signing.pub

``sign`` writes ``<catalog>.sig`` (base64) next to the catalog — publish both
files together. Deployments pin the public key via ``FW_CATALOG_PUBLIC_KEY``
(the base64 string inside the ``.pub`` file); once pinned, the API refuses
catalogs whose signature does not verify. Keep the ``.key`` file offline.
"""

import argparse
import base64
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def keygen(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    private = Ed25519PrivateKey.generate()
    key_file = out_dir / "catalog-signing.key"
    pub_file = out_dir / "catalog-signing.pub"
    key_file.write_text(base64.b64encode(private.private_bytes_raw()).decode() + "\n", encoding="ascii")
    pub_file.write_text(base64.b64encode(private.public_key().public_bytes_raw()).decode() + "\n", encoding="ascii")
    print(f"private key: {key_file}  (keep offline, never commit)")
    print(f"public key:  {pub_file}  (pin as FW_CATALOG_PUBLIC_KEY)")


def sign(catalog_file: Path, key_file: Path) -> None:
    private = Ed25519PrivateKey.from_private_bytes(base64.b64decode(key_file.read_text().strip()))
    signature = private.sign(catalog_file.read_bytes())
    sig_file = catalog_file.with_name(catalog_file.name + ".sig")
    sig_file.write_text(base64.b64encode(signature).decode() + "\n", encoding="ascii")
    print(f"signed: {sig_file}")


def verify(catalog_file: Path, pub_file: Path) -> None:
    public = Ed25519PublicKey.from_public_bytes(base64.b64decode(pub_file.read_text().strip()))
    sig_file = catalog_file.with_name(catalog_file.name + ".sig")
    try:
        public.verify(base64.b64decode(sig_file.read_text().strip()), catalog_file.read_bytes())
    except (InvalidSignature, FileNotFoundError) as exc:
        print(f"FAILED: {exc or 'signature does not verify'}")
        sys.exit(1)
    print("OK: signature verifies")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p_keygen = sub.add_parser("keygen", help="generate an Ed25519 keypair")
    p_keygen.add_argument("--out-dir", type=Path, default=Path("keys"))

    p_sign = sub.add_parser("sign", help="write <catalog>.sig")
    p_sign.add_argument("catalog", type=Path)
    p_sign.add_argument("--key", type=Path, required=True)

    p_verify = sub.add_parser("verify", help="check <catalog>.sig")
    p_verify.add_argument("catalog", type=Path)
    p_verify.add_argument("--pub", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "keygen":
        keygen(args.out_dir)
    elif args.command == "sign":
        sign(args.catalog, args.key)
    else:
        verify(args.catalog, args.pub)


if __name__ == "__main__":
    main()
