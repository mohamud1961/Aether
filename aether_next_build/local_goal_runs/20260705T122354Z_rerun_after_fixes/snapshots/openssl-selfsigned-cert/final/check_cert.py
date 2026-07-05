#!/usr/bin/env python3
from datetime import datetime
from pathlib import Path
import ssl
import sys

CERT_PATH = Path("/app/ssl/server.crt")
EXPECTED_CN = "dev-internal.company.local"


def main() -> int:
    if not CERT_PATH.exists():
        print(f"Missing certificate: {CERT_PATH}", file=sys.stderr)
        return 1

    try:
        cert = ssl._ssl._test_decode_cert(str(CERT_PATH))
    except Exception as exc:
        print(f"Failed to load certificate: {exc}", file=sys.stderr)
        return 1

    subject = {}
    for rdn in cert.get("subject", ()):
        for key, value in rdn:
            subject[key] = value

    cn = subject.get("commonName")
    if cn != EXPECTED_CN:
        print(f"Unexpected Common Name: {cn}", file=sys.stderr)
        return 1

    not_after = cert.get("notAfter")
    if not not_after:
        print("Expiration date missing", file=sys.stderr)
        return 1

    exp_dt = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z")
    print(f"Common Name: {cn}")
    print(f"Expiration Date: {exp_dt.strftime('%Y-%m-%d')}")
    print("Certificate verification successful")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
