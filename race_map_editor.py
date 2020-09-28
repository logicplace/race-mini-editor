#!/usr/bin/env python3

import os
import sys
import argparse
from typing import Dict
from collections import OrderedDict

import tomlkit

from lib.maps import save_tmx, load_tmx
from lib.util import (
	music, load_tileset, save_tileset, load_spriteset, write_tileset, write_spriteset, draw_track,
	Table, PokeImportError
)
from lib.sound import write_pmmusic, read_pmmusic, MinLibSound
from lib.structures import GrandPrixTrack, read2b_base


class Error(Exception):
	pass


tracks: Dict[str, GrandPrixTrack] = OrderedDict()
track_types = {"GrandPrixTrack": GrandPrixTrack}

with open("tracks.toml") as f:
	obj = tomlkit.loads(f.read())
	config = {k: v for k, v in obj.items() if not isinstance(v, dict)}
	for key, kwargs in obj.items():
		if isinstance(kwargs, dict):
			t = kwargs.pop("class")
			tracks[key] = track_types[t](key, **kwargs, config=config)

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
			load_tileset(f, config["titles_grand_prix_tileset"], height=8)
			load_tileset(f, config["titles_menus_tileset"])

			config["ai_easy_table_base"] = read2b_base(f, config["ai_table_base"], 0)
			config["ai_normal_table_base"] = read2b_base(f, config["ai_table_base"], 1)
			config["ai_hard_table_base"] = read2b_base(f, config["ai_table_base"], 2)

			# Export music
			bgm_table = Table(config["audio_table_base"], config["track_count"], (b"\xf0", b"\xf2"))
			bgm_table.read(f)
			for i, data in bgm_table.iter_entries(f):
				music[i] = MinLibSound.from_bin(f"track_{i}", data)

			# TODO: don't overwrite what's already there
			print("Exporting sound data...")
			write_pmmusic(music.values(), args.out)

			exports = args.tracks if args.tracks else list(tracks.keys())
			for e in exports:
				if e.startswith("tileset:"):
					addr = int(e[8:], 16)
					load_tileset(f, addr)
					if args.png:
						print(f"Rendering tileset ${addr:06x}...")
						write_tileset(addr, args.out)
					else:
						raise Error("TSX not implemented yet")
				elif e.startswith("spriteset:"):
					addr = int(e[10:], 16)
					load_spriteset(f, addr)
					print(f"Rendering spriteset ${addr:06x}...")
					write_spriteset(addr, args.out)
				else:
					# Map name
					try:
						track = tracks[e]
					except KeyError:
						raise Error(f"no known track {e}")
					track.read(f)

					if args.render:
						print(f"Rendering {track.ident}...")
						draw_track(track, args.out)

					if not args.png:
						print(f"Exporting track data for {track.ident}...")
						save_tmx(track, args.out)

					if args.tilesets:
						print(f"Exporting tilesets for {track.ident}...")
						if track.metadata.tileset_base not in written:
							write_tileset(track.metadata.tileset_base, args.out)
						if track.metadata.preview_tileset_base not in written:
							write_tileset(track.metadata.preview_tileset_base, args.out)

					if args.spritesets:
						print(f"Exporting sprite sheet for {track.ident}...")
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
			sounds = read_pmmusic(args.folder)
			for k, v in sounds.items():
				if k.startswith("track_"):
					music[int(k[6:])] = v

			update = {"ai": set(), "music": set(), "tilesets": set(), "spritesets": set()}
			for i in imports:
				if i not in tracks:
					print(f"No track named {i}", file=sys.stderr)
					continue
				try:
					track = tracks[i]
					load_tmx(track, args.folder)
					track.write(f, update)
					print(f"Imported {track.ident}")
				except FileNotFoundError:
					if args.tracks:
						print(f"No TMX for track {i}", file=sys.stderr)
						continue

			# Save title tilesets wholesale, TODO: consider saving partially?
			save_tileset(f, config["titles_grand_prix_tileset"])
			save_tileset(f, config["titles_menus_tileset"])
			print("Wrote title tilesets")

			# TODO: reallocate tables as needed
			# for now, just make sure lengths are <= what's there
			# Import music
			raws = {}
			lengths = {}
			for m in update["music"]:
				if m.ident.startswith("track_"):
					idx = int(m.ident[6:])
					raws[idx] = music[idx].to_bin()
					lengths[idx] = len(raws[idx])

			bgm_table = Table(config["audio_table_base"], config["track_count"], (b"\xf0", b"\xf2"))
			bgm_table.read(f)
			res = bgm_table.check_conflicts(lengths)
			if res == 0:
				raise Error(
					"Cannot import music, result would be too large, and relocation is not yet supported."
				)
			elif res == 1:
				# Import per song in-place
				for idx, raw in raws.items():
					bgm_table.write_entry(f, idx, raw, False)
					print(f"Wrote sound data track_{idx}")
			elif res == 2:
				# Rewrite pointer array and overwrite entire music block
				bgm_table.write_all_entries(f, (v for k, v in sorted(raws.items())), False)
				print("Rewrote music table")

			# Import AI
			raws = [{}, {}, {}]
			lengths = [{}, {}, {}]
			mapping = {}
			track: GrandPrixTrack
			for track in update["ai"]:
				raw = raws[0][track.index] = track.ai_easy.to_bin()
				lengths[0][track.index] = len(raw)
				raw = raws[1][track.index] = track.ai_normal.to_bin()
				lengths[1][track.index] = len(raw)
				raw = raws[2][track.index] = track.ai_hard.to_bin()
				lengths[2][track.index] = len(raw)
				mapping[track.index] = track.ident

			for difficulty in (0, 1, 2):
				diff_name = ["easy", "normal", "hard"][difficulty]
				ai_table_base = read2b_base(f, config["ai_table_base"], difficulty)
				ai_table = Table(ai_table_base, config["track_count"], b"\xff\x00")
				ai_table.read(f)
				res = ai_table.check_conflicts(lengths[difficulty])
				if res == 0:
					raise Error(
						f"Cannot import AI for {diff_name} mode, result would be too large, and relocation is not yet supported."
					)
				elif res == 1:
					# Import per AI in-place
					print(f"Writing AI data for {diff_name} mode...")
					for idx, raw in raws[difficulty].items():
						bgm_table.write_entry(f, idx, raw, False)
						print(f"...{mapping[idx]}")
				elif res == 2:
					# Rewrite pointer array and overwrite entire AI block
					bgm_table.write_all_entries(f, (v for k, v in sorted(raws.items())), False)
					print("Rewrote {diff_name} AI table")

			# Import tilesets, TODO: ensure correct size
			for base in update["tilesets"]:
				save_tileset(f, base)
			print("Wrote track tilesets")
	else:
		raise Error(f"Unknown(?) command {args.command}")

except Error as err:
	print(f"Error: {err.args[0]}", file=sys.stderr)
