*[Leia em português (BR)](CONTRIBUTING.md)*

# Contributing

This project started from a very specific need (controlling an AUN
ET30 projector with two physically broken buttons), but the IR codes
discovered here likely work for other projectors too — many cheap
devices sold under different brands (AliExpress, Amazon, etc.) reuse
the same remote control chip.

## How to help

- **Is your projector/remote similar, and did the codes work?** Open
  an issue with the exact brand/model. This helps map which devices
  share this same remote.
- **Found a missing button or a wrong code?** Open a PR updating
  [`README.md`](README.en.md) (code table) and
  [`codebook.json`](codebook.json) together — keep both in sync.
- **Tested on another (non-Tuya) IR Hub or tool?** Report whether the
  NEC "textbook" timings worked or whether you needed the real
  measured timings (see the note in `README.md`) — helps show how
  sensitive this specific hardware is.
- **Python CLI bugs (Tuya usage):** this project already went through
  several real bugs documented in [`TUYA_CLI.md`](TUYA_CLI.en.md) — if
  you find another one (especially something that only shows up
  against real hardware, not in isolated tests), PRs or issues are
  welcome.

## Testing before sending a PR

```bash
pip install -r requirements.txt
python3 nec_encoder.py    # runs the self-test (encoder/decoder round-trip)
python3 nec_decoder.py
```

Both should finish with `ROUND-TRIP OK`.

## Code of conduct

No unnecessary formality: be kind, assume good intent, and remember
that whoever is reading this probably got here at 2am trying to fix a
broken remote, same as us.
