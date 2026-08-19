# EXIT-Toys-C2PA-Tool

Lokale, offline desktop-tool die je beelden — een hele map of een eigen selectie — per stuk:

1. **een zichtbaar AI-icoon/label inbrandt** (optioneel, met Pillow), en
2. **C2PA Content Credentials** toevoegt die de herkomst declareren als
   AI-gegenereerd of AI-bewerkt (via `c2patool`).

Zo dek je in één stap zowel het **zichtbare label** als de **machine-leesbare
markering** die de EU AI Act (artikel 50) voor AI-content vereist.

De **beeldverwerking draait volledig lokaal**: je beelden worden op je eigen
machine gelabeld en ondertekend en gaan naar geen enkele externe (AI-)dienst.
Alleen je **templates en iconen** worden — als je git-toegang hebt — met de
gedeelde repo gesynchroniseerd, en de app haalt bij het starten de nieuwste
code van GitHub op (zie hieronder).

---

## Installatie — zo krijg je de app

**Dit is de standaardmanier om de app te installeren.** Je hebt toegang tot deze
repo nodig (`Dutchtoysgroup/c2pa-ai-labeltool`) — vraag de beheerder of je bent
toegevoegd.

1. Pak **`install.command`** (download het uit deze repo via **Code → download**,
   of ontvang `Installeer C2PA AI-labeltool.zip` van de beheerder en pak het uit).
2. **Rechtermuisklik → Open** op `install.command` (eenmalig; vanwege
   macOS-beveiliging wordt een gewone dubbelklik geblokkeerd).
3. **Log één keer in bij GitHub** in de browser (opent vanzelf).
4. Klaar. De app wordt opgehaald, gebouwd en gestart, en staat voortaan in
   **Programma's**. Vanaf dan werkt hij zichzelf bij vanaf GitHub.

De installer regelt de rest zelf: git, het GitHub-hulpje (`gh`) en `c2patool`.
Werkt op Apple Silicon én Intel-Macs.

> **Beheerder:** deel `install.command` met collega's als **.zip** (dan blijft het
> uitvoerbaar), bijvoorbeeld via Box, en zorg dat ze toegang hebben tot de repo.

## Starten (macOS) — gewoon dubbelklikken

Er staat een echte macOS-app: **`C2PA AI-labeltool`** (in je map Programma's /
Applications, ook via Spotlight of Launchpad te vinden).

1. Dubbelklik op **C2PA AI-labeltool**.
2. De tool opent vanzelf in je browser op <http://localhost:8000>.

Meer is er niet: `c2patool` zit **in de app ingebouwd** en de eerste keer zet de
app zelf de Python-omgeving op (virtualenv + pakketten; eenmalig, internet
nodig). Python 3 moet wél aanwezig zijn — via de installer komt dat mee met
Apple's ontwikkeltools. Geen terminal.

> **Versie-indicator:** de header toont of je versie gelijk is aan GitHub
> (“Up-to-date”) of dat er nieuwere code klaarstaat (“Update beschikbaar” —
> heropen de app om bij te werken).

> **Zelf bijwerken:** elke keer dat je de app opent, haalt hij eerst de
> nieuwste versie van GitHub op (`Dutchtoysgroup/c2pa-ai-labeltool`) en start
> die. GitHub is dus de bron; je Mac draait een automatisch bijgewerkte kopie.
> Offline? Dan start hij gewoon de laatste lokale versie.

> De app is een lichte “launcher” die de code in `~/c2pa-ai-tool` start. Blijft
> de app op de achtergrond draaien; elke keer dat je 'm opent, komt de tool weer
> in beeld.

### App (opnieuw) bouwen

Verplaats je het project of wil je de app opnieuw aanmaken:

```bash
bash ~/c2pa-ai-tool/macapp/build_mac_app.sh
```

Dat zet `C2PA AI-labeltool.app` in `/Applications` (of `~/Applications`) met
`c2patool` meegebundeld.

## Handmatige installatie (gevorderd)

Liever zonder de installer? Op een Mac met git + Python 3:

```bash
git clone https://github.com/Dutchtoysgroup/c2pa-ai-labeltool.git ~/c2pa-ai-tool
cd ~/c2pa-ai-tool
bash macapp/build_mac_app.sh
```

Dat bouwt dezelfde app (met `c2patool` automatisch meegedownload).

## Starten via de terminal (alternatief / andere platforms)

```bash
python3 -m venv .venv
source .venv/bin/activate        # macOS/Linux
# .venv\Scripts\activate         # Windows
python -m pip install -r requirements.txt
python app.py                    # opent http://localhost:8000
```

Ontbreekt een Python-pakket, dan print `app.py` een duidelijke install-instructie
en stopt. Voor deze route moet `c2patool` wél op je `PATH` staan (zie hieronder).

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
- **Automatisch delen via GitHub**: zodra je een template opslaat, bijwerkt of
  verwijdert, of een icoon uploadt, wordt dat direct gecommit en naar de repo
  gepusht. Zo ziet iederéén die de tool gebruikt dezelfde templates en iconen.
  Een melding in beeld bevestigt of het delen via GitHub gelukt is; lukt het
  pushen niet (bijv. offline of geen push-rechten), dan blijft de wijziging in
  elk geval lokaal bewaard.
- **Invoer** → kies wat je verwerkt:
  - **Map…** opent een Finder-mapkiezer (of plak een absoluut pad); de hele map
    wordt verwerkt (met *Ook submappen* eventueel recursief).
  - **Bestanden…** opent een Finder-bestandskiezer waarmee je één of meer losse
    beelden selecteert — dan worden **alléén die bestanden** verwerkt. De
    invoermap wordt afgeleid van de map van het eerste bestand.
- **Uitvoermap** → standaard `<invoer>/gelabeld`; originelen worden dan nooit
  overschreven.
- **Originelen vervangen** (aanvinken) → schrijft het gelabelde + ondertekende
  bestand **atomair terug over het origineel** in plaats van naar een uitvoermap.
  Onomkeerbaar en zonder kopie, dus dubbel gezekerd: je vinkt het zelf aan én
  bevestigt bij Start in een pop-up (waarin de veilige **Annuleren**-knop bewust
  de opvallende groene is). Maak vooraf een back-up.
- **Bronsoort** bepaalt de `digitalSourceType`:
  - *Volledig AI-gegenereerd* → `…/trainedAlgorithmicMedia`
  - *Echte foto met AI-elementen* → `…/compositeWithTrainedAlgorithmicMedia`
- **Zichtbaar label**: kies icoon (of upload een nieuwe PNG met transparantie),
  tekst, hoek, formaat (% van beeldbreedte, met min/max px), marge en een
  optionele contrast-pill. De **live preview** toont hoe het label valt en werkt
  meteen mee met je instellingen. Heb je meerdere beelden geselecteerd, dan wordt
  de preview een **carrousel**: blader met de pijltjes links/rechts door je
  selectie (met een teller, bv. `2 / 5`).
- **Verplicht veld leeg?** Klik je op Start terwijl de invoer of AI-tool leeg is,
  dan krijgt dat veld een **rode rand** naast de melding. De badges rechtsboven
  tonen de status van `c2patool` en `ffmpeg`; klik op de `c2patool`-badge voor
  uitleg over wat het is en waarom het nodig is.

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
  met het **meegeleverde es256 test-certificaat** in `certs/test/`
  (zie `certs/test/README.md`). Het manifest is **cryptografisch geldig**
  (`validation_state: Valid`), maar verifiers (bv. Content Credentials / Verify)
  tonen de ondertekenaar als **“untrusted”** (`signingCredential.untrusted`).
  Prima om te testen — **niet voor publicatie**.
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
templates.json    Opgeslagen templates — automatisch gedeeld via de repo
icons/            Icoonbestanden (PNG met transparantie); een AI-badge wordt
                  automatisch aangemaakt als de map leeg is
certs/test/       Meegeleverd es256 TEST-certificaat (untrusted, alleen testen)
macapp/           Bouwscript + launcher + icoon voor de dubbelklik-macOS-app
```

## Ondersteunde bestandstypen

`jpg`, `jpeg`, `png`, `webp` — en `mp4`, `mov` (C2PA; zichtbaar label alleen met
ffmpeg). Overige bestanden worden overgeslagen en gelogd.
