#!/usr/bin/env python3

import os
import sys
import argparse
from typing import Dict
from collections import OrderedDict

import tomlkit

from lib.maps import save_tmx, load_tmx
from lib.util import (
	load_tileset, write_tileset, write_spriteset, draw_track, TITLES_GRANDPRIX, TITLES_RANKING
)
from lib.structures import GrandPrixTrack


class Error(Exception):
	pass


tracks: Dict[str, GrandPrixTrack] = OrderedDict()
track_types = {"GrandPrixTrack": GrandPrixTrack}

with open("tracks.toml") as f:
	obj = tomlkit.loads(f.read())
	for key, kwargs in obj.items():
		t = kwargs.pop("type")
		tracks[key] = track_types[t](key, **kwargs)

parser = argparse.ArgumentParser(description="Import and export track data for Pokemon Race mini")
parser.add_argument("rom", help="Pokemon Race mini ROM file")
subparsers = parser.add_subparsers(dest="command")
subparsers.add_parser("list", aliases=["l"], help="List known tracks.")
export_parser = subparsers.add_parser(
	"export", aliases=["x"], help="Export track contents or information."
)
export_parser.add_argument(
	"tracks",
	nargs="*",
	help=(
	"Export an editable track and its preview."
	" May specify one or more tracks by name or by an arbitrary hexadecimal address"
	" of the metadata entry. May also specify tileset:# or spriteset:# for arbitrary"
	" graphics, where # is a hexadecimal address."
	" If nothing is specified, it exports all the tracks."
	)
)
export_parser.add_argument(
	"--out",
	"-o",
	default="",
	help="Output folder to store exports in if not the current directory."
)
export_parser.add_argument(
	"--metadata",
	"-m",
	action="store_true",
	help="Export metadata for the specified tracks as JSON."
)
export_parser.add_argument(
	"--png", "-p", action="store_true", help="Export PNGs only, no TMX files."
)
export_parser.add_argument(
	"--tilesets",
	"-t",
	action="store_true",
	help="Export the tilesets for the specified track(s) as PNGs."
)
export_parser.add_argument(
	"--spritesets",
	"-s",
	action="store_true",
	help=("Export the spriteset(s) for the specified track(s) as PNGs.")
)
export_parser.add_argument(
	"--render",
	"-r",
	action="store_true",
	help=("Export renders of the specified track(s) as PNGs.")
)
import_parser = subparsers.add_parser("import", aliases=["i"], help="Import track data.")
import_parser.add_argument(
	"tracks",
	nargs="*",
	help=(
	"Import data from a TMX file and its related graphics."
	" May specify one or more tracks by name."
	" If nothing is specified, it imports all the tracks with TMX files."
	)
)
import_parser.add_argument(
	"--folder",
	"-f",
	default="",
	help="Folder to look in for TMX/PNG files if not the current directory."
)
import_parser.add_argument("--yes", "-y", action="store_true", help="Overwrite without asking.")

written = set()

try:
	args = parser.parse_args()

	if args.command in {"l", "list"}:
		for name in tracks.keys():
			# TODO: print real names?
			print(f"* {name}")
	elif args.command in {"x", "export"}:
		with open(args.rom, "rb") as f:
			# Load name tiles
			load_tileset(f, TITLES_GRANDPRIX, height=8)
			load_tileset(f, TITLES_RANKING)

			exports = args.tracks if args.tracks else list(tracks.keys())
			for e in exports:
				if e.startswith("tileset:"):
					addr = int(e[8:], 16)
					load_tileset(f, addr)
					if args.png:
						print(f"Rendering tileset ${addr:06x}...")
						write_tileset(addr, args.out)
					else:
						raise Error("TMS not implemented yet")
				elif e.startswith("spriteset:"):
					raise Error("sprites not implemented yet")
				else:
					try:
						addr = int(e, 16)
					except ValueError:
						# Map name
						try:
							track = tracks[e]
						except KeyError:
							raise Error(f"no known track {e}")
					else:
						# Metadata location
						track = GrandPrixTrack(f"track_{addr:06x}", addr, 0, 0, 0)
					track.read(f)

					if args.render:
						print(f"Rendering {track.ident}...")
						draw_track(track, args.out)

					if not args.png:
						save_tmx(track, args.out)

					if args.tilesets:
						if track.metadata.tileset_base not in written:
							write_tileset(track.metadata.tileset_base, args.out)
						if track.metadata.preview_tileset_base not in written:
							write_tileset(track.metadata.preview_tileset_base, args.out)

					if args.spritesets:
						if track.metadata.sprite_base not in written:
							write_spriteset(track.metadata.sprite_base, args.out)

	elif args.command in {"i", "import"}:
		afn = os.path.abspath(args.rom)
		if not args.yes:
			r = input(f"Are you sure you want to overwrite the contents of {afn}? [n] ")
			if r != "y":
				sys.exit(0)
		with open(args.rom, "r+b") as f:
			imports = args.tracks if args.tracks else list(tracks.keys())
			for i in imports:
				if i not in tracks:
					print(f"No track named {i}", file=sys.stderr)
					continue
				try:
					track = tracks[i]
					load_tmx(track, args.folder)
					track.write(f)
					print(f"Imported {track.ident}")
				except FileNotFoundError:
					if args.tracks:
						print(f"No TMX for track {i}", file=sys.stderr)
						continue
	else:
		raise Error(f"Unknown(?) command {args.command}")

except Error as err:
	print(f"Error: {err.args[0]}", file=sys.stderr)
