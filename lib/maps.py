import os

import tmxlib
from tmxlib.fileio import TMXSerializer
from tmxlib.tileset import ImageTileset
from tmxlib.mapobject import RectangleObject

from .util import tilesets, write_tileset, PokeImportError
from .structures import TrackGhost, GrandPrixTrack, GrandPrixTrackMetaData

made_tilesets = {}


def ts_name_to_addr(name: str) -> int:
	return int(name.replace("tileset_", ""), 16)


def make_tsx(addr: int, folder: str) -> ImageTileset:
	if addr in made_tilesets:
		return made_tilesets[addr]
	img = tmxlib.image.open(write_tileset(addr, folder))
	ts = ImageTileset(f"{addr:06x}", (8, 8), img, base_path=folder)
	made_tilesets[addr] = ts
	return ts


def save_tmx(track: GrandPrixTrack, folder: str):
	out = tmxlib.Map((track.metadata.width, track.metadata.height), (8, 8), base_path=folder)
	out.properties["metadata base"] = f"${track.bases['metadata']:06x}"
	out.properties["sprite base"] = f"${track.metadata.sprite_base:06x}"
	out.properties["tilemap base"] = f"${track.metadata.tilemap_base:06x}"
	out.properties["background music"] = track.bgm.ident
	out.properties["unknown 2"] = str(track.metadata.unk2)
	out.properties["ai easy"] = track.ai_easy.to_string()
	out.properties["ai normal"] = track.ai_normal.to_string()
	out.properties["ai hard"] = track.ai_hard.to_string()

	# Make and add tilesets
	tiles = make_tsx(track.metadata.tileset_base, folder)
	preview_tiles = make_tsx(track.metadata.preview_tileset_base, folder)
	out.tilesets.append(tiles)
	out.tilesets.append(preview_tiles)

	# Tile properties
	for i in range(0x00, 0x50):
		tiles[i].properties["type"] = "non-solid"
	# 0x50~0x60 never used, untested
	for i in range(0x60, 0x80):
		tiles[i].properties["type"] = "solid"
	for i in range(0x80, 0x84):
		tiles[i].properties["type"] = "grass"
		tiles[i].properties["note"] = "slows and causes a grass effect"
	for i in range(0x84, 0x88):
		tiles[i].properties["type"] = "water"
		tiles[i].properties["note"] = "swims if Pikachu collides with the ground inside it"
	for i in range(0x88, 0x90):
		tiles[i].properties["type"] = "slowing"
	for i in range(0x90, 0xa0):
		tiles[i].properties["type"] = "one-way"
		tiles[i].properties["note"] = "solid only from the top"

	# A layer for each concept
	layer = out.add_layer("Track")
	obj_layer = out.add_object_layer("Track objects", color=(1.0, 0.0, 0.0))
	preview = out.add_layer("Preview")

	preview.properties["base"] = f"${track.metadata.preview_tilemap_base:06x}"

	# Make starting position object
	obj_layer.append(
		RectangleObject(
		obj_layer, (track.metadata.starting_x, track.metadata.starting_y),
		pixel_size=(16, 16),
		name="StartingPos"
		)
	)

	pos = ((x, y) for y in range(track.metadata.height) for x in range(track.metadata.width))
	for p, t in zip(pos, track.tilemap):
		layer[p] = tiles[t]

	pos = ((x, y)
		for y in range(track.metadata.preview_map_height)
		for x in range(track.metadata.preview_map_width))
	for p, t in zip(pos, track.preview_tilemap):
		preview[p] = preview_tiles[t]
	preview.visible = False

	# Add titles as available
	titles = out.add_layer("Titles")

	title_gp_tiles = make_tsx(track.config["titles_grand_prix_tileset"], folder)
	out.tilesets.append(title_gp_tiles)

	title_idx = track.index * 8
	for x, t in enumerate(range(title_idx, title_idx + 8)):
		titles[x, 0] = title_gp_tiles[t]

	title_rank_tiles = make_tsx(track.config["titles_menus_tileset"], folder)
	out.tilesets.append(title_rank_tiles)

	titles.properties["rank tilemap base"] = f"${track.bases['title_ranking']:06x}"
	for x, t in enumerate(track.title_ranking_tilemap):
		titles[x, 1] = title_rank_tiles[t]

	titles.properties["ditto tilemap base"] = f"${track.bases['title_ditto']:06x}"
	for x, t in enumerate(track.title_ditto_tilemap):
		titles[x, 2] = title_rank_tiles[t]

	titles.visible = False

	fn = os.path.join(folder, f"{track.ident}.tmx")
	out.save(fn, serializer=TMXSerializer((1, 1)), base_path=folder)


def load_tmx(track: GrandPrixTrack, folder: str, sounds: dict = {}):
	fn = os.path.join(folder, f"{track.ident}.tmx")
	tmap: tmxlib.Map = tmxlib.Map.open(fn)
	pika = tmap.layers["Track objects"]["StartingPos"]
	layer = tmap.layers["Track"]
	preview = tmap.layers["Preview"]

	track.bases = {
		"metadata": int(tmap.properties["metadata base"].lstrip("$"), 16),
	}

	if "Titles" in tmap.layers:
		titles = tmap.layers["Titles"]
		track.bases["title_ditto"] = int(titles.properties["ditto tilemap base"].lstrip("$"), 16)
		track.bases["title_ranking"] = int(titles.properties["rank tilemap base"].lstrip("$"), 16)

	for i in range(0, tmap.width):
		if not preview[i, 0]:
			break
	preview_width = i

	for i in range(0, tmap.height):
		if not preview[0, i]:
			break
	preview_height = i

	layer_tileset = ts_name_to_addr(layer[0, 0].tileset.name)
	preview_tileset = ts_name_to_addr(preview[0, 0].tileset.name)

	if "background music" in tmap.properties:
		# TODO: assume track_# for now, change to a method of rebuilding the table later
		bgm_name = tmap.properties["background music"]
		if not bgm_name.startswith("track_"):
			raise PokeImportError("does not support arbitrary track names yet")
		bg_music = int(bgm_name[6:])
	else:
		bg_music = int(tmap.properties["unknown 1"])

	track.metadata = GrandPrixTrackMetaData(
		tileset_base=layer_tileset,
		tilemap_base=int(tmap.properties["tilemap base"].lstrip("$"), 16),
		width=tmap.width,
		height=tmap.height,
		bg_music=bg_music,
		starting_x=round(pika.pixel_x),
		starting_y=round(pika.pixel_y),
		unk2=int(tmap.properties["unknown 2"]),
		sprite_base=int(tmap.properties["sprite base"].lstrip("$"), 16),
		preview_tileset_base=preview_tileset,
		preview_tilemap_base=int(preview.properties["base"].lstrip("$"), 16),
		preview_map_width=preview_width,
		preview_map_height=preview_height,
	)

	track.ai_easy = TrackGhost.from_string(tmap.properties["ai easy"])
	track.ai_normal = TrackGhost.from_string(tmap.properties["ai normal"])
	track.ai_hard = TrackGhost.from_string(tmap.properties["ai hard"])

	track.tilemap = b"".join(t.number.to_bytes(1, "little") for t in layer.all_tiles())
	track.preview_tilemap = b"".join(
		t.number.to_bytes(1, "little") for t in preview.all_tiles() if t
	)

	tilesets[layer_tileset] = layer[0, 0].tileset.image.pil_image
	tilesets[preview_tileset] = preview[0, 0].tileset.image.pil_image

	# TODO: name tilemap
