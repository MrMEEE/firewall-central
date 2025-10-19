"""
Shared utilities for certificate management and cryptographic operations.
"""

import os
import ssl
import socket
from datetime import datetime, timedelta
from typing import Tuple, Optional
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtensionOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key


class CertificateManager:
    """Manages SSL certificates for secure communication between components."""
    
    def __init__(self, ca_cert_path: str, ca_key_path: str):
        self.ca_cert_path = ca_cert_path
        self.ca_key_path = ca_key_path
        
    def generate_ca_certificate(self, common_name: str = "Firewalld Central CA") -> Tuple[bytes, bytes]:
        """Generate a new Certificate Authority certificate and private key."""
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create CA certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Firewalld Central"),
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=3650)  # 10 years
        ).add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
            ]),
            critical=False,
        ).add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                key_cert_sign=True,
                crl_sign=True,
                digital_signature=False,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).sign(private_key, hashes.SHA256())
        
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        return cert_pem, key_pem
    
    def generate_server_certificate(self, hostname: str, ip_address: Optional[str] = None) -> Tuple[bytes, bytes]:
        """Generate a server certificate signed by the CA."""
        if not os.path.exists(self.ca_cert_path) or not os.path.exists(self.ca_key_path):
            raise FileNotFoundError("CA certificate or key not found")
        
        # Load CA certificate and key
        with open(self.ca_cert_path, 'rb') as f:
            ca_cert = x509.load_pem_x509_certificate(f.read())
        
        with open(self.ca_key_path, 'rb') as f:
            ca_key = load_pem_private_key(f.read(), password=None)
        
        # Generate server private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create server certificate
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Firewalld Central"),
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        ])
        
        # Build SAN list
        san_list = [x509.DNSName(hostname)]
        if ip_address:
            try:
                san_list.append(x509.IPAddress(ip_address))
            except ValueError:
                # If IP address is invalid, just add as DNS name
                san_list.append(x509.DNSName(ip_address))
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            ca_cert.subject
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        ).add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                key_cert_sign=False,
                crl_sign=False,
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).add_extension(
            x509.ExtendedKeyUsage([
                x509.oid.ExtendedKeyUsageOID.SERVER_AUTH,
                x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
            ]),
            critical=True,
        ).sign(ca_key, hashes.SHA256())
        
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        return cert_pem, key_pem
    
    def generate_client_certificate(self, client_id: str) -> Tuple[bytes, bytes]:
        """Generate a client certificate for agent authentication."""
        if not os.path.exists(self.ca_cert_path) or not os.path.exists(self.ca_key_path):
            raise FileNotFoundError("CA certificate or key not found")
        
        # Load CA certificate and key
        with open(self.ca_cert_path, 'rb') as f:
            ca_cert = x509.load_pem_x509_certificate(f.read())
        
        with open(self.ca_key_path, 'rb') as f:
            ca_key = load_pem_private_key(f.read(), password=None)
        
        # Generate client private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Create client certificate
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "CA"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Firewalld Central"),
            x509.NameAttribute(NameOID.COMMON_NAME, f"agent-{client_id}"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            ca_cert.subject
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=365)
        ).add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        ).add_extension(
            x509.KeyUsage(
                key_cert_sign=False,
                crl_sign=False,
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        ).add_extension(
            x509.ExtendedKeyUsage([
                x509.oid.ExtendedKeyUsageOID.CLIENT_AUTH,
            ]),
            critical=True,
        ).sign(ca_key, hashes.SHA256())
        
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        return cert_pem, key_pem
    
    def verify_certificate(self, cert_pem: bytes) -> bool:
        """Verify a certificate against the CA."""
        try:
            # Load CA certificate
            with open(self.ca_cert_path, 'rb') as f:
                ca_cert = x509.load_pem_x509_certificate(f.read())
            
            # Load certificate to verify
            cert = x509.load_pem_x509_certificate(cert_pem)
            
            # Verify certificate signature
            ca_public_key = ca_cert.public_key()
            ca_public_key.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                cert.signature_algorithm_oid._name.replace('_', '').upper()
            )
            
            # Check if certificate is still valid
            now = datetime.utcnow()
            if now < cert.not_valid_before or now > cert.not_valid_after:
                return False
            
            return True
        except Exception:
            return False
    
    def get_certificate_info(self, cert_pem: bytes) -> dict:
        """Extract information from a certificate."""
        cert = x509.load_pem_x509_certificate(cert_pem)
        
        subject_dict = {}
        for attribute in cert.subject:
            subject_dict[attribute.oid._name] = attribute.value
        
        return {
            'subject': subject_dict,
            'serial_number': str(cert.serial_number),
            'not_valid_before': cert.not_valid_before.isoformat(),
            'not_valid_after': cert.not_valid_after.isoformat(),
            'issuer': {attr.oid._name: attr.value for attr in cert.issuer}
        }


def setup_ssl_context(cert_path: str, key_path: str, ca_cert_path: Optional[str] = None) -> ssl.SSLContext:
    """Create an SSL context for secure communication."""
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    
    if ca_cert_path:
        context.load_verify_locations(ca_cert_path)
    else:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    
    context.load_cert_chain(cert_path, key_path)
    
    return context


def get_local_ip() -> str:
    """Get the local IP address of the machine."""
    try:
        # Connect to a remote address (doesn't actually send data)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"