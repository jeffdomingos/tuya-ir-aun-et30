*[Leia em português (BR)](README.md)*

# Tuya IR CLI — AUN ET30 Projector Control

Python CLI that controls the AUN ET30 projector through a Tuya Smart
IR Hub via the **Cloud API**. Supports three ways to obtain an IR
code:

**Status: project complete.** All 15 remote buttons (13 physical +
the 2 broken by battery corrosion, LEFT and VOLUME-) are mapped,
confirmed live on the projector, and saved in `codebook.json`. See
section [8. Real bugs found and fixed](#8-real-bugs-found-and-fixed)
and [9. How LEFT and VOLUME- were solved](#9-how-left-and-volume--were-solved)
to understand what wasn't obvious in the original implementation.

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
   - **Data Center**: choose the region where your Tuya Smart/Smart Life app account is registered (must match, otherwise the device won't show up to link). In Brazil, this is usually **Western America Data Center**.

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

In this project's case, two devices showed up:
- **Smart IR** — the real physical Hub. Its Device ID goes into `TUYA_DEVICE_ID`.
- **Projector** — a virtual remote the app itself already created/
  partially learned. Its Device ID is used as the `remote_id` in menu
  option **5** (importing codes already learned by the app).

If `TUYA_ENDPOINT` in `.env.example` doesn't match your chosen Data
Center, adjust it per the list of regions in the file itself.

## 2. Installation

```bash
cd tuya_ir_cli
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

If you already tried learning buttons through the Tuya Smart app (as
was the case here, with the "Projector" remote), start with option
**5**. Paste that virtual remote's Device ID when prompted. The
script lists each saved code, shows the decoded hex, and you map it
to the corresponding button in this project (Power, Up, Down, etc.).
This avoids relearning everything from scratch via the CLI.

### 4.1 Learn the buttons that work (option 2)

Buttons supported for learning: `POWER`, `MUTE`, `REWIND`,
`PLAY/PAUSE`, `FORWARD`, `UP`, `RIGHT`, `DOWN`, `OK`, `BACK`,
`MENU`, `INPUT`, `VOLUME+`.

Flow: choose the button → point the physical remote straight at the
Hub → press ENTER → press the button on the remote quickly. The
script waits up to 20s for a signal. The captured code is decoded (if
it's standard NEC) and saved to `codebook.json`.

Use this for buttons that import (option 5) didn't bring in.

### 4.2 Infer the broken buttons: LEFT and VOLUME- (option 3)

Since these buttons don't transmit anything physically, they can't be
"learned" — the script generates a list of plausible candidates based
on bit patterns observed in already-learned/imported neighboring
buttons (e.g. the bit difference between UP/DOWN is also tested on
RIGHT and VOLUME+) and lets you test each one live:

1. Choose `LEFT` or `VOLUME -`.
2. For each candidate, the script asks if it can send it — point the
   Hub at the projector and watch.
3. If the projector reacts correctly (cursor moves left / volume goes
   down), confirm with `s`. The code is saved as `inferred_confirmed`
   in the codebook and from then on behaves like any other learned
   code.
4. If no candidate works, the script warns you — you may need to
   learn/import more neighboring buttons first (more data = better
   heuristic) or the real protocol isn't pure NEC.

**Inference prerequisites:**
- For `LEFT`: have `UP`, `DOWN` and/or `RIGHT` first.
- For `VOLUME -`: have `VOLUME+` first (and ideally `UP`/`DOWN` too,
  to reuse the bit pattern).

### 4.3 View status (option 4)

Shows, for each of the 15 buttons, whether the code is: learned,
imported from the app, inferred and confirmed, placeholder
(unconfirmed), or still has no code at all.

### 4.4 Manual code (option `m`)

Accepts any 32-bit NEC code (8 hex digits), with or without the `0x`
prefix — useful for quickly testing hypotheses without going through
the inference flow.

## 5. Project structure

```
tuya_ir_cli/
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

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `[AUTH ERROR]` | Wrong Access ID/Secret or wrong region endpoint | Check the Authorization Key section and the project's Data Center |
| Permission error / "no permission" | API service not subscribed on the project | Service API tab → subscribe to "IR Control Hub Open Service" |
| `TUYA_DEVICE_ID` not found / device offline | Hub not linked to the project or offline | Redo Link Tuya App Account and confirm the Hub is online in the app |
| Option 5 (import) errors/returns empty list | The "Projector" Device ID might not work directly as `remote_id` | Confirm you pasted the right Device ID; if it persists, skip importing and learn directly (option 2) |
| `[NO SIGNAL]` when trying to learn a button | Button is really broken, remote out of range, or weak battery | Replace the battery, move the remote closer to the Hub; if it persists, the button is dead — use inference (option 3) |
| Command accepted but projector doesn't react | Incompatible NEC timing, hub out of IR range, or protocol isn't pure NEC | Move the hub closer to the projector; manually test `necx2=True`; for buttons learned with `checksum_ok=False`, the signal might not be standard NEC — in that case resending still works (it uses the captured base64, not the decoding) |
| Invalid `remote_id` after deleting the remote in the app | Stale local cache | The script tries to reprovision automatically; if that fails, delete `.tuya_remote_cache.json` |
| No inference candidate works | Heuristic didn't match the real remote's chip | Learn more neighboring buttons (more data improves candidates) or try manual values via option `m` |

## 7. Notes on inference

Inference is **not a real reading** — it's an educated guess based on
how cheap NEC remotes usually map physically adjacent buttons to bits
of the command byte. It's only ever offered for live testing, never
applied "blind": you always confirm visually on the projector before
any code is saved as final.

In practice, for this specific remote, bit-heuristic inference
**did not work** — the chip doesn't follow a simple, predictable
pattern (see section 9 below for what actually worked).

## 8. Real bugs found and fixed

During testing against the real Hub (never validated before, only
against mocks), four real bugs showed up in the original
implementation — the first one serious enough to invalidate hours of
testing:

0. **`nec_encoder.py` generated the wrong format — silent failure.**
   The encoder produced `base64 + FastLZ compressed` (the format
   documented in several Tuya reverse-engineering projects), but the
   endpoint
   `POST /v2.0/infrareds/{id}/remotes/{remote_id}/learning-codes`
   **on this Hub** expects **raw hex** (uint16 little-endian
   durations, uncompressed and without base64). Worse: the API
   **accepts** the base64 and responds `success: true` — but the Hub
   doesn't actually emit the IR. No error, no warning, simply nothing
   happens on the device.

   Consequence: the entire brute-force scan done to discover the
   broken buttons was pointless. The correct code for the LEFT button
   (`0x00FF9B64`) had already been individually tested and "didn't
   work" — when in fact the payload was in the wrong format. The same
   code, sent verbatim as raw hex, works perfectly.

   How it was diagnosed: sending a **known-working** code (DOWN,
   `0x00FF9A65`) through both paths. Via raw hex the cursor moved
   down; via `encode_nec()` nothing happened. A simple control test
   that should have been done from the start.

   Fix: `encode_nec()` now generates raw hex, using timings from a
   **mold** extracted from a real code captured by the app
   (`8889 / 4513 / 563 / 1703`, instead of the "textbook" values
   `9000 / 4500 / 560 / 1690`). Generating `0x00FF9B64` with this mold
   produces a payload **byte-for-byte identical** to the app's —
   validated by exact comparison, and the module's `__main__` runs
   this assertion. The old encoder is still available as
   `encode_nec_base64_legacy()`, for reference only.

The other three:

1. **`nec_decoder.py` only knew how to decode one of the two formats
   Tuya uses.** `durations_from_tuya_code()` assumed every code came
   as base64 + FastLZ compressed (the format `nec_encoder.py`
   produces, used when *provisioning* a new virtual remote). But the
   `GET /remotes/{remote_id}/learning-codes` endpoint — used both to
   import codes from the app and to list what's already been learned
   — returns codes as **raw hex** (uncompressed durations, no
   base64). This crashed the import option with an unhandled
   exception. Fixed: it now tries base64+FastLZ first and falls back
   to raw hex if decompression fails.

2. **`tuya_client.py._provision_remote` parsed the response wrong.**
   It expected `resp["result"]["remote_id"]`, but the API returns
   `resp["result"]` as the `remote_id` string itself (no nesting).
   Every time the script provisioned a new virtual remote, it broke
   with `TypeError: string indices must be integers`.

3. **Signature error (`sign invalid`, code 1004) in `enable_learning`/
   `disable_learning`.** These functions called `openapi.put(path, {})`
   passing an empty dict as the body. Tuya's library computes the HMAC
   signature treating an empty body as the hash of an empty string,
   but the `requests` library, given `json={}` (empty dict, not
   `None`), serializes and sends `"{}"` as the literal body —
   mismatching what was signed. Result: every attempt at real
   learning (option 2) failed with a signature error. Fixed by passing
   `None` instead of `{}`.

## 9. How LEFT and VOLUME- were solved

**LEFT:** the bit-based inference heuristic never found the right
code — in fact, an exhaustive scan of **all 256 possible commands**
at address `0x00` (the same as the other 13 buttons) found nothing,
even though the correct code (`0x9B`) was technically inside that
range and had been tested individually at the time. What actually
solved it: the user managed to register the Left button directly in
the **Tuya Smart app**, through the "combine code" flow of the
"Projector" remote template. This became visible via the API
(`GET /remotes/{remote_id}/learning-codes` on the "Projector"
`remote_id`) as a new entry with `key_name='navigate_left'`.

Interestingly, resending the same 4-byte code (`0x00FF9B64`)
**resynthesized from scratch** by `nec_encoder.encode_nec()` did not
make the projector react — it only worked when resending the payload
**verbatim** (the exact string the API returned, without
re-encoding). In other words, for this specific remote, the "textbook"
NEC encoding didn't reproduce 100% of what the hardware expects
(probably some timing nuance); the actual 4-byte value was correct,
but the synthesized pulses weren't bit-for-bit identical to the
originals.

**VOLUME- (`0x00FF9C63`):** solved by manual scanning after the
encoder bug (item 0 above) was fixed. The value `0x9C` had actually
been tested at the very beginning of the project — and "failed",
because the payload went out in the wrong format.

An intermediate attempt did produce `0x00FF8B74` as "confirmed", but
it was a **false positive**: the test script at the time sent a
`VOLUME+` before each candidate "to open the volume bar on screen",
and what appeared to go up was that `VOLUME+`, not the candidate.
Lesson: a test script shouldn't inject commands the user didn't ask
for — it contaminates the experiment.

### The real pattern of the codes

With all 15 buttons mapped, you can see how the remote's chip numbers
the keys — and why the inference heuristics failed:

| cmd | button | | cmd | button |
|---|---|---|---|---|
| `0x82` | FORWARD | | `0x99` | RIGHT |
| `0x88` | MUTE | | `0x9A` | DOWN |
| `0x8C` | VOLUME+ | | `0x9B` | LEFT |
| `0x91` | MENU | | `0x9C` | VOLUME- |
| `0x93` | PLAY_PAUSE | | `0x9E` | OK |
| `0x95` | UP | | `0xA4` | BACK |
| `0x97` | INPUT | | `0xA8` | POWER |
| `0x98` | REWIND | | | |

Observations that break the "obvious" assumptions:

- **Functional pairs aren't numerically adjacent.** FORWARD (`0x82`)
  and REWIND (`0x98`) are the remote's most obvious pair and are 22
  values apart. That's why looking for VOLUME- next to VOLUME+
  (`0x8C`) never made sense — it's actually at `0x9C`.
- **VOLUME+ and VOLUME- differ by exactly 1 bit** (`0x8C` vs `0x9C`,
  bit 4). The "flip one bit" heuristic existed in `inference.py`, but
  was only applied to bits 0 and 1 — never to the high bits.
- **The `0x98`–`0x9C` block is contiguous**: REWIND, RIGHT, DOWN,
  LEFT, VOLUME-. The two broken buttons were direct neighbors of each
  other, which only became visible after discovering both.
- The numbering follows neither the buttons' physical position nor
  functional grouping — it's the chip matrix's scan order, which
  can't be deduced from the outside.

**Honest conclusion about inference:** for this remote, no bit
heuristic would have gotten it right. What actually solved it was
(a) fixing the payload format and (b) exhaustive scanning with visual
confirmation on every shot. The value of `inference.py` ended up
being more about ordering the candidates than guessing the right one.

## 10. Exporting the codebook to the Tuya Smart app

After mapping everything, you can create a **real** virtual remote
inside the Tuya Smart app, with all 15 keys persisted — not just
one-off firing, it shows up there like a normal remote.

The catch: the `POST /v2.0/infrareds/{id}/learning-codes` endpoint
(which creates a new remote and saves the list of keys) requires a
**`key`** field on each item in `codes` — it's mandatory per the
[official documentation](https://developer.tuya.com/en/docs/cloud/837dd9e219?id=Kb3oeazmud83g),
but easy to miss because the API **silently accepts** a payload
without it and still responds `success: true` — except no key
actually gets saved. `key_name` alone (what was being used before)
isn't enough; it's just an optional display label.

```python
codes = [{"key": name, "key_name": name, "code": entry["code_b64"]}
         for name, entry in codebook.all_entries().items()]

body = {
    "category_id": 6,      # Projector, in Tuya's taxonomy
    "brand_id": 999999,    # "Other" / generic
    "remote_name": "Projector AUN ET30 (CLI)",
    "codes": codes,
}
client.openapi.post(f"/v2.0/infrareds/{device_id}/learning-codes", body)
```

The virtual remote created this way shows up in the Tuya Smart app
like any other, with all 15 keys ready to use from there too —
without depending on the CLI.

### 10.1 The app's icons (arrows, OK, volume, etc.) — the `id` field matters

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
had already built correctly (a brand saved as "Other", category 6 =
Projector):

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
the app's "More" list, exactly like on the original remote.

**Watch out for `id` collisions:** if any code in the batch doesn't
have an explicit `id`, the API auto-generates a sequential one
(1, 2, 3...) that can collide with a fixed `id` used by another code
in the same batch — whichever is processed last "wins" and the other
code **silently disappears** (no error, no warning; the final saved
key count just ends up lower than expected). Always provide an
explicit, unique `id` for every code in the batch, even the ones
without a standard icon.

**Helper scripts created during this investigation** (live in the
project root, not part of `main.py`'s main flow):

- `scan_missing_buttons.py` / `remote_voldown.py` — batch scanning or
  numbered candidate testing, meant to run locally without an agent
  session's per-command time limit.
- `test_candidates_interactive.py` — interactive menu to test and
  save candidates one at a time.
- `remote.py` — terminal "remote control" (Windows, via `msvcrt`):
  press a key and the command fires instantly, no ENTER needed, for
  quickly testing all already-mapped buttons.
