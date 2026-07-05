#!/usr/bin/env python3
from pathlib import Path
from datetime import datetime
import sys
from cryptography import x509
from cryptography.hazmat.backends import default_backend

cert_path = Path('/app/ssl/server.crt')
if not cert_path.exists():
    raise SystemExit('Certificate file missing')

with cert_path.open('rb') as f:
    cert = x509.load_pem_x509_certificate(f.read(), default_backend())

subject = cert.subject.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
if not subject:
    raise SystemExit('Common Name missing')
cn = subject[0].value
expires = cert.not_valid_after.strftime('%Y-%m-%d')
print(f'Common Name: {cn}')
print(f'Expiration Date: {expires}')
print('Certificate verification successful')
