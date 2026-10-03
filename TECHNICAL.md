# Jirachi Bonus Disc Extractor - Technical Notes

English | [日本語](TECHNICAL.jp.md)

Notes on the disc and ROM data itself: how we found and verified the ROMs,
and what the patches actually change. Written for future reference. See
[README](README.md) for usage. For the implementation, read the source.

## The disc

Only one disc is known to carry these ROMs, the US pre-order Bonus Disc
(`PC6E01 Rev.00`).

The disc can be identified without reading the whole ~1.4 GB image:

| Check | Location | Expected value |
|---|---|---|
| GameCube disc magic | `0x1C` (u32 BE) | `0xC2339F3D` |
| File system table (FST) offset | `0x424` (u32 BE) | `0x000DBE00` |
| Hash of the FST itself | `0x000DBE00`, `0x1BB` bytes | SHA-256 `24ef3c366c733e3e80ac144aef246cb95579469c7f99e41bfae322d666870802` |
| FST entry #16, file location | FST + 192 bytes (12 bytes per entry) | `0x35108000` |
| Embedded container magic | `0x35108000` (u32 BE) | `0xAE0F38A2` |

FST entry #16, at outer disc offset `0x35108000`, is
`/tgc/pokedownload.tgc`. It's a second, complete GameCube disc image
("PokeDownLoad") embedded inside the first, in Nintendo's TGC container
format. Per [tcrf.net][tcrf], it also holds leftover Kirby Air Ride assets
alongside the Jirachi ROMs. That inner disc has its own file system too,
but we never had to parse it. The three ROM locations below were found once
and are absolute offsets into the outer disc image.

[tcrf]: https://tcrf.net/Pok%C3%A9mon_Colosseum/Bonus_Discs#:~:text=Kirby%20Air%20Ride%20leftovers

## ROM locations

| File | Offset | Size | SHA-256 (original, unpatched) |
|---|---|---|---|
| `client.bin` | `0x352DDF2C` | `0x6BC0` | `a78161cc15f356e9e356619ab4701be3e2c5270075129c33bc35f2033402681f` |
| `client.2003_1112.bin` | `0x352D8000` | `0x5F2C` | `f6c0110162aa48c13707cbb21ba612a4833820eaef538335d82f2d54e6cceeb8` |
| `sample0519.bin` | `0x3DA32D30` | `0x116C8` | `544719a8a96439ef56eee84afebdfa7ebe1abbb7a1e93f0e21f98fc5365b8f27` |

These hashes are what each extracted file is checked against, both right
after pulling it off the disc and again right before patching. A file
that doesn't match, whether from a bad offset or a damaged disc image,
never makes it to the download or patch step.

See [README](README.md) for each ROM's in-game OT, TID, and language.

## ROM structure

Each of the three files is the same structure: a small ARM bootloader,
uncompressed, followed by a compressed payload holding the actual game
code. On boot, the bootloader decompresses the payload into RAM at a
fixed address and jumps there to begin execution.

The bootloader's layout is the same across all three ROMs:

| File offset | Contents | What it does |
|---|---|---|
| `0x154` to `0x157` | `ldr r0, [pc, #imm]` | address the compressed data is read from |
| `0x158` to `0x15B` | `ldr r1, [pc, #imm]` | address the decompressed data is written to |
| `0x15C` to `0x15F` | call instruction | runs the actual decompression |
| `0x160` to `0x163` | `ldr lr, [pc, #imm]` | the same destination address, read again |
| `0x164` to `0x167` | `bx lr` | jumps into the code that was just decompressed |
| `0x174` to `0x177` | data | the destination address itself, always near `0x0201xxxx` |

The compressed data's source address depends on how the ROM was loaded.
Real GBA multiboot loads it into EWRAM, where the compressed data
starts at `0x02000278`. Loaded as a plain cartridge or emulator ROM
image, it's read from `0x08000278` instead. Both addresses end in
`0x278`, so the compressed data always starts the same distance past the
bootloader itself, whichever memory space the bootloader ends up running
from. Only the base address changes.

## Compatibility patches

These ROMs were never meant to run outside the official GameCube to GBA
transfer they shipped with. Loaded through multiboot on real hardware, or
as a plain ROM image on an emulator, they fail a handshake and a chipset
check that the bootloader otherwise waits on, and never get anywhere. The
patches below remove those checks.

They are based on technical information from [Zaksabeast's
Multiboot-Jirachi-Patches][zaksabeast] (ISC License). Zaksabeast's
handshake patch writes `0x0000` twice as
NOPs. `0x0000` is actually `movs r0, r0`, which also sets the condition
flags. We write `0x46C0` (`mov r8, r8`) instead, the standard Thumb NOP
with no side effects. The ISO extraction and the shiny lock removal patch
are original to this project.

[zaksabeast]: https://github.com/zaksabeast/Multiboot-Jirachi-Patches/

**`client.bin`**

| Address | Patched value | Width | Effect |
|---|---|---|---|
| `0x0201036C` | `0x46C046C0` | word | two NOPs, skips the handshake wait |
| `0x02014CEC` | `0x2000` | halfword | forces the chipset check to pass |
| `0x02012EC4` | `0x47702011` | word | reports the game code as US Ruby/Sapphire |

**`client.2003_1112.bin`**, same three patches, different addresses:

| Address | Patched value | Width | Effect |
|---|---|---|---|
| `0x02010378` | `0x46C046C0` | word | skips the handshake wait |
| `0x0201437C` | `0x2000` | halfword | forces the chipset check to pass |
| `0x02012EEC` | `0x47702011` | word | reports the game code as US Ruby/Sapphire |

**`sample0519.bin`** needs no game code patch, and its handshake check is
skipped with a branch instead of two NOPs. Its bootloader lays the wait
loop out a little differently from the other two. It is also the only
one of the three with a working shiny lock (`client.bin` and
`client.2003_1112.bin` shipped with a broken one, see
[README](README.md) for odds), so it gets an optional third patch:

| Address | Patched value | Width | Effect |
|---|---|---|---|
| `0x0201E398` | `0xE03A` | halfword | branches past the handshake wait loop |
| `0x0201F5F6` | `0x2000` | halfword | forces the chipset check to pass |
| `0x0201E9E2` | `0x46C0` | halfword | optional: skips the branch that increments the PID until it is not shiny |

## How the patches take effect

The payload is only patchable after the bootloader decompresses it into
RAM, since patching it compressed would mean re-implementing the
compression format. So the bootloader itself is extended: once
decompression finishes, it writes each new value above into its target
address, then jumps into the code exactly as before. This replaces the
original jump at `0x160` and some of what follows it, the last thing the
bootloader runs before handing off to the game.

The compressed source redirect uses the same mechanism, just changing
where the first read pulls from.
