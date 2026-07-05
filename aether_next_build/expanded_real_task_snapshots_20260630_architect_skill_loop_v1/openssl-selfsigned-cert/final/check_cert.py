#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import ssl
import sys

CERT_PATH = Path('/app/ssl/server.crt')

def main() -> int:
    if not CERT_PATH.exists():
        print('Certificate file missing', file=sys.stderr)
        return 1
    try:
        cert = ssl._ssl._test_decode_cert(str(CERT_PATH))
    except Exception as exc:
        print(f'Failed to load certificate: {exc}', file=sys.stderr)
        return 1

    subject = dict(x[0] for x in cert.get('subject', []))
    cn = subject.get('commonName')
    if not cn:
        print('Common Name missing', file=sys.stderr)
        return 1

    not_after = cert.get('notAfter')
    exp = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z').date().isoformat()

    print(f'Common Name: {cn}')
    print(f'Expiration Date: {exp}')
    print('Certificate verification successful')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
