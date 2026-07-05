#!/usr/bin/env python3
import ssl
import sys
from datetime import datetime
from pathlib import Path

CERT_PATH = Path('/app/ssl/server.crt')


def main() -> int:
    if not CERT_PATH.exists():
        print('Certificate file not found', file=sys.stderr)
        return 1

    try:
        cert = ssl._ssl._test_decode_cert(str(CERT_PATH))
    except Exception as exc:
        print(f'Failed to load certificate: {exc}', file=sys.stderr)
        return 1

    subject = cert.get('subject', ())
    common_name = None
    for rdn in subject:
        for key, value in rdn:
            if key == 'commonName':
                common_name = value
                break
        if common_name:
            break

    if not common_name:
        print('Common Name not found', file=sys.stderr)
        return 1

    not_after = cert.get('notAfter')
    if not not_after:
        print('Expiration date not found', file=sys.stderr)
        return 1

    expiry = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z').strftime('%Y-%m-%d')
    print(f'Common Name: {common_name}')
    print(f'Expiration Date: {expiry}')
    print('Certificate verification successful')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
