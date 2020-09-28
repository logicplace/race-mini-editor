# Race mini Editor #

Edit Pokémon Race mini tracks!

## Setup ##

This requires Python 3.6+ to run. It also requires the Pokémon Race mini ROM. Both the original Japanese version and the English patched version should work fine.

Before you can use this, you have to install the dependencies: `pip install -r requirements.txt`

To learn how to use it in more detail, use: `./race_map_editor.py --help`

## Export ##

Export everything with: `./race_map_editor.py /path/to/race.min x -o dump`

Currently this exports tilesets, tilemaps, track titles, sound data, AI, and some metadata info for the Rookie Cup tracks. You may define more tracks in [tracks.toml](tracks.toml).

To export spritesheets, use the flag `-sp` somewhere after `x`

## Edit ##

Edit the track with [Tiled](https://www.mapeditor.org/). The TMX library used here technically only supports up to 1.2 but 1.4 works fine for me so that's probably fine!

You may edit the tilemap, AI (sorta), and metadata in Tiled. Note that the first and last 12 columns of tiles should be identical except for the flag. For the tileset, you'll have to edit it in your image editor of choice.

Only use the correct tileset for the correct layer and do not change the layer names.

There are 10 rows of tiles for each track. The first 5 are non-solid, the next 1 I haven't tested, the next 2 are solid, the next 1 is slowing (some are grass and some are water, check tile properties for specifics), and the last 1 is solid on top (but able to pass thru otherwise). For water tiles, characters will only switch to swimming mode if they land on a solid tile (including the last row tiles) while inside a water tile. Thus, place a water tile, then a solid one directly below it. The players will not stop swimming until they jump (even if they leave water tiles into normal, non-solid ones).

## Import ##

Import all tracks with: `./race_map_editor.py /path/to/race.min i -f dump`

Make sure to back up the ROM yourself! It will confirm as such before importing.

Currently this imports the tilesets, tilemaps, track BGMs, AI, and metadata info editable in the TMX file.

## tracks.toml ##

```toml
# bases, see file

[GpRk1]
type = "GrandPrixTrack"
index = 0
```

Basically just a pickled class in toml, check out GrandPrixTrack in [structures.py](structures.py) for extra details. etc.

* The identifier goes in the square brackets, this is what you pass at the command-line to work on that one track.
* `index` is the internal index of the track in the game, though. You can go by its order in the title tileset (tileset_07c180.png) where the upper left is 0, the one to the right of that is 1, and first one on the next row is 2, 

## TODO ##

* Find track intro/ranking screen graphic.
* Import sprite sheets.
* Ideally, make a custom editor that can deal with typesetting the titles, generating preview maps, and editing the tilesets internally instead of using a separate image editor.
* Potentially add the ability to edit things besides tracks (eg. other screens, for translations).

## Developing ##

Use YAPF to format. I don't really care how poorly designed this is so have at it.
