# race mini

* $192b = map width
* $1931 = map tile base
* $1933 = map tile location hi
* $1934 = map tile location of current UL tile
* $1938 = how far down the top of the viewport is from the top of the map
* $195c = map data pointer lo/mid (hi = $02)

* $1679 = (uint16) pikachu's x position on the map
* $167c = (uint16) pikachu's y position on the map
* $169b = (uint16) opponent's x position on the map
* $169e = (uint16) opponent's y position on the map

fun_0217dd - writes to pika y 

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
* 08:
  * written into int8_195e
* 09: goal x position (crossing from any y counts as a lap)
  * written into int16_195f (0-padded)
  * read every frame
  * setting this too low causes the opponent to spawn much further into the level (wrapping issue?)
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
