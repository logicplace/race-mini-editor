import re
import struct
from typing import Any, BinaryIO, Dict, NamedTuple, Optional, Sequence, Tuple

from .util import music, tilesets, load_tileset, spritesets, load_spriteset, PokeImportError
from .sound import MinLibSound
from .encoders import encode_tiles


def to3b(x: int):
	return x.to_bytes(3, "little")


def read2b_base(f: BinaryIO, table_base: int, idx: int) -> int:
	f.seek(table_base + idx * 2)
	return (table_base & 0xff0000) + int.from_bytes(f.read(2), "little")


def write2b_base_and_seek(f: BinaryIO, table_base: int, idx: int, addr: int):
	f.seek(table_base + idx * 2)
	f.write((addr & 0xffff).to_bytes(2, "little"))
	f.seek(addr)


def readXb_until(f: BinaryIO, x: int, until: int):
	ret = []
	comp = ~until
	while comp != until:
		data = f.read(x)
		ret.append(data)
		comp = data[0]
	return ret


class TrackGhost:
	# 0bPRLDUCBA
	DPAD = 0x78
	POWER = 0x80
	RIGHT = 0x40
	LEFT = 0x20
	DOWN = 0x10
	UP = 0x08
	C = 0x04
	B = 0x02
	A = 0x01

	_splitter = re.compile(r'#.*|\d+|[^\s\d#]+')

	dir_to_arrows = {
		0: "",
		RIGHT: "→",
		LEFT: "←",
		DOWN: "↓",
		UP: "↑",
		RIGHT | DOWN: "↘",
		LEFT | DOWN: "↙",
		# Stupid ones
		RIGHT | UP: "↗",
		LEFT | UP: "↖",
		RIGHT | LEFT: "↔",
		DOWN | UP: "↕",
		RIGHT | LEFT | DOWN: "↔↓",
		RIGHT | LEFT | UP: "↔↑",
		RIGHT | DOWN | UP: "→↕",
		LEFT | DOWN | UP: "←↕",
		RIGHT | LEFT | DOWN | UP: "↔↕",
	}

	# yapf: disable
	arrow_to_dir = {
		"r": 0,
		">": RIGHT, "→": RIGHT,
		"<": LEFT, "←": LEFT,
		"v": DOWN, "↓": DOWN,
		"^": UP, "↑": UP,
		"\\": RIGHT | DOWN, "↘": RIGHT | DOWN,
		"/": RIGHT | DOWN, "↙": RIGHT | DOWN,
		"C": C, "B": B, "A": A,
		"c": C, "b": B, "a": A,
		# Stupid ones
		"↗": RIGHT | UP,
		"↖": LEFT | UP,
		"↔": RIGHT | LEFT,
		"↕": DOWN | UP,
	}
	# yapf: enable

	def __init__(self):
		self.ops: Sequence[Tuple[int, int]] = []

	@classmethod
	def from_bin(cls, source: BinaryIO) -> "TrackGhost":
		ret = cls()
		while True:
			data = source.read(10)
			for i in range(0, 10, 2):
				keys = data[i]
				ticks = data[i + 1]
				ret.ops.append((keys, ticks))
				if keys == 0xff:
					source.seek(-(10 - i + 2), 1)
					return ret

	def to_bin(self) -> bytes:
		ret = bytearray()
		for op in self.ops:
			ret.extend(op)
		return bytes(ret)

	def to_string(self):
		ret = []
		last_dir = 0
		for keys, ticks in self.ops:
			op = []
			if keys == 0:
				op.append("r")
				last_dir = 0
			elif keys == 0xff:
				break
			elif keys == self.LEFT | self.B:
				op.append("↞")
				last_dir = self.LEFT
			elif keys == self.RIGHT | self.B:
				op.append("↠")
				last_dir = self.RIGHT
			else:
				direction = keys & self.DPAD
				arrows = self.dir_to_arrows[direction]
				if keys & self.A:
					if direction == last_dir:
						op.append("↥")
					else:
						op.append(arrows)
						op.append("A")
				else:
					op.append(arrows)
				if keys & self.B:
					op.append("B")
				last_dir = direction
			op.append(str(ticks))
			ret.append("".join(op))
		return " ".join(ret)

	@classmethod
	def from_string(cls, s: str) -> "TrackGhost":
		# ←< ↑^ →> ↓v ↘\ ↙/ and ↖↗↔↕ should work too I guess
		# r reset/rest
		# ↥ jump while continuing movement
		# ↞ dash left
		# ↠ dash right
		# ↳x typical jump dash, [(1, 8), (0, 16), (64, x)]
		ret = cls()
		matched = cls._splitter.finditer(s)
		for mo in matched:
			arrows: str = mo.group(0)
			if arrows[0] == "#":
				continue
			try:
				ticks: str = next(matched).group(0)
			except StopIteration:
				raise PokeImportError("Bad AI, missing tick count for final command.") from None

			if not ticks.isdecimal():
				raise PokeImportError(f"Expected tick count, found {ticks}")

			ticks_i = int(ticks)
			if arrows[0] == "↥" and all(x in "ABC" for x in arrows[1:]):
				value = ret.ops[-1][0] | cls.A
				if "B" in arrows:
					value |= cls.B
				if "C" in arrows:
					value |= cls.C
				ret.ops.append((value, ticks_i))
			elif arrows in ("↠", "»"):
				ret.ops.append((cls.RIGHT | cls.B, ticks_i))
			elif arrows in ("↞", "«"):
				ret.ops.append((cls.LEFT | cls.B, ticks_i))
			else:
				direction = 0
				for a in arrows:
					if a in "↥↠»↞«":
						suggest = "A" if a == "↥" else "B"
						raise PokeImportError(
							f"{a} direction cannot be used with other directions. Use {suggest} instead."
						)

					try:
						direction |= cls.arrow_to_dir[a]
					except KeyError:
						raise PokeImportError(f"Key {a} is unknown.")
				ret.ops.append((direction, ticks_i))

		ret.ops.append((0xff, 0))
		return ret


class SpriteAttrs(NamedTuple):
	x: int
	y: int
	tile: int
	enable: bool
	invert_color: bool
	vflip: bool
	hflip: bool

	def to_bin(self) -> bytes:
		options = (0x08 if self.enable else 0x00) | (0x04 if self.invert_color else
			0x00) | (0x02 if self.vflip else 0x00) | (0x01 if self.hflip else 0x00)
		return struct.pack("BBBB", self.x, self.y, self.tile, options)

	@classmethod
	def from_bin(cls, b: bytes) -> "TrackSplash":
		options = b[3]
		return cls(
			b[0], b[1], b[2], bool(options & 0x08), bool(options & 0x04), bool(options & 0x02),
			bool(options & 0x01)
		)


class GrandPrixTrackMetaData(NamedTuple):
	# bases are 3 bytes, the rest are 1
	tileset_base: int
	tilemap_base: int
	width: int
	height: int
	bg_music: int
	starting_x: int
	starting_y: int
	unk2: int
	sprite_base: int
	preview_tileset_base: int
	preview_tilemap_base: int
	preview_map_width: int
	preview_map_height: int

	@classmethod
	def from_bin(cls, b: bytes) -> "GrandPrixTrackMetaData":
		return cls(
			*(
			int.from_bytes(a, "little") if isinstance(a, bytes) else a
			for a in struct.unpack("<3s3s6B3s3s3s2B", b)
			)
		)

	def to_bin(self) -> bin:
		return struct.pack(
			"<3s3s6B3s3s3s2B", to3b(self.tileset_base), to3b(self.tilemap_base), self.width,
			self.height, self.bg_music, self.starting_x, self.starting_y, self.unk2,
			to3b(self.sprite_base), to3b(self.preview_tileset_base),
			to3b(self.preview_tilemap_base), self.preview_map_width, self.preview_map_height
		)


class GrandPrixTrack:
	ident: str
	index: Optional[int]

	bases: Dict[str, int]
	metadata: GrandPrixTrackMetaData
	tilemap: Sequence[int]
	preview_tilemap: Sequence[int]
	title_ditto_tilemap: Sequence[int]
	title_ranking_tilemap: Sequence[int]
	splash_spritemap: Sequence[SpriteAttrs]

	bgm: MinLibSound

	ai_easy: TrackGhost
	ai_normal: TrackGhost
	ai_hard: TrackGhost

	def __init__(self, ident: str, index: int, *, config: Dict[str, Any]):
		self.bases = {}
		self.ident = ident
		self.index = index
		self.config = config

	def read(self, f: BinaryIO):
		idx, config = self.index, self.config
		metadata_base = read2b_base(f, config["metadata_array_base"], idx)
		title_ditto_base = read2b_base(f, config["titles_nobar_tilemaps_array_base"], idx)
		title_ranking_base = read2b_base(f, config["titles_bar_tilemaps_array_base"], idx)

		f.seek(config["track_screens_array_base"] + 2 * idx)
		splash_map_base = 0x070000 | int.from_bytes(f.read(2), "little")

		ai_easy_base = read2b_base(f, config["ai_easy_table_base"], idx)
		ai_normal_base = read2b_base(f, config["ai_normal_table_base"], idx)
		ai_hard_base = read2b_base(f, config["ai_hard_table_base"], idx)

		self.bases = {
			"ai_easy": ai_easy_base,
			"ai_normal": ai_normal_base,
			"ai_hard": ai_hard_base,
			"metadata": metadata_base,
			"title_ditto": title_ditto_base,
			"title_ranking": title_ranking_base,
			"splash_map": splash_map_base,
		}

		f.seek(splash_map_base)
		splash_map_data = f.read(12 * 4)
		self.splash_spritemap = [
			SpriteAttrs.from_bin(splash_map_data[i:i + 4]) for i in range(0, 12 * 4, 4)
		]

		f.seek(ai_easy_base)
		self.ai_easy = TrackGhost.from_bin(f)

		f.seek(ai_normal_base)
		self.ai_normal = TrackGhost.from_bin(f)

		f.seek(ai_hard_base)
		self.ai_hard = TrackGhost.from_bin(f)

		f.seek(metadata_base)
		self.metadata = GrandPrixTrackMetaData.from_bin(f.read(23))
		load_tileset(f, self.metadata.tileset_base, height=10)
		load_tileset(f, self.metadata.preview_tileset_base)

		f.seek(self.metadata.tilemap_base)
		self.tilemap = f.read(self.metadata.width * self.metadata.height)
		f.seek(self.metadata.preview_tilemap_base)
		self.preview_tilemap = f.read(
			self.metadata.preview_map_width * self.metadata.preview_map_height
		)

		# right-aligned
		f.seek(title_ditto_base)
		self.title_ditto_tilemap = f.read(8)

		# right-aligned and double lined (screen border)
		f.seek(title_ranking_base)
		self.title_ranking_tilemap = f.read(8)

		load_spriteset(f, self.metadata.sprite_base, height=12)

	def write(self, f: BinaryIO, update_out: dict):
		idx, config = self.index, self.config

		write2b_base_and_seek(f, config["metadata_array_base"], idx, self.bases["metadata"])
		f.write(self.metadata.to_bin())

		f.seek(self.metadata.tileset_base)
		f.write(encode_tiles(self.tileset))
		f.seek(self.metadata.preview_tileset_base)
		f.write(encode_tiles(self.preview_tileset))

		f.seek(self.metadata.tilemap_base)
		f.write(self.tilemap)
		f.seek(self.metadata.preview_tilemap_base)
		f.write(self.preview_tilemap)

		update_out["ai"].add(self)
		update_out["music"].add(self.bgm)
		update_out["tilesets"] |= {self.metadata.tileset_base, self.metadata.preview_tileset_base}
		update_out["spritesets"].add(self.metadata.sprite_base)

	@property
	def bgm(self):
		return music[self.metadata.bg_music]

	@property
	def tileset(self):
		return tilesets[self.metadata.tileset_base]

	@property
	def spriteset(self):
		return spritesets[self.metadata.sprite_base]

	@property
	def preview_tileset(self):
		return tilesets[self.metadata.preview_tileset_base]
