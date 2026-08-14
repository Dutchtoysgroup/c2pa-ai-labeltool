# EXIT-Toys-C2PA-Tool

Lokale, offline desktop-tool die per map beelden:

1. **een zichtbaar AI-icoon/label inbrandt** (optioneel, met Pillow), en
2. **C2PA Content Credentials** toevoegt die de herkomst declareren als
   AI-gegenereerd of AI-bewerkt (via `c2patool`).

Zo dek je in één stap zowel het **zichtbare label** als de **machine-leesbare
markering** die de EU AI Act (artikel 50) voor AI-content vereist.

Alles draait lokaal — er verlaat geen data je machine.

---

## Snel starten

```bash
# 1. (aanbevolen) virtuele omgeving
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows

# 2. Python-dependencies
python -m pip install -r requirements.txt

# 3. c2patool installeren (de C2PA-ondertekenmotor) — zie hieronder

# 4. Starten
python app.py
```

De tool opent automatisch <http://localhost:8000>. Ontbreekt een Python-pakket,
dan print `app.py` een duidelijke install-instructie en stopt.

## c2patool installeren

De tool schakelt `c2patool` (de officiële C2PA-CLI) als ondertekenmotor.
Zonder `c2patool` op je `PATH` blijft de **Start-knop uitgeschakeld**.

**Optie A — via Rust/Cargo (aanbevolen):**

```bash
cargo install c2patool
```

(Heb je nog geen Rust: installeer via <https://rustup.rs>.)

**Optie B — kant-en-klare binary:** download de nieuwste release voor jouw
platform van <https://github.com/contentauth/c2pa-rs> (map `c2patool`) en zet het
binary in een map die op je `PATH` staat (bv. `/usr/local/bin`).

Controleer: `c2patool --version`.

## ffmpeg (optioneel, alleen voor video)

Pillow kan geen videobeelden bewerken. Is `ffmpeg` aanwezig, dan wordt het
zichtbare icoon ook in `.mp4`/`.mov` gebrand; zo niet, dan slaat de tool de
zichtbare laag voor video over (met een logregel) en zet het **wel** C2PA.
Installeer op macOS met `brew install ffmpeg`.

---

## Zo werkt het

- **Template** bovenaan: sla terugkerende basiswaarden één keer op (bv.
  “Foxy — volledig AI”, “Productfoto — composite”) en herlaad ze; je hoeft dan
  alleen nog het invoer-mappad per run in te vullen. Het invoerpad wordt bewust
  *niet* in de template bewaard. Templates staan in `templates.json`.
- **Mappad (invoer)** → plak een absoluut pad. **Uitvoermap** → standaard
  `<invoer>/gelabeld`. Originelen worden nooit overschreven.
- **Bronsoort** bepaalt de `digitalSourceType`:
  - *Volledig AI-gegenereerd* → `…/trainedAlgorithmicMedia`
  - *Echte foto met AI-elementen* → `…/compositeWithTrainedAlgorithmicMedia`
- **Zichtbaar label**: kies icoon (of upload een nieuwe PNG met transparantie),
  tekst, hoek, formaat (% van beeldbreedte, met min/max px), marge en een
  optionele contrast-pill. De **live preview** toont een voorbeeldbeeld uit je
  map met de huidige instellingen.

### Vaste verwerkingsvolgorde (belangrijk)

Per bestand, in deze volgorde:

1. **eerst** het zichtbare icoon/label inbranden (Pillow / ffmpeg), dan
2. **daarna** pas C2PA-ondertekenen.

Elke pixelwijziging ná het ondertekenen breekt de C2PA-hash. Daarom gaat het
icoon er eerst op, op exact de kopie die vervolgens getekend wordt. Eén
eindbestand per beeld, met beide lagen.

### Het C2PA-manifest

Per bestand worden deze assertions gezet:

- `c2pa.actions.v2` met één `c2pa.created`-actie + `digitalSourceType`,
  `softwareAgent` (de AI-tool, evt. met model) en een UTC-`when`-timestamp.
- `stds.schema-org.CreativeWork` met `author` = jouw organisatie.
- `c2pa.ai_generative_training` met `use` = `notAllowed` (standaard) of `allowed`.
- `claim_generator` = `EXIT-Toys-C2PA-Tool/1.0`.

---

## Test-certificaat vs. productie-certificaat

- **Test-certificaat** (standaard aan, of wanneer je geen cert opgeeft): tekent
  met de ingebouwde test-credentials van `c2patool`. Het manifest is **technisch
  geldig**, maar verifiers (bv. Content Credentials / Verify) tonen de
  ondertekenaar als **“untrusted”**. Prima om te testen — **niet voor publicatie**.
- **Productie-certificaat**: een **door een CA ondertekend** certificaat (`.pem`)
  + bijbehorende private key. Vul beide velden in en kies het juiste algoritme
  (`es256` / `ps256` / `ed25519`). Alleen dan verschijnt jouw organisatie als
  vertrouwde ondertekenaar.

## Let op: metadata kan onderweg verdwijnen

Downstream-stappen (CDN's, resize-/optimalisatiescripts, ChannelEngine-export,
sommige social platforms) **strippen C2PA-metadata vaak weg**. Daarom:

- teken **zo laat mogelijk** in je pipeline, en
- **archiveer het getekende master-bestand** apart, zodat je altijd een
  geverifieerd origineel hebt.

---

## Projectstructuur

```
app.py            FastAPI-backend + verwerkingslogica
static/index.html Single-page UI (vanilla HTML/CSS/JS, geen build-stap)
requirements.txt  Python-dependencies
templates.json    Opgeslagen templates (start als lege lijst)
icons/            Icoonbestanden (PNG met transparantie); een AI-badge wordt
                  automatisch aangemaakt als de map leeg is
```

## Ondersteunde bestandstypen

`jpg`, `jpeg`, `png`, `webp` — en `mp4`, `mov` (C2PA; zichtbaar label alleen met
ffmpeg). Overige bestanden worden overgeslagen en gelogd.
