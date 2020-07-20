# Race mini Editor #

Edit Pokémon Race mini tracks!

## Setup ##

This requires Python 3.6+ to run. It also requires the Pokémon Race mini ROM. Both the original Japanese version and the English patched version should work fine.

Before you can use this, you have to install the dependencies: `pip install -r requirements.txt`

To learn how to use it in more detail, use: `./race_map_editor.py --help`

## Export ##

Export everything with: `./race_map_editor.py /path/to/race.min x -o dump`

Currently this exports tilesets, tilemaps, track titles, and some metadata info for the Rookie Cup tracks. You may define more tracks in [tracks.toml](tracks.toml).

To export spritesheets, use the flag `-sp` somewhere after `x`

## Edit ##

Edit the track with [Tiled](https://www.mapeditor.org/). The TMX library used here technically only supports up to 1.2 but 1.4 works fine for me so that's probably fine!

You may edit the tilemap and metadata in Tiled. Note that the first and last 12 columns of tiles should be identical except for the flag. For the tileset, you'll have to edit it in your image editor of choice.

Only use the correct tileset for the correct layer and do not change the layer names.

There are 10 rows of tiles for each track. The first 5 are non-solid, the next 1 I haven't tested, the next 2 are solid, the next 1 is slowing (some are grass and some are water, check tile properties for specifics), and the last 1 is solid on top (but able to pass thru otherwise). For water tiles, characters will only switch to swimming mode if they land on a solid tile (including the last row tiles) while inside a water tile. Thus, place a water tile, then a solid one directly below it. The players will not stop swimming until they jump (even if they leave water tiles into normal, non-solid ones).

## Import ##

Import all tracks with: `./race_map_editor.py /path/to/race.min i -f dump`

Make sure to back up the ROM yourself! It will confirm as such before importing.

Currently this imports the tilesets, tilemaps, and metadata info editable in the TMX file.

## tracks.toml ##

```toml
[GpRk1]
type = "GrandPrixTrack"
metadata_base = 0x0240dd
title_index = 0
title_ditto_base = 0x020edf
title_ranking_base = 0x021312
```

Basically just a pickled class in toml, check out GrandPrixTrack in [structures.py](structures.py) for extra details.

* The identifier goes in the square brackets, this is what you pass at the command-line to work on that one track.
* `metadata_base` is the 2-byte value stored in $195c when playing a track + $020000.
* `title_index` is the sequential index of the centered title graphics stored in the tileset at $07c180. May change this to a hex address later idk.
* `title_ditto_base` and `title_ranking_base` are the locations of tilemaps for the tileset located at $07b068, used for the title bar in the ditto battle screen and the ranking screen, respectively.

## TODO ##

* Find music and AI locations. Are these related to the two unknowns?
* Find track intro/ranking screen graphic.
* Is there some place in the ROM that ties the title addresses and metadata address together?? Find/use if so.
* Import titles (tilesets and maps).
* Export/import sprite sheets.
* Ideally, make a custom editor that can deal with typesetting the titles, generating preview maps, and editing the tilesets internally instead of using a separate image editor.
* Potentially add the ability to edit things besides tracks (eg. other screens, for translations).

## Developing ##

Use YAPF to format. I don't really care how poorly designed this is so have at it.
