# race mini

* $14f5 = currently playing song

* $1679 = `uint16` pikachu's x position on the map
* $167c = `uint16` pikachu's y position on the map
* $169b = `uint16` opponent's x position on the map
* $169e = `uint16` opponent's y position on the map
* $16b2 = start of some structure
  * $16c2 = `uint24` address of current screen's sprite attributes info in ROM (pikachu for win/lose screen, banner for ranking screen)

* $1892 = `uint8` x offset for ranking screen sprites
* $1893 = `uint8` y offset for ranking screen sprites

* $192b = map width
* $1931 = `uint16` map tilemap base
* $1933 = `uint8` map tilemap location hi
* $1934 = `uint16` map tilemap location of current UL tile
* $1938 = how far down the top of the viewport is from the top of the map
* $1951 = `uint8` difficulty index
* $195b = `uint8` map index (for lookups in arrays)
* $195c = `uint16` map metadata pointer lo/mid (hi = $02)

* $00646A = `uint16[64]` locations of music/sound data
* $0064ea~$0078c5 = audio data
* $010562 = `uint16[16]` locations of level sprite attribute maps in order
* $0240a6 = `uint16[16]` locations of level metadata in order
* $0368ed = `uint16[3]` locations of AI tables indexed by difficulty
* $0368f3 = `unit16[16]` locations of AI in order (easy)
* $036913 = `unit16[16]` locations of AI in order (normal)
* $036933 = `unit16[16]` locations of AI in order (hard)
* $072a00/$076600 = spritesets for title/ranking screens

fun_0217dd - writes to pika y

```c++
void fun_003ec6() {
    // YI set to the value of uint8_1504, which is always 0
    if (uint8_14e8 == 0) {
        if (uint8_14fb) {
            TMR3_CTRL_L &= 0xfb;
        }
        uint8_14ee &= 0xce;
        uint8_14ed = 0;

        uint16_t y = uint16_14e0;
        uint8_t a = *(uint8_t*)y;
        if (a & 0x80) {
            uint16_14e0 = y + 1;
            y = 0x63d6 + a * 2;

            if (*y != 0) {
                uint16_t ba;
                if (!uint8_14fb) {
                    TMR3_PRE = *y;
                }
                uint16_14ef = *y;

                hl = (uint16_t)uint8_14e6;
                y = 0x63a2;

                if (uint8_1507 & 0x80 == 0) {
                    a = *(uint8_t*)(y + hl);
                    ba = TMR3_PRE / a;
                } else {
                    // $3fcc
                    ba = 0x14;
                }
                hl = *uint16_14ef - ba;

                if (!uint8_14fb) {
                    TMR3_PVT = hl;
                }
                uint16_14f1 = hl;

                // $3f5c - Fetch note length
                // uint8_14e2 = last x of a 0x8x command
                // uint8_14e5 = last x of a 0xBx command
                uint8_14e8 = *(uint8_t*)(0x636c + 9 * uint8_14e5 + uint8_14e2) - 1;

                // uint8_14e3 = last 0x9x or 0xDx command
                if (uint8_14e3) {
                    uint8_14ea = uint8_14e8 - uint8_14e3;
                }

                if (!uint8_14fb) {
                    AUD_VOL = (AUD_VOL & 0xfc) | uint8_1507;
                    TMR3_CTRL_L |= 6; // enable + reset
                }

                return;
            } else {
                // $3fa1
                if (!uint8_14fb) {
                    AUD_VOL &= 0xfc; // + 0 ?
                }
                uint8_14e8 = *(uint8_t*)(0x636c + 9 * uint8_14e5 + uint8_14e2) - 1;
                return;
            }
        }
    }
}
```

```c++
// Clear map metadata
void fun_021564() {
    uint8_192b = 0; // map width
    int8_192c = 0;
    uint16_1931 = 0;
    uint8_1933 = 0; // map location hi
    int16_1936 = 0;
    int16_1938 = 0;
    sint16_193a = -10;
    sint16_193c = -10;
}
```

```c++
// Set up map metadata
void fun_02158d(uint8 width, int8 height, uint24 base) {
    uint8_192b = width;
    int8_192c = height;
    uint24_1931 = base;

    uint16_192d = width * 8 - 96;
    uint16_192f = height * 8 - 64;
    uint16_1942 = uint16_192f - 32;
}
```

```c++
// Draw map/preview
void fun_02162f() {
    unit16 map_remainder;
    uint24 *map, *screen;
    if (!uint24_1931) {
        return;
    }
    map = (uint8_1933 << 16) | uint16_1934;
    screen = TILEMAP;

    // uint8_192b = map width
    map_remainder = uint8_192b - 12;

    for(int y = 9; y; --y) {
        for (int x = 0; x < 12; ++x) {
            *screen = *map;
            ++map;
            ++screen;
        }
        *screen = *map;
        screen += 4;
        map += map_remainder;
    }
}
```

```c++
// Calculate map position from map base
void fun_0215d8() {
    int16_1940 = int16_1938 >> 3; // intdiv 8
    int16_193e = uint8_192b * int16_1940 + int16_1936 >> 3;
    // Set to upper left tile in map data
    uint16_1934 = int16_193e + uint_1931;
    int8_1633 = int8_1936 & 7;
    int8_1632 = int8_1938 & 7;
}
```

```c++
// Find AI
void fun_022d17() {
    unit16 *addr = 0x0368ed + uint8_1951 * 2; // difficulty
    addr = (0x030000 | *addr) + uint8_195b * 2; // track
    unit24_1981 = (0x030000 | *addr);
    uint8_1984 = *((uint8*)unit24_1981 + 1);
    uint8_1987 = uint8_1988 = 0;
}
```

```c++
void fun_017a2c(uint8 *x) {
    uint16 tmp = (uint16)(x + 11)
    tmp = max(0, tmp - uint16_1942, uint16_192d);
    uint16_1936 = tmp;
    uint16_193a = tmp - 16;

    tmp = (uint16)(x + 14);
    tmp = max(0, tmp - 0x25, uint16_192f);
    uint16_1938 = tmp;
    uint16_193c = tmp - 16;
}
```

loader: $023ea8

metadata format:

* 00~02: tile gfx base (TILEMAP)
* 03~05: base tile map data
  * x for fun_02158d
  * translated to current map tile location in fun_0215d8
* 06: width
  * a for fun_02158d
* 07: height (extending downward)
  * b for fun_02158d
* 08: music index
  * written into int8_195e
* 09: starting x offset
  * written into int16_195f (0-padded)
  * read every frame
  * setting this too low causes the opponent to spawn much further into the level (wrapping issue, sorta)
* 0a: starting y offset for all players (and hoppip), in pixels
  * read in fun_011d1d, written to `[[$18b7] + $0e]`
  * that's then read in fun_017a2c, combined with the byte after it as int16_167c (for second map? also was 0), and used to calculate uint16_1938 and uint16_193c
* 0b: ???
  * read in fun_022ee3 at $022f16, written to uint8_197c
  * that's then read in fun_011e9c and modified and written to `[[$18bb] + $1a]` and passes wholesale to fun_0118a8
  * fun_0118a8(a) uses it as a lookup of `uint16 ba = [$0118b2 + a * 2]`, and writes ba to `[[$18bb] + $02]`
  * fun_011943 reads and tests the value for a guaranteed jump ? weird code section
* 0c~0e: sprite base
* 0f~11: preview tile gfx base (TILEMAP)
* 12~14: preview tile map base
* 15: preview map width
* 16: preview map height

## ai

seems to be a series of cmd, delay

ends at cmd = $FF

## music

* 0x8x, x written to $14e2
* 0xCx, x written to $14e6
* 0x9x and 0xDx are written to $14e3
* 0xAx and 0xEx, x written to $14e4
  then looked up `uint8[16]` table at $63a6 and written to $1439
  and $14ee |= 2
* 0xBx, x written to $14e5

note length lookup via: uint8_14e8 = *(0x636c + 9 * uint8_14e5 + uint8_14e2) - 1

```text
+----+----+----+----+----+----+----+----+----+----+
| \8 | 80 | 81 | 82 | 83 | 84 | 85 | 86 | 87 | 88 |
| B\ | 89 | 8a | 8b | 8c | 8d | 8e | 8f |    |    | on following row
+----+----+----+----+----+----+----+----+----+----+
| B0 | 01 | 02 | 04 | 06 | 08 | 0c | 10 | 18 | 20 |
| B1 | 01 | 03 | 06 | 09 | 0c | 12 | 18 | 24 | 30 |
| B2 | 02 | 04 | 08 | 0c | 10 | 18 | 20 | 30 | 40 |
| B3 | 03 | 06 | 0c | 12 | 18 | 24 | 30 | 48 | 60 |
| B4 | 04 | 08 | 10 | 18 | 20 | 30 | 40 | 60 | 80 |
| B5 | 05 | 0a | 14 | 1e | 28 | 3c | 50 | 78 | a0 |
+---------- Garbage(?) below this point ----------+
| B6 | 02 | 04 | 08 | 10 | 01 | 02 | 03 | 04 | 05 |
| B7 | 06 | 07 | 08 | 09 | 0a | 0b | 0c | 0d | 0e |
| B8 | 0f | 08 | 04 | 01 | 03 | 04 | 01 | 03 | 04 |
| B9 | 03 | 03 | 01 | 03 | 08 | 04 | 01 | 00 | 00 |
| Ba | 40 | 00 | ff | 60 | 00 | ff | 10 | 00 | 00 |
| Bb | 00 | 04 | ff | 07 | 20 | 00 | 18 | 00 | 78 |
| Bc | 60 | 71 | e0 | 6a | 00 | 65 | 40 | 5f | 00 |
| Bd | 5a | e0 | 54 | 00 | 50 | c0 | 4b | 60 | 47 |
| Be | 00 | 43 | c0 | 3e | 00 | 3c | b0 | 38 | 70 |
| Bf | 35 | 80 | 32 | a0 | 2f | 00 | 2d | 70 | 2a |
+----+----+----+----+----+----+----+----+----+----+
```

All songs seem to call 0xBX 0xF1 0xAX 0xCX 0x9X 0x8X (sometimes order changes) then have notes with some 0x8X and 0xCX mixed in, ending in 0xF2. Wouldn't be surprised if 0xAX showed up midway, but don't seem to see any 0xBX calls mid-song.

## first map

```hex
00 90 05 00 08 06 8c 10  07 18 67 04 00 90 04 40
4b 03 40 58 03 20 08
```

* preview tile data = $035840
* preview map width = 32
* map location = $060cdf (starting) $060800 (base)
* map width = 140
* map metadata location = $0240dd

* sprite attributes for track title/ranking = $07e3e0

## second map

```hex
00 95 05 c0 10 06 8c 10  08 18 57 03 00 60 04 40
4b 03 40 59 03 20 08
```

* preview tile data = $035940
* preview map width = 32
* map location = $ (starting) $0610c0 (base)
* map width = 140
* map metadata location = $0240f4
