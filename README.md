# Jirachi Bonus Disc Extractor

English | [日本語](README.jp.md)

Extracts the three Jirachi distribution ROMs from the 2003 US Pokémon Colosseum
Bonus Disc (`PC6E01 Rev.00`). Runs offline in a single HTML file.

## Usage

Open <https://healache.github.io/jirachi-bonus-disc-extractor/>.

1. Drop in a `PC6E01.iso`.
2. Pick an output format. Multiboot ROM for hardware and emulators that
   correctly emulate the official multiboot behavior, such as mGBA.
   Emulator-compatible ROM for GBA emulators that do not correctly load
   multiboot ROMs.
3. Download the ROMs.

## The three ROMs

| File                   | OT         | TID   | Language | Status                |
| ---------------------- | ---------- | ----- | -------- | --------------------- |
| `client.bin`           | WISHMKR    | 20043 | ENG      | Official distribution |
| `client.2003_1112.bin` | METEOR     | 30719 | ENG      | Unreleased            |
| `sample0519.bin`       | ネガイボシ | 30719 | JPN      | Official distribution |

## Shiny

WISHMKR and METEOR shipped with broken shiny locks and can be hunted on retail.
ネガイボシ's shiny lock works, so it has to be removed.

| ROM                       | Odds        | Approx.   |
| ------------------------- | ----------- | --------- |
| WISHMKR                   | 9 / 65,536  | 1 / 7,282 |
| METEOR                    | 10 / 65,536 | 1 / 6,554 |
| ネガイボシ (lock removed) | 7 / 65,536  | 1 / 9,362 |

ネガイボシ is seeded from the GBA's RTC and has no one-per-save limit.
Removing the lock is the only way to get a Japanese-origin shiny Jirachi from
these ROMs, as WISHMKR and METEOR are English-only.

## Third-party

The multiboot compatibility patch is based on technical information from
Zaksabeast's
[Multiboot-Jirachi-Patches](https://github.com/zaksabeast/Multiboot-Jirachi-Patches/),
licensed under the ISC License.

## License

This project is licensed under the BSD 3-Clause License.
