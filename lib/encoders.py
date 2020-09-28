from PIL.Image import Image


def encode_tiles(im: Image) -> bytes:
	ret = bytearray()
	bitmasks = (1, 2, 4, 8, 0x10, 0x20, 0x40, 0x80)
	im = im.convert("1")

	for base_y in range(0, im.height, 8):
		for x in range(0, im.width):
			pixel = 0
			for m, y in zip(bitmasks, range(base_y, base_y + 8)):
				if not im.getpixel((x, y)):
					pixel |= m
			ret.append(pixel)

	return bytes(ret)
