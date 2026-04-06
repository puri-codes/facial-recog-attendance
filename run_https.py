#!/usr/bin/env python
"""Run the Django app over HTTPS for LAN camera access.

This generates a local self-signed certificate, installs it into the current
user trust store when possible, and serves the Django WSGI app over TLS so
browser camera APIs are allowed on a local IP.
"""

from __future__ import annotations

import argparse
import ipaddress
import os
import socket
import ssl
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'facial_attendance.settings')

import django  # noqa: E402
from cryptography import x509  # noqa: E402
from cryptography.hazmat.primitives import hashes, serialization  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import rsa  # noqa: E402
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID  # noqa: E402
from django.core.wsgi import get_wsgi_application  # noqa: E402


BASE_DIR = Path(__file__).resolve().parent
DEV_CERT_DIR = BASE_DIR / '.devcert'
CERT_FILE = DEV_CERT_DIR / 'server.crt'
KEY_FILE = DEV_CERT_DIR / 'server.key'


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


def get_local_ip() -> str:
    """Best-effort local LAN IP used for the certificate SAN list."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(('8.8.8.8', 80))
        return sock.getsockname()[0]
    except OSError:
        return '127.0.0.1'
    finally:
        sock.close()


def collect_san_ips() -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    ip_values: set[str] = {'127.0.0.1', '::1'}

    try:
        ip_values.add(get_local_ip())
    except OSError:
        pass

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None):
            address = info[4][0]
            try:
                ip_values.add(str(ipaddress.ip_address(address)))
            except ValueError:
                continue
    except OSError:
        pass

    ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
    for value in sorted(ip_values):
        try:
            ips.append(ipaddress.ip_address(value))
        except ValueError:
            continue
    return ips


def ensure_certificate() -> tuple[Path, Path]:
    """Create a self-signed certificate if it does not already exist."""
    DEV_CERT_DIR.mkdir(parents=True, exist_ok=True)

    if CERT_FILE.exists() and KEY_FILE.exists():
        return CERT_FILE, KEY_FILE

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, 'NP'),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'Bagmati'),
        x509.NameAttribute(NameOID.LOCALITY_NAME, 'Kathmandu'),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, 'cv-attendance-system'),
        x509.NameAttribute(NameOID.COMMON_NAME, socket.gethostname()),
    ])

    san_names = [
        x509.DNSName('localhost'),
        x509.DNSName(socket.gethostname()),
        x509.DNSName('cv-attendance.local'),
    ]
    san_names.extend(x509.IPAddress(ip_value) for ip_value in collect_san_ips())

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .add_extension(
            x509.SubjectAlternativeName(san_names),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    KEY_FILE.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    CERT_FILE.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return CERT_FILE, KEY_FILE


def import_certificate_to_windows_store(cert_file: Path) -> None:
    """Trust the dev certificate for the current Windows user when possible."""
    if os.name != 'nt':
        return

    try:
        result = subprocess.run(
            ['certutil', '-user', '-addstore', 'Root', str(cert_file)],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print('Trusted the local dev certificate in the current user store.')
        else:
            print('Could not auto-trust the certificate; browser may show a certificate warning.')
            if result.stdout:
                print(result.stdout.strip())
            if result.stderr:
                print(result.stderr.strip())
    except FileNotFoundError:
        print('certutil was not found; browser may show a certificate warning.')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run the Django app over HTTPS.')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to. Use 0.0.0.0 for LAN access.')
    parser.add_argument('--port', type=int, default=8443, help='HTTPS port to listen on.')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    django.setup()
    application = get_wsgi_application()

    cert_file, key_file = ensure_certificate()
    import_certificate_to_windows_store(cert_file)

    httpd = make_server(args.host, args.port, application, server_class=ThreadingWSGIServer, handler_class=WSGIRequestHandler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert_file), keyfile=str(key_file))
    httpd.socket = context.wrap_socket(httpd.socket, server_side=True)

    display_host = get_local_ip() if args.host == '0.0.0.0' else args.host
    print(f'Starting HTTPS server at https://{display_host}:{args.port}/')
    print('Use this URL in the browser to enable camera access over the LAN.')
    httpd.serve_forever()


if __name__ == '__main__':
    main()