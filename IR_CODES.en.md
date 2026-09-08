*[Leia em português (BR)](IR_CODES.md)*

# IR remote codes — AUN ET30 (and possible sibling models)

Standalone reference for the infrared codes of the remote control that
ships with the **AUN ET30** mini projector. These codes were **not
documented anywhere public** before this repository (no hits in the
best-known IR databases — irdb, Flipper-IRDB, RemoteCentral — nor in
forums) — they were reverse-engineered through a Tuya Smart IR Hub,
with a fair amount of trial and error. See [README.md](README.en.md)
for the full story of how each one was discovered (some by real
capture, others by brute-force scanning).

If your remote **looks the same** (same button layout, same generic
mini projector sold under different rebranded names — common with
cheap AliExpress/Amazon projectors) and these codes work on your unit,
**open an issue or PR** with your projector's brand/model — it helps
map the family of devices sharing this same remote chip.

## Protocol

- **Protocol:** standard NEC, 32 bits (address + ~address + command +
  ~command), 38 kHz carrier.
- **Address:** `0x00` on all confirmed buttons.
- **Real measured timings** (off the NEC "textbook" values — see note
  below): leader mark `8889µs`, leader space `4513µs`, bit mark
  `563µs`, `0`-bit space `563µs`, `1`-bit space `1703µs`, stop mark
  `563µs`.

> **Important note for anyone re-implementing this:** the NEC
> "textbook" timings (9000/4500/560/1690µs) also decode these signals
> correctly (any IR receiver's tolerance covers the difference), but
> some specific transmitters/receivers (like the Hub used here) only
> accept the **exact, measured** timings, not the standard values. If
> your tests with textbook timings don't work, use the real values
> above.

## Code table

All at address `0x00`. Full NEC code = `00FF` + command + `~command`.

| Button | Command (hex) | Full NEC code | Source |
|---|---|---|---|
| FORWARD | `0x82` | `0x00FF827D` | captured (real learning) |
| MUTE | `0x88` | `0x00FF8877` | imported from Tuya Smart app |
| VOLUME+ | `0x8C` | `0x00FF8C73` | imported from Tuya Smart app |
| MENU | `0x91` | `0x00FF916E` | imported from Tuya Smart app |
| PLAY/PAUSE | `0x93` | `0x00FF936C` | captured (real learning) |
| UP (arrow) | `0x95` | `0x00FF956A` | imported from Tuya Smart app |
| INPUT / SOURCE | `0x97` | `0x00FF9768` | imported from Tuya Smart app |
| REWIND | `0x98` | `0x00FF9867` | captured (real learning) |
| RIGHT (arrow) | `0x99` | `0x00FF9966` | imported from Tuya Smart app |
| DOWN (arrow) | `0x9A` | `0x00FF9A65` | imported from Tuya Smart app |
| LEFT (arrow) | `0x9B` | `0x00FF9B64` | imported from Tuya Smart app |
| VOLUME- | `0x9C` | `0x00FF9C63` | scan + live confirmation |
| OK | `0x9E` | `0x00FF9E61` | imported from Tuya Smart app |
| BACK | `0xA4` | `0x00FFA45B` | imported from Tuya Smart app |
| POWER | `0xA8` | `0x00FFA857` | imported from Tuya Smart app |

Note that the command bytes don't follow the buttons' physical layout
or any obvious logical grouping (POWER and BACK sit isolated far from
the rest; the `0x98`–`0x9C` block groups REWIND/RIGHT/DOWN/LEFT/
VOLUME- purely by coincidence of the chip's scan matrix). Details on
how each value was found are in
[README.md, section 9](README.en.md#9-how-left-and-volume--were-solved).

## Ready-to-use formats

- [`AUN_ET30.ir`](AUN_ET30.ir) — **Flipper Zero** format (native NEC protocol).
- [`AUN_ET30.lircd.conf`](AUN_ET30.lircd.conf) — **LIRC** format (`lircd.conf`).
- [`codebook.json`](codebook.json) — format used by this repo's CLI
  (includes the Tuya API's specific binary payload, plus plain NEC hex).

Any tool that accepts raw NEC (Arduino + `IRremote`, ESPHome, Tasmota,
generic capture/replay tools) can use the values in the table above
directly — address `0x00`, command per the column.
