#!/usr/bin/env python3
"""
Genereert het meegeleverde es256 TEST-certificaat opnieuw (met de `cryptography`
library — deterministisch, geen openssl-CLI-eigenaardigheden).

- Subject: O = CN = "EXIT Toys / Dutch Toys Group" (plus C=NL). C2PA vereist een
  organizationName (O) in de signer-cert; zonder O keurt de verificatie af.
  Verifiers tonen bij "Signed by" dan "EXIT Toys / Dutch Toys Group".
- notBefore staat 1 dag in het verleden: c2patool weigert een keten waarin een
  certificaat een notBefore ~nu heeft ("not yet valid").
- Het blijft een zelf-ondertekend, NIET-vertrouwd testcert. Verifiers tonen
  "untrusted signer". Voor publicatie: echt CA-certificaat gebruiken.

Draai met de venv-python van het project:
    ./.venv/bin/python certs/test/regen_test_cert.py
"""
import datetime as dt
from pathlib import Path

try:
    from cryptography import x509
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
except ImportError:
    raise SystemExit(
        "De 'cryptography' library is nodig om het testcert te genereren.\n"
        "Installeer met:  ./.venv/bin/python -m pip install cryptography"
    )

NAME = "EXIT Toys / Dutch Toys Group"
HERE = Path(__file__).resolve().parent

not_before = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1)
not_after = not_before + dt.timedelta(days=3650)


def _key():
    return ec.generate_private_key(ec.SECP256R1())


def main():
    # --- root (self-signed test-CA) ---
    ca_key = _key()
    ca_name = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, NAME),
        x509.NameAttribute(NameOID.COMMON_NAME, NAME + " Test Root"),
        x509.NameAttribute(NameOID.COUNTRY_NAME, "NL"),
    ])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name).issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before).not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=False, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=True,
            crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    # --- end-entity (signer) ---
    ee_key = _key()
    ee_name = x509.Name([
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, NAME),
        x509.NameAttribute(NameOID.COMMON_NAME, NAME),
        x509.NameAttribute(NameOID.COUNTRY_NAME, "NL"),
    ])
    ee_cert = (
        x509.CertificateBuilder()
        .subject_name(ee_name).issuer_name(ca_name)
        .public_key(ee_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before).not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.KeyUsage(
            digital_signature=True, content_commitment=False, key_encipherment=False,
            data_encipherment=False, key_agreement=False, key_cert_sign=False,
            crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(ee_key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
        .sign(ca_key, hashes.SHA256())
    )

    # chain: EE eerst, dan root
    (HERE / "es256_certs.pem").write_bytes(
        ee_cert.public_bytes(serialization.Encoding.PEM)
        + ca_cert.public_bytes(serialization.Encoding.PEM)
    )
    (HERE / "es256_private.key").write_bytes(
        ee_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    print("Klaar. Signer-subject: O=CN=" + NAME)
    print("Geldig vanaf:", not_before.strftime("%Y-%m-%d %H:%M:%SZ"),
          "t/m", not_after.strftime("%Y-%m-%d"))


if __name__ == "__main__":
    main()
