import os
import json
import struct
import warnings
from typing import BinaryIO, Dict, Iterator, List, Sequence, Union, TYPE_CHECKING

from PIL import Image

from .decoders import TileDecoder, SpriteDecoder
from .encoders import encode_tiles

if TYPE_CHECKING:
	from .sound import MinLibSound
	from .structures import GrandPrixTrack, SpriteAttrs

music: Dict[int, "MinLibSound"] = {}
tilesets: Dict[int, Image.Image] = {}
spritesets: Dict[int, Image.Image] = {}


class PokeImportError(Exception):
	pass


class PokeImportWarning(Warning):
	def warn(self):
		warnings.warn(self, stacklevel=2)


def load_tileset(f: BinaryIO, base: int, height=16):
	if base not in tilesets:
		f.seek(base)
		tilesets[base] = TileDecoder.from_stream(f, height=height)


def save_tileset(f: BinaryIO, base: int):
	if base in tilesets:
		raw = encode_tiles(tilesets[base])
		f.seek(base)
		f.write(raw)


def write_tileset(tileset: int, folder: str) -> str:
	img = tilesets[tileset]
	fn = os.path.join(folder, f"tileset_{tileset:06x}.png")
	img.save(fn)
	return fn


def load_spriteset(f: BinaryIO, base: int, height=16) -> Image.Image:
	if base not in spritesets:
		f.seek(base)
		spritesets[base] = SpriteDecoder.from_stream(f, height=height)
	return spritesets[base]


def write_spriteset(spriteset: int, folder: str):
	img = spritesets[spriteset]
	fn = os.path.join(folder, f"spriteset_{spriteset:06x}.png")
	img.save(fn)


def write_info(track: "GrandPrixTrack", folder: str):
	fn = os.path.join(folder, f"{track.ident}.json")
	with open(fn, "wt") as f:
		json.dump(dict(track.metadata._asdict()), f, indent=4, sort_keys=True)


def render_map(width: int, height: int, map: Sequence[int], tileset: Image.Image) -> Image.Image:
	width_tiles = tileset.width // 8
	img = Image.new("L", (width * 8, height * 8))
	for i, tile in enumerate(map):
		x = (i % width) * 8
		y = (i // width) * 8
		set_x = (tile % width_tiles) * 8
		set_y = (tile // width_tiles) * 8
		t = tileset.crop((set_x, set_y, set_x + 8, set_y + 8))
		img.paste(t, (x, y, x + 8, y + 8))
	return img


def render_spritemap(
	width: int, height: int, map: Sequence["SpriteAttrs"], spriteset: Image.Image
) -> Image.Image:
	min_x, max_x, min_y, max_y = 0, 0, 0, 0
	for attrs in map:
		min_x = min(min_x, attrs.x)
		max_x = max(max_x, attrs.x)
		min_y = min(min_y, attrs.y)
		max_y = max(max_y, attrs.y)
	max_x += 16
	max_y += 16
	width_tiles = spriteset.width // 16

	img = Image.new("LA", (max_x - min_x, max_y - min_y))
	for attrs in map:
		x = attrs.x - min_x
		y = attrs.y - min_y
		set_x = (attrs.tile % width_tiles) * 16
		set_y = (attrs.tile // width_tiles) * 16
		t = spriteset.crop((set_x, set_y, set_x + 16, set_y + 16))
		img.paste(t, (x, y, x + 16, y + 16))
	return img


def draw_track(track: "GrandPrixTrack", folder: str):
	fn = os.path.join(folder, f"{track.ident}_render.png")
	img = render_map(track.metadata.width, track.metadata.height, track.tilemap, track.tileset)
	img.save(fn)

	fn = os.path.join(folder, f"{track.ident}_preview_render.png")
	img = render_map(
		track.metadata.preview_map_width, track.metadata.preview_map_height, track.preview_tilemap,
		track.preview_tileset
	)
	img.save(fn)

	fn = os.path.join(folder, f"{track.ident}_titles.png")
	title_idx = track.title_index * 8
	img = Image.new("L", (64, 24))
	title = render_map(8, 1, list(range(title_idx, title_idx + 8)), tilesets[TITLES_GRANDPRIX])
	img.paste(title, (0, 0, 64, 8))
	title = render_map(8, 1, track.title_ranking_tilemap, tilesets[TITLES_RANKING])
	img.paste(title, (0, 8, 64, 16))
	title = render_map(8, 1, track.title_ditto_tilemap, tilesets[TITLES_RANKING])
	img.paste(title, (0, 16, 64, 24))
	img.save(fn)


class BaseTable:
	"""
	Represents an array of pointers which point to contiguous data.
	Please instantiate Table or TableFixed.
	"""
	base: int
	count: int
	bsize: int
	indices: List[int]

	def __init__(self, base: int, count: int, bsize: int = 2):
		self.base = base
		self.count = count
		self.bsize = bsize
		self.indices: List[int] = []

	def read(self, f: BinaryIO):
		f.seek(self.base)
		raw = f.read(self.count * self.bsize)
		res = struct.unpack(["B", "H", "HB"][self.bsize - 1] * self.count, raw)
		if self.bsize == 3:
			self.indices = [(hi << 16) | lo for lo, hi in zip(res[::2], res[1::2])]
		elif self.bsize == 2:
			hi = self.base & 0xff0000
			self.indices = [hi | lo for lo in res]
		else:
			raise Exception("show me a use of 1 byte tables")

	def read_entry(self, f: BinaryIO, idx: int) -> bytes:
		raise NotImplementedError

	def iter_entries(self, f: BinaryIO) -> Iterator[bytes]:
		raise NotImplementedError


class Table(BaseTable):
	""" A table for poiting to variable-length data. """
	def __init__(
		self, base: int, count: int, ending: Union[bytes, Sequence[bytes]], bsize: int = 2
	):
		super().__init__(base, count, bsize)
		self.ending = (ending, ) if isinstance(ending, bytes) else ending
		self.end_length = len(self.ending[0])
		if any(len(e) != self.end_length for e in self.ending):
			raise Exception("for now, all expected endings must be the same length")
		self.lengths: List[int] = []

	def _parity(self, x: int) -> bool:
		assert x <= 0x3fff
		return bool(sum(map(int, f"{x:b}")) & 1)

	def read(self, f: BinaryIO):
		super().read(f)

		lookup = {idx: i for i, idx in enumerate(self.indices)}
		self.lengths = [0] * len(self.indices)

		prev = 0
		for idx in sorted(self.indices):
			if prev:
				self.lengths[lookup[prev]] = idx - prev
			prev = idx

		f.seek(idx)
		while f.read(self.end_length) not in self.ending:
			pass

		maybe_padding = f.read(1)[0]
		maybe_parity = maybe_padding & 0x40
		if maybe_padding & 0x80:
			maybe_padding = ((maybe_padding & 0x3f) << 8) | f.read(1)[0]
			length_size = 2
		else:
			length_size = 1

		if bool(self._parity(maybe_padding)) == bool(maybe_parity):
			# Padding probably exists of length maybe_padding, including the bytes read.
			maybe_padding -= length_size
			padding = f.read(maybe_padding)
			if any(p for p in padding):
				# If they're not all 00s, this wasn't padding
				f.seek(-(maybe_padding + length_size), 1)

		self.lengths[lookup[idx]] = f.tell() - idx

	def _read_entry(self, f: BinaryIO, length: int) -> bytes:
		ret = f.read(length)
		# trim to true ending, if there's any padding to ignore
		for j in range(self.end_length, len(ret), self.end_length):
			if ret[j - self.end_length:j] in self.ending:
				return ret[:j]
		return b""

	def read_entry(self, f: BinaryIO, idx: int) -> bytes:
		f.seek(self.indices[idx])
		return self._read_entry(f, self.lengths[idx])

	def iter_entries(self, f: BinaryIO) -> Iterator[bytes]:
		if not self.indices:
			return

		it = iter(sorted(zip(self.indices, self.lengths, range(len(self.indices)))))
		base, length, i = next(it)
		f.seek(base)
		yield i, f.read(length)
		for _, length, i in it:
			yield i, self._read_entry(f, length)

	def _write_padding(self, f: BinaryIO, length: int) -> int:
		if length:
			parity = 0x40 if self._parity(length) else 0x00

			if length > 0x3f:
				written = f.write(bytes((parity | (length >> 8), length & 0xff)))
				length -= 2
			else:
				written = f.write(bytes((parity | length, )))
				length -= 1
			padding = b"\x00" * length
			return written + f.write(padding)
		return 0

	def write_entry(self, f: BinaryIO, idx: int, data: bytes, pad_extra: bool = True) -> int:
		if len(data) <= self.lengths[idx]:
			f.seek(self.indices[idx])
			written = f.write(data)

			# Calculate padding section, if any
			if pad_extra:
				pad_length = self.lengths[idx] - len(data)
				written += self._write_padding(f, pad_length)

			return written

	def write_all_entries(self, f: BinaryIO, data: Sequence[bytes], pad_extra: bool = True) -> int:
		assert len(data) <= self.count
		f.seek(sorted(self.indices)[0])
		written = 0
		new_indices = []
		for raw in data:
			new_indices.append(f.tell())
			written += f.write(raw)

		# Calculate padding section, if any
		if pad_extra:
			pad_length = sum(self.lengths) - written
			written += self._write_padding(f, pad_length)

		# Write new table
		f.seek(self.base)
		for idx in new_indices:
			if self.bsize == 2:
				assert idx & 0xff0000 == self.base & 0xff0000
				written += f.write(struct.pack("<H", idx & 0xffff))
			elif self.bsize == 3:
				written += f.write(struct.pack("<HB", idx & 0xffff, (idx & 0xff0000) >> 16))

		return written

	def check_conflicts(self, lengths: Dict[int, int]) -> int:
		"""
		Return value:
		  0 = conflict, would need to reallocate
		  1 = can overwrite inline no issue
		  2 = can fit in entire space by rewriting pointer array
		"""
		checks = [lengths[i] if i in lengths else l for i, l in enumerate(self.lengths)]
		if all(a <= b for a, b in zip(checks, self.lengths)):
			return 1
		return 2 if sum(checks) <= sum(self.lengths) else 0


class TableFixed(BaseTable):
	""" A table for pointing to fixed-length data. """
	def __init__(self, base: int, count: int, entry_size: int, bsize: int = 2):
		super().__init__(base, count, bsize)
		self.entry_size = entry_size

	def read_entry(self, f: BinaryIO, idx: int) -> bytes:
		f.seek(self.indices[idx])
		return f.read(self.entry_size)

	def iter_entries(self, f: BinaryIO) -> Iterator[bytes]:
		if not self.indices:
			return

		it = sorted(zip(self.indices, range(len(self.indices))))
		base, i = next(it)
		f.seek(base)
		yield i, f.read(self.entry_size)
		for _, i in it:
			yield i, f.read(self.entry_size)
