#!/usr/bin/env python3
from datetime import datetime
from pathlib import Path
import ssl
import sys

CERT_PATH = Path('/app/ssl/server.crt')
EXPECTED_CN = 'dev-internal.company.local'

if not CERT_PATH.is_file():
    raise SystemExit('Missing certificate: /app/ssl/server.crt')

try:
    cert = ssl._ssl._test_decode_cert(str(CERT_PATH))
except Exception as exc:
    raise SystemExit(f'Failed to load certificate: {exc}')

cn = None
for rdn in cert.get('subject', ()):
    for key, value in rdn:
        if key == 'commonName':
            cn = value
            break
    if cn is not None:
        break

if cn is None:
    raise SystemExit('Common Name not found in certificate subject')
if cn != EXPECTED_CN:
    raise SystemExit(f'Unexpected Common Name: {cn}')

not_after = cert.get('notAfter')
if not not_after:
    raise SystemExit('Expiration date not found')

exp_date = datetime.strptime(not_after, '%b %d %H:%M:%S %Y %Z').date().isoformat()
print(f'Common Name: {cn}')
print(f'Expiration date: {exp_date}')
print('Certificate verification successful')
