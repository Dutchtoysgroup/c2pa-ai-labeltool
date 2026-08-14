# Meegeleverd TEST-certificaat (es256)

`es256_certs.pem` + `es256_private.key` vormen een **zelf-ondertekend
test-certificaat** (ECDSA P-256 / es256) dat de tool gebruikt wanneer
“Gebruik test-certificaat” aan staat of wanneer je geen eigen cert opgeeft.

- Het manifest dat hiermee ontstaat is **cryptografisch geldig**
  (`validation_state: Valid`), maar de ondertekenaar is **niet vertrouwd**:
  verifiers tonen `signingCredential.untrusted`.
- **Gebruik dit nooit voor publicatie.** Vervang het door een echt, door een
  CA ondertekend certificaat (velden “Certificaat (.pem)” en “Private key” in de
  UI).

Deze bestanden zijn bewust ingecheckt zodat test-modus out-of-the-box werkt —
vergelijkbaar met de voorbeeldcertificaten die c2patool zelf meelevert.
