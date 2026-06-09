"""
Generate a self-signed TLS certificate for local HTTPS development.

Writes ``certs/server.key`` and ``certs/server.crt`` (PEM format,
RSA-2048, SHA-256, valid 365 days). Suitable ONLY for development
and on-premises pilot deployments. Do NOT use in production.

Usage:
    python scripts/generate_self_signed_cert.py
    python scripts/generate_self_signed_cert.py --host 192.168.1.50 --days 730

Run the server with HTTPS:
    uvicorn server_app:app --host 0.0.0.0 --port 8443 \\
        --ssl-keyfile certs/server.key \\
        --ssl-certfile certs/server.crt
"""
from __future__ import annotations

import argparse
import datetime as _dt
import ipaddress
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger("certgen")


def _is_ip(value: str) -> bool:
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def generate(host: str, days: int, out_dir: Path) -> tuple[Path, Path]:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    out_dir.mkdir(parents=True, exist_ok=True)
    key_path = out_dir / "server.key"
    crt_path = out_dir / "server.crt"

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "SA"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Smart Reception"),
        x509.NameAttribute(NameOID.COMMON_NAME, host),
    ])

    san_entries: list[x509.GeneralName] = [x509.DNSName("localhost")]
    san_entries.append(x509.IPAddress(ipaddress.ip_address("127.0.0.1")))
    if _is_ip(host):
        san_entries.append(x509.IPAddress(ipaddress.ip_address(host)))
    else:
        san_entries.append(x509.DNSName(host))

    now = _dt.datetime.now(_dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _dt.timedelta(minutes=5))
        .not_valid_after(now + _dt.timedelta(days=days))
        .add_extension(x509.SubjectAlternativeName(san_entries), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(private_key=key, algorithm=hashes.SHA256())
    )

    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    crt_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

    logger.info("Wrote private key: %s", key_path)
    logger.info("Wrote certificate: %s (valid %d days)", crt_path, days)
    return key_path, crt_path


def main() -> int:
    p = argparse.ArgumentParser(description="Generate self-signed TLS cert")
    p.add_argument("--host", default="localhost", help="Common name / SAN host")
    p.add_argument("--days", type=int, default=365, help="Validity period")
    p.add_argument("--out", default="certs", help="Output directory")
    args = p.parse_args()
    out_dir = (PROJECT_ROOT / args.out).resolve()
    try:
        generate(args.host, args.days, out_dir)
    except ImportError:
        logger.error("`cryptography` is required: pip install cryptography")
        return 2
    print()
    print("Run with HTTPS:")
    print(
        "  uvicorn server_app:app --host 0.0.0.0 --port 8443 "
        f"--ssl-keyfile {out_dir.name}/server.key "
        f"--ssl-certfile {out_dir.name}/server.crt"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
