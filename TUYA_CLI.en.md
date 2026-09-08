*[Leia em português (BR)](TUYA_CLI.md)*

# Python CLI + Tuya Cloud API — full guide

> This document is only needed if you want to use this repository's
> **Python CLI** with a Tuya Smart IR Hub (learning, sending, and
> importing codes via the Cloud API). If you just want the AUN ET30
> remote's IR codes to use however you like, see [README.md](README.en.md)
> — none of this is required.

Python CLI that controls the AUN ET30 projector through a Tuya Smart
IR Hub via the **Cloud API**. Supports three ways to obtain an IR
code:

1. **Real learning** — point the physical remote at the Hub and
   capture the real signal. Use this for buttons that still work on
   your remote.
2. **Assisted inference** — for physically broken buttons (which will
   never transmit anything), generates plausible candidates from
   already-learned neighboring buttons and lets you test each one
   live, pointing the Hub at the projector, until you confirm which
   one works.
3. **Synthetic placeholder** — algorithmically generated example codes
   (standard NEC protocol), used only as a fallback before any real
   learning happens.

## How this actually works

Tuya's Cloud API doesn't have a single endpoint that accepts "raw NEC
hex" or "learn and resend in real time" as one thing. IR commands go
through the `learning-codes` family of endpoints:

- `PUT /v2.0/infrareds/{id}/learning-state?state=true` — turns on
  learning mode on the Hub.
- `GET /v2.0/infrareds/{id}/learning-codes?learning_time=...` —
  checks whether something was captured (used to learn real codes
  from the physical remote).
- `POST /v2.0/infrareds/{id}/learning-codes` — saves a code and
  generates a `remote_id` ("virtual remote").
- `POST /v2.0/infrareds/{id}/remotes/{remote_id}/learning-codes` —
  fires a code (learned or generated) in real time.
- `GET /v2.0/infrareds/{id}/remotes/{remote_id}/learning-codes` —
  lists all codes already saved for a `remote_id` (used to import
  what the Tuya Smart/Smart Life app already learned).

Both learned and synthetic codes use the same binary format: a
base64 string with the list of pulse durations (mark/space, in
microseconds), compressed with a FastLZ variant. That's why the
project has two complementary pieces:

- `nec_encoder.py` — generates that format from a hexadecimal NEC
  code (used for placeholders and inference candidates).
- `nec_decoder.py` — does the reverse: decodes what the Hub captures
  from the physical remote back into readable NEC hex (used for
  learning and importing, so you can see and confirm the real code
  for each button).

Both were validated byte-for-byte (round-trip encode → decode)
against the publicly documented reverse-engineering of Tuya's format,
also used by projects like tinytuya and IRTuya.

## 1. Step by step on the Tuya portal

> The portal was renamed — today it's **platform.tuya.com** (the old
> link `iot.tuya.com` may not load anymore depending on your
> network/DNS).

### 1.1 Create an account and Cloud project
1. Go to [platform.tuya.com](https://platform.tuya.com) and create/sign in to your developer account.
2. Go to **Cloud** (side menu) → **Create Cloud Project**.
3. Fill in:
   - **Project Name**: any name, e.g. `IR Projector AUN ET30`.
   - **Industry**: `Smart Home`.
   - **Development Method**: `Custom Development` (this is what gives you Cloud API access with Access ID/Secret).
   - **Data Center**: choose the region where your Tuya Smart/Smart Life app account is registered (must match, otherwise the device won't show up to link).

### 1.2 Get the Access ID and Access Secret
1. Open the created project → **Overview** tab.
2. In the **Authorization Key** section you'll see:
   - **Access ID / Client ID** → goes into `TUYA_ACCESS_KEY`
   - **Access Secret / Client Secret** → click "Show" → goes into `TUYA_SECRET_KEY`

### 1.3 Enable the required API services
1. On the same project page, go to the **Service API** tab.
2. Confirm the following services are **subscribed/enabled**
   (otherwise calls will return a permission error):
   - **IoT Core**
   - **Authorization** (Authentication)
   - **IR Control Hub Open Service** (or "Infrared Control Hub" /
     "Universal Infrared Open Service", the name varies by region)
3. If any is missing, use **Go to Subscribe** to add it (free on the Trial/Basic plan).

### 1.4 Link your IR Hub to the project and get the Device ID
1. Still in the project, go to **Devices → Link Tuya App Account** (or "Link My App").
2. Scan the QR code with the **Tuya Smart** app (Me → scan icon at the top).
3. Once linked, your devices will show up in the **All Devices** list.

Usually two relevant devices show up:
- **Smart IR** — the real physical Hub. Its Device ID goes into `TUYA_DEVICE_ID`.
- A virtual remote the app itself already created/partially learned
  (e.g. "Projector"). Its Device ID is used as the `remote_id` in menu
  option **5** (importing codes already learned by the app).

If `TUYA_ENDPOINT` in `.env.example` doesn't match your chosen Data
Center, adjust it per the list of regions in the file itself.

## 2. Installation

```bash
python3 -m venv .venv && source .venv/bin/activate   # optional, but recommended
pip install -r requirements.txt
```

## 3. Configuration

```bash
cp .env.example .env
# edit .env with TUYA_ACCESS_KEY, TUYA_SECRET_KEY, TUYA_ENDPOINT, TUYA_DEVICE_ID
```

If any variable is missing, the script will prompt for it
interactively in the terminal at runtime (less convenient for repeat
use — prefer `.env`).

## 4. Usage

```bash
python3 main.py
```

Main menu:

```
1) Send command
2) Learn a button's code (physical remote -> Hub)
3) Infer + test a broken button's code
4) View code status (codebook)
5) Import codes from an existing virtual remote (app)
m) Send a manual NEC code (hex)
q) Quit
```

### 4.0 Import what the app already learned (option 5) — start here

If you already tried learning buttons through the Tuya Smart app,
start with option **5**. Paste that virtual remote's Device ID when
prompted. The script lists each saved code, shows the decoded hex,
and you map it to the corresponding button. This avoids relearning
everything from scratch via the CLI.

### 4.1 Learn the buttons that work (option 2)

Flow: choose the button → point the physical remote straight at the
Hub → press ENTER → press the button on the remote quickly. The
script waits up to 20s for a signal. The captured code is decoded (if
it's standard NEC) and saved to `codebook.json`.

Use this for buttons that import (option 5) didn't bring in.

### 4.2 Infer physically broken buttons (option 3)

For buttons that don't transmit anything physically, they can't be
"learned" — the script generates a list of plausible candidates based
on bit patterns observed in already-learned/imported neighboring
buttons and lets you test each one live:

1. Choose the broken button.
2. For each candidate, the script asks if it can send it — point the
   Hub at the device and watch.
3. If the device reacts correctly, confirm with `s`. The code is
   saved as `inferred_confirmed` in the codebook and from then on
   behaves like any other learned code.
4. If no candidate works, the script warns you — you may need to
   learn/import more neighboring buttons first (more data = better
   heuristic) or the real protocol isn't pure NEC.

**Honest warning:** for the AUN ET30 remote specifically, this bit
heuristic **did not work** — see
["Lessons from the AUN ET30"](#6-lessons-from-the-aun-et30-what-actually-worked-and-what-didnt)
below for why, and what actually worked.

### 4.3 View status (option 4)

Shows, for each button, whether the code is: learned, imported from
the app, inferred and confirmed, placeholder (unconfirmed), or still
has no code at all.

### 4.4 Manual code (option `m`)

Accepts any 32-bit NEC code (8 hex digits), with or without the `0x`
prefix — useful for quickly testing hypotheses without going through
the inference flow.

## 5. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `[AUTH ERROR]` | Wrong Access ID/Secret or wrong region endpoint | Check the Authorization Key section and the project's Data Center |
| Permission error / "no permission" | API service not subscribed on the project | Service API tab → subscribe to "IR Control Hub Open Service" |
| `TUYA_DEVICE_ID` not found / device offline | Hub not linked to the project or offline | Redo Link Tuya App Account and confirm the Hub is online in the app |
| Option 5 (import) errors/returns empty list | The virtual remote's Device ID might not work directly as `remote_id` | Confirm you pasted the right Device ID; if it persists, skip importing and learn directly (option 2) |
| `[NO SIGNAL]` when trying to learn a button | Button is really broken, remote out of range, or weak battery | Replace the battery, move the remote closer to the Hub; if it persists, the button is dead — use inference (option 3) |
| Command accepted but device doesn't react | Incompatible NEC timing, hub out of IR range, protocol isn't pure NEC, **or the payload is in the wrong format** (see section 6) | Move the hub closer to the device; manually test `necx2=True`; for buttons learned with `checksum_ok=False`, the signal might not be standard NEC — in that case resending still works (it uses the captured base64, not the decoding) |
| Invalid `remote_id` after deleting the remote in the app | Stale local cache | The script tries to reprovision automatically; if that fails, delete `.tuya_remote_cache.json` |
| No inference candidate works | Heuristic didn't match the real remote's chip | Learn more neighboring buttons (more data improves candidates) or try manual values via option `m` |

## 6. Lessons from the AUN ET30: what actually worked (and what didn't)

This section documents the real problems hit while using this CLI
against a real Hub — useful if you're adapting this code for another
device/Hub, even if the AUN ET30's specific codes aren't what you're
after.

### 6.1 The most serious bug: wrong payload format, silent failure

`nec_encoder.py` originally produced `base64 + FastLZ compressed`
(the format documented in several Tuya reverse-engineering projects),
but the endpoint
`POST /v2.0/infrareds/{id}/remotes/{remote_id}/learning-codes`
**on this specific Hub** expects **raw hex** (uint16 little-endian
durations, uncompressed and without base64). Worse: the API
**accepts** the base64 and responds `success: true` — but the Hub
doesn't actually emit the IR. No error, no warning, simply nothing
happens on the device.

How it was diagnosed: sending a **known-working** code through both
paths. Via raw hex the device reacted; via `encode_nec()` nothing
happened — a simple control test that should be done any time a
"correct code" seems not to work.

Fix: `encode_nec()` now generates raw hex, using timings from a
**mold** extracted from a real code captured by the app (see
[README.md](README.en.md#protocol)), instead of the NEC "textbook"
values. The old encoder is still available as
`encode_nec_base64_legacy()`, for reference only — **do not use it to
send real commands**.

**Lesson for any Tuya-based IR Hub:** before assuming a code is
wrong, confirm the payload format your Hub's specific endpoint
expects, by testing a *known-working* code through both paths
(synthesis vs. verbatim capture).

### 6.2 Three other real bugs found

1. **`nec_decoder.py` only knew how to decode one of the two formats
   Tuya uses.** `durations_from_tuya_code()` assumed every code came
   as base64 + FastLZ compressed. But the
   `GET /remotes/{remote_id}/learning-codes` endpoint returns codes
   as **raw hex**. This crashed the import option with an unhandled
   exception. Fixed: it now tries base64+FastLZ first and falls back
   to raw hex if decompression fails.

2. **`tuya_client.py._provision_remote` parsed the response wrong.**
   It expected `resp["result"]["remote_id"]`, but the API returns
   `resp["result"]` as the `remote_id` string itself (no nesting).

3. **Signature error (`sign invalid`, code 1004) in
   `enable_learning`/`disable_learning`.** These functions called
   `openapi.put(path, {})` passing an empty dict as the body. The
   `requests` library, given `json={}` (empty dict, not `None`),
   serializes and sends `"{}"` as the literal body — mismatching the
   HMAC signature Tuya computes (which treats an empty body as the
   hash of an empty string). Fixed by passing `None` instead of `{}`.

### 6.3 Physically broken buttons: when bit inference isn't enough

Two buttons on the AUN ET30 remote (Left and Volume-) were physically
broken and transmitted nothing. The bit-inference heuristic
(`inference.py`) assumes cheap NEC remotes map physically adjacent
buttons to neighboring bits of the command byte — but that turned out
**not to hold** for this remote: an exhaustive scan of all 256
possible commands found nothing at the time, because the generated
payload was in the wrong format (section 6.1). Once the encoder was
fixed, the correct values were found by manual scanning with visual
confirmation on every shot — not by heuristic.

The real command pattern (see the table in
[README.md](README.en.md#code-table)) shows the key numbering follows
the chip matrix's scan order, not the buttons' physical position or
logical grouping — so "obvious" pairs like Volume+/Volume- can be far
apart in bit terms.

**Careful when testing candidates:** don't inject extra commands "to
help visualize" (e.g. sending Volume+ before testing a Volume-
candidate to open the on-screen bar) — this contaminates the test and
can produce false positives. Always test one isolated command at a
time.

### 6.4 Exporting the codebook to the Tuya Smart app

After mapping everything, you can create a **real** virtual remote
inside the Tuya Smart app, with all keys persisted — not just one-off
firing, it shows up there like a normal remote.

The catch: the `POST /v2.0/infrareds/{id}/learning-codes` endpoint
(which creates a new remote and saves the list of keys) requires a
**`key`** field on each item in `codes` — it's mandatory per the
[official documentation](https://developer.tuya.com/en/docs/cloud/837dd9e219?id=Kb3oeazmud83g),
but easy to miss because the API **silently accepts** a payload
without it and still responds `success: true` — except no key
actually gets saved. `key_name` alone isn't enough; it's just an
optional display label.

```python
codes = [{"key": name, "key_name": name, "code": entry["code_b64"]}
         for name, entry in codebook.all_entries().items()]

body = {
    "category_id": 6,      # Projector, in Tuya's taxonomy
    "brand_id": 999999,    # "Other" / generic
    "remote_name": "My Custom Remote",
    "codes": codes,
}
client.openapi.post(f"/v2.0/infrareds/{device_id}/learning-codes", body)
```

#### The app's icons (arrows, OK, volume, etc.) — the `id` field matters

Creating the remote with the right `key` (e.g. `navigate_up`,
`volume_down`, `power`) is already enough for the API to accept it and
for the key to show up with the right name — but the app's **graphic
icons** (the D-pad, power/volume/mute buttons) stay **disabled** if
each code's `id` field doesn't match the standard ID from Tuya's
internal catalog. Without an explicit `id`, the API auto-generates a
sequential counter (1, 2, 3...) that doesn't correspond to anything —
the app accepts it and shows the key in the "More" (extras) list, but
doesn't link it to the icon.

Standard IDs found by comparing against a remote the Tuya app itself
had already built correctly (category 6 = Projector):

| `key` | `id` | function |
|---|---|---|
| `power` | 1 | Power |
| `ok` | 42 | OK |
| `menu` | 45 | Menu |
| `navigate_up` | 46 | Up |
| `navigate_down` | 47 | Down |
| `navigate_left` | 48 | Left |
| `navigate_right` | 49 | Right |
| `volume_up` | 50 | Volume+ |
| `volume_down` | 51 | Volume- |
| `mute` | 106 | Mute |
| `back` | 116 | Back |

Buttons without a standard icon (e.g. Input, Rewind, Forward,
Play/Pause) have no fixed `id` — they use any unique number outside
that range (e.g. `900001`, `900002`...), and remain accessible from
the app's "More" list.

**Watch out for `id` collisions:** if any code in the batch doesn't
have an explicit `id`, the API auto-generates a sequential one
(1, 2, 3...) that can collide with a fixed `id` used by another code
in the same batch — whichever is processed last "wins" and the other
code **silently disappears** (no error, no warning). Always provide
an explicit, unique `id` for every code in the batch, even the ones
without a standard icon.

## 7. Project structure

```
├── .env.example         # environment variable template
├── requirements.txt
├── config.py             # loads/validates config from .env
├── nec_encoder.py         # converts NEC hex -> Tuya binary format
├── nec_decoder.py         # converts Tuya binary format -> NEC hex
├── codebook.py            # persists codes per button (codebook.json)
├── inference.py           # inference heuristics for broken buttons
├── tuya_client.py         # authentication, sending, learning, importing
├── main.py                # interactive CLI
├── codebook.json          # created automatically (codes per button)
└── .tuya_remote_cache.json  # created automatically (remote_id cache)
```

**Helper scripts** (project root, outside `main.py`'s main flow,
created during the AUN ET30 investigation and useful as reference for
manual scans on other devices):

- `scan_missing_buttons.py` / `remote_voldown.py` — batch scanning or
  numbered candidate testing, meant to run locally without a
  per-command time limit.
- `test_candidates_interactive.py` — interactive menu to test and
  save candidates one at a time.
- `remote.py` — terminal "remote control" (Windows, via `msvcrt`):
  press a key and the command fires instantly, no ENTER needed.
