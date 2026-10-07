# EXIT-Toys-C2PA-Tool

Lokale, offline desktop-tool die je beelden — een hele map of een eigen selectie — per stuk:

1. **een zichtbaar AI-icoon/label inbrandt** (optioneel, met Pillow), en
2. **C2PA Content Credentials** toevoegt die de herkomst declareren als
   AI-gegenereerd of AI-bewerkt (via `c2patool`).

Zo dek je in één stap zowel het **zichtbare label** als de **machine-leesbare
markering** die de EU AI Act (artikel 50) voor AI-content vereist.

De **beeldverwerking draait volledig lokaal**: je beelden worden op je eigen
computer gelabeld en ondertekend en gaan naar geen enkele externe (AI-)dienst.

---

## Installeren

Download de app op **<https://dashboard-exit.com/labeltool>** (zonder inlog):

- **macOS** — `.dmg` voor een Mac met Apple-chip of met Intel-processor. Open
  hem en sleep **C2PA AI-labeltool** naar Programma's. De app is ondertekend en
  door Apple gecontroleerd, dus hij opent zonder waarschuwing.
- **Windows** — `Setup.exe`. Installeert alleen voor jou, zonder
  beheerdersrechten. De installer is nog niet ondertekend: kies bij "Windows
  heeft uw pc beschermd" voor **Meer informatie** → **Toch uitvoeren**.

Alles zit in de app: Python, de pakketten en `c2patool`. Je hebt geen
GitHub-account, git of Python nodig.

## Starten

Dubbelklik op **C2PA AI-labeltool** (Programma's, Spotlight of Launchpad op de
Mac; Startmenu of bureaublad op Windows). De tool opent in je browser op
<http://localhost:8000>. De server blijft op de achtergrond draaien; opnieuw
dubbelklikken opent de tool weer.

## Bijwerken

Gaat vanzelf. Bij elke start kijkt de app op
`https://dashboard-exit.com/labeltool/update` of er een nieuwere versie is en
installeert die dan eerst. Op de Mac alleen als de nieuwe versie door hetzelfde
team is ondertekend en door Apple is gecontroleerd. Loopt er nog een
verwerking, dan wacht de update tot de volgende start. De versie-badge in de
tool toont of je de nieuwste hebt.

## Templates en iconen

- **Gedeelde** templates en iconen (zoals "EXIT Toys - Standaard Ai") zitten in
  de app en komen met elke update mee. Ze staan in deze repo: `templates.json`
  en `icons/`. Wil je er een toevoegen of aanpassen, wijzig het hier en maak
  een nieuwe release.
- **Eigen** templates en iconen bewaart de app op je eigen computer:
  `~/Library/Application Support/C2PA AI-labeltool` (macOS) of
  `%APPDATA%\C2PA AI-labeltool` (Windows). Een gedeelde template aanpassen
  maakt er een eigen kopie van; verwijderen verbergt hem alleen voor jou.
- Had je de oude versie (de git-installatie in `~/c2pa-ai-tool`), dan neemt de
  app bij de eerste start je eigen templates en iconen daaruit over. Die map kun
  je daarna weggooien.

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
- **Gedeelde en eigen templates**: zie [Templates en iconen](#templates-en-iconen).
  Draai je de tool vanuit de broncode (zie Ontwikkelen), dan wordt een
  opgeslagen template of geüpload icoon nog wel meteen gecommit en gepusht.
- **Invoer** → kies wat je verwerkt:
  - **Map…** opent een mapkiezer (Finder op macOS, Verkenner op Windows), of plak een absoluut pad; de hele map
    wordt verwerkt (met *Ook submappen* eventueel recursief).
  - **Bestanden…** opent een bestandskiezer (Finder/Verkenner) waarmee je één of meer losse
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

## Ontwikkelen

### Een nieuwe versie uitbrengen

1. Zet het nieuwe versienummer in `VERSION` (bijv. `2.0.1`) en commit.
2. Tag en push: `git tag v2.0.1 && git push origin main v2.0.1`.
3. De workflow `Release` bouwt de app voor macOS (Apple-chip en Intel,
   ondertekend en genotariseerd met het Developer ID van Dutch Toys Group) en
   Windows, en publiceert ze met `latest.json` als GitHub Release. De
   downloadpagina en de update-feed op het dashboard pakken die vanzelf op.

Pull requests bouwen en testen de app ook, zonder te ondertekenen of te
publiceren. Benodigde secrets: `CSC_LINK` (base64 van de .p12), `CSC_KEY_PASSWORD`,
`APPLE_API_KEY_P8`, `APPLE_API_KEY_ID` en `APPLE_API_ISSUER`, dezelfde als bij
EXIT SEO Crawler.

### Lokaal bouwen

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r packaging/requirements-build.txt
# c2patool in build/c2patool/ zetten (zie de workflow), dan:
.venv/bin/pyinstaller --noconfirm --distpath dist --workpath build/pyinstaller packaging/c2pa-labeltool.spec
```

`dist/C2PA AI-labeltool.app --selftest` controleert of alles in de app zit.

### Vanuit de broncode draaien

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python app.py          # opent http://localhost:8000
```

`c2patool` moet dan zelf op je `PATH` staan (`cargo install c2patool`, of een
binary van <https://github.com/contentauth/c2pa-rs>). In deze modus staan
templates en iconen in de repo zelf en worden wijzigingen meteen gecommit en
gepusht. Zo werkt ook de oude installatie (`install.command`, `install.bat`),
die bij elke start `git pull` doet; die blijft werken.

De broncode moet daarom op **Python 3.9 t/m 3.13** draaien: veel oude
installaties gebruiken de ingebouwde Python 3.9 van macOS. Dus **geen**
`dict | None` in annotaties op FastAPI-endpoints (gebruik `Optional[dict]`) en
geen `match`/`case`. Controle vóór je pusht:

```bash
/usr/bin/python3 -m py_compile app.py updater.py desktop.py
```

## Projectstructuur

```
app.py            FastAPI-backend + verwerkingslogica
desktop.py        Startpunt van de app: update, server starten, browser openen
updater.py        Versie, gebruikersmap en de update-feed
VERSION           Versienummer van de app
static/index.html Single-page UI (vanilla HTML/CSS/JS, geen build-stap)
requirements.txt  Python-dependencies
templates.json    Gedeelde templates (zitten in de app)
icons/            Gedeelde iconen (PNG met transparantie)
certs/test/       Meegeleverd es256 TEST-certificaat (untrusted, alleen testen)
packaging/        PyInstaller-recept, Mac-entitlements, Windows-installer, latest.json
.github/workflows Release-workflow
macapp/, winapp/  Oude installatie: launcher + bouwscripts (git pull bij elke start)
install.*         Oude installers (git + GitHub-login)
```

## Ondersteunde bestandstypen

`jpg`, `jpeg`, `png`, `webp` — en `mp4`, `mov` (C2PA; zichtbaar label alleen met
ffmpeg). Overige bestanden worden overgeslagen en gelogd.

Bestanden **zonder (zichtbare) extensie** in de naam worden herkend op basis van
hun inhoud en gewoon verwerkt; de uitvoer **behoudt exact dezelfde naam** — er
wordt geen extensie toegevoegd.
