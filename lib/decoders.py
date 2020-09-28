import struct
from typing import BinaryIO

from PIL import Image
from PIL.ImageFile import PyDecoder


class TileDecoder(PyDecoder):
	def decode(self, b: bytes):
		if len(b) % 8 != 0:
			raise Exception("tile too smol")

		width = self.state.xsize

		if width % 8 != 0:
			raise Exception("canvas too smol")

		raw = bytearray(width * self.state.ysize)

		for i in range(0, len(b), width):
			data = b[i:i + width]
			plop_blanks = width - len(data)

			if plop_blanks > 0:
				data += b"\0" * plop_blanks

			i *= 8
			for m, x in zip((1, 2, 4, 8, 0x10, 0x20, 0x40, 0x80), range(i, i + width * 8, width)):
				for d in data:
					raw[x] = 0 if d & m else 0xff
					x += 1

		self.set_as_raw(bytes(raw))
		return -1, 0

	@staticmethod
	def from_stream(f: BinaryIO, width: int = 16, height: int = 16) -> Image.Image:
		return Image.frombytes("L", (width * 8, height * 8), f.read(width * height * 8), "tile")


Image.register_decoder("tile", TileDecoder)


def bigQ_into_bytearray(tile: int, mask: int, im: Image.Image, start_x: int, start_y: int):
	cols = [((tile >> x) & 0xff, (mask >> x) & 0xff) for x in range(56, -1, -8)]

	for m, y in zip((1, 2, 4, 8, 0x10, 0x20, 0x40, 0x80), range(start_y, start_y + 8)):
		for (c, a), x in zip(cols, range(start_x, start_x + 8)):
			im.putpixel((x, y), (0 if c & m else 0xff, 0 if a & m else 0xff))


class SpriteDecoder(PyDecoder):
	def decode(self, b: bytes):
		if len(b) % 64 != 0:
			raise Exception("sprite too smol")

		width = self.state.xsize

		if width % 16 != 0:
			raise Exception("canvas too smol")

		x, y = 0, 0
		bwidth = width // 16 * 64

		for i in range(0, len(b), bwidth):
			data = b[i:i + bwidth]

			for j in range(0, len(data), 64):
				m1, m2, d1, d2, m3, m4, d3, d4 = struct.unpack(">8Q", data[j:j + 64])
				ul_data, bl_data, ur_data, br_data = d1 & ~m1, d2 & ~m2, d3 & ~m3, d4 & ~m4

				bigQ_into_bytearray(ul_data, m1, self.im, x, y)
				bigQ_into_bytearray(ur_data, m3, self.im, x + 8, y)
				bigQ_into_bytearray(bl_data, m2, self.im, x, y + 8)
				bigQ_into_bytearray(br_data, m4, self.im, x + 8, y + 8)
				x += 16

			x = 0
			y += 16

		return -1, 0

	@staticmethod
	def from_stream(f: BinaryIO, width: int = 16, height: int = 16) -> Image.Image:
		return Image.frombytes(
			"LA", (width * 16, height * 16), f.read(width * height * 64), "sprite"
		)


Image.register_decoder("sprite", SpriteDecoder)
