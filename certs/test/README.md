# Meegeleverd TEST-certificaat (es256)

`es256_certs.pem` + `es256_private.key` vormen een **zelf-ondertekend
test-certificaat** (ECDSA P-256 / es256) dat de tool gebruikt wanneer
“Gebruik test-certificaat” aan staat of wanneer je geen eigen cert opgeeft.

- Subject: `O = CN = "EXIT Toys / Dutch Toys Group"`. Verifiers tonen bij
  **“Signed by”** dus *EXIT Toys / Dutch Toys Group*.
- Het manifest is **cryptografisch geldig** (`validation_state: Valid`), maar de
  ondertekenaar is **niet vertrouwd**: verifiers tonen `signingCredential.untrusted`.
- **Gebruik dit nooit voor publicatie.** Vervang het door een echt, door een
  C2PA-conforme CA ondertekend certificaat (velden “Certificaat (.pem)” en
  “Private key” in de UI).

## Opnieuw genereren

```bash
./.venv/bin/python certs/test/regen_test_cert.py
```

Twee dingen die daarbij bewust geregeld zijn (en die het eerder lastig maakten):

- **O (organizationName) is verplicht.** C2PA keurt een signer-cert zónder
  organisatieveld af (`the certificate is invalid`). Daarom staat O erin.
- **notBefore ligt 1 dag in het verleden.** c2patool weigert een keten waarin
  een certificaat een notBefore ~nu heeft (“not yet valid”), dus een vers
  gegenereerd cert zou anders willekeurig falen.

Het script gebruikt de `cryptography`-library:
`./.venv/bin/python -m pip install cryptography` (alleen nodig om te
regenereren, niet om de tool te draaien).
