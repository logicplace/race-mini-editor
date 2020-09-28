import os
import re
import string
import textwrap
from typing import BinaryIO, Dict, Sequence

from .util import PokeImportError, PokeImportWarning


class MinLibSound:
	# TODO: double check this
	op_to_mml = {
		i: (
		f"o{i // 12 + 2}", ("c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b")[i % 12]
		)
		for i in range(0x49)
	}

	# This is Race-specific atm but maybe it can be generated from the tables
	op_to_mml.update({
		0x49: "r",
		0x80: "l32",
		0x81: "l16",
		0x82: "l8",
		0x83: "l8.",
		0x84: "l4",
		0x85: "l4.",
		0x86: "l2",
		0x87: "l2.",
		0x88: "l1",
		# TODO: 0x9X effects
		# TODO: What's 0xAX do
		0xb0: "w32",
		0xb1: "w48",
		0xb2: "w64",
		0xb3: "w96",
		0xb4: "w128",
		0xb5: "w160",
		# 0xc# are guesses right now, data (hex) is 02 04 08 10
		# I think this is the denominator ie 1/2, 1/4, etc
		0xc0: "%128",
		0xc1: "%64",
		0xc2: "%32",
		0xc3: "%16",
		0xf0: ";",
		0xf1: "[",
		0xf2: "]",
	})

	mml_to_op = {v: k for k, v in op_to_mml.items()}

	_splitter = re.compile(r'(/\*[\s\S]+?\*/)|//.*|(xx..)|(\d+\.*)|(/(?!\*)|[^\d.\s/]+)')

	def __init__(self, ident: str):
		self.ident = ident
		self.ops: Sequence[str] = []

	@classmethod
	def from_bin(cls, ident: str, raw: bytes) -> "MinLibSound":
		ret = cls(ident)
		for i, x in enumerate(raw):
			op = cls.op_to_mml.get(x, f"xx{x:02x}")
			(ret.ops.extend if isinstance(op, tuple) else ret.ops.append)(op)
		return ret

	def to_bin(self) -> bytes:
		ret = bytearray()
		cur_o = "o??"
		for op in self.ops:
			with_o = ""
			try:
				if op[0] == "o":
					cur_o = op
				elif op == "<":
					cur_o = f"o{int(cur_o[1:]) - 1}"
				elif op == ">":
					cur_o = f"o{int(cur_o[1:]) + 1}"
				elif op[0] in "cdefgab":
					op, l = (op[:2], op[2:]) if op[1:2] == "#" else (op[0], op[1:])
					if l:
						ret.append(self.mml_to_op[f"l{l}"])
					with_o = f" with octave {cur_o}"
					ret.append(self.mml_to_op[(cur_o, op)])
				elif op[0] == "r":
					l = op[1:]
					if l:
						ret.append(self.mml_to_op[f"l{l}"])
					ret.append(self.mml_to_op["r"])
				elif op.startswith("xx"):
					ret.append(int(op[2:], 16))
				else:
					ret.append(self.mml_to_op[op])
			except KeyError:
				raise PokeImportError(f"no way to compile {op}{with_o}") from None
		return bytes(ret)

	def optimize(self):
		# TODO: detect odd lengths out in a sequence or like permutate and find shortest idk?
		# or maybe split normalize and optimize, then we can find common patterns?
		# yapf: disable
		current: Dict[str, str] = {
			"l": "", "w": "", "%": "", "o": "",
			# Not generated (yet?)
			"v": "", "q": "", "s": "",
		}
		# yapf: enable

		new_ops = []
		for op in self.ops:
			o = op[0]
			if o == "x":
				# TODO: effects
				new_ops.append(op)
			elif o in "olw%":
				a = op[1:]
				if current[o] != a:
					new_ops.append(op)
					current[o] = a
			else:
				new_ops.append(op)
		self.ops = new_ops

	def to_pmmusic_mml(self) -> str:
		return " ".join(f"/*{op}*/" if op.startswith("xx") else op for op in self.ops)

	@classmethod
	def from_pmmusic_mml(cls, ident: str, s: str) -> "MinLibSound":
		def next_token(command: str, expect: str = "") -> str:
			comment = "//"
			while comment:
				try:
					comment, xx, numeric, op = next(it).groups()
				except StopIteration:
					raise PokeImportError("unexpected end of MML")
			if expect == "#" and not numeric.isdecimal():
				raise PokeImportError(f"expected numeric argument to {command}, got {n}")
			return xx or numeric or op

		ret = cls(ident)
		it = cls._splitter.finditer(s)
		last_op = ""

		for mo in it:
			comment: str
			xx: str
			numeric: str
			op: str
			comment, xx, numeric, op = mo.groups()
			if numeric:
				if last_op:
					ret.ops.append(last_op + numeric)
					last_op = ""
					continue
				raise PokeImportError(f"numeric with no command: {numeric}")
			elif last_op:
				if last_op == "l":
					raise PokeImportError(f"expected numeric argument to l, got {n}")
				ret.ops.append(last_op)
				last_op = ""

			if comment:
				if comment.startswith("/*xx"):
					op = comment[2:-2]
				else:
					continue

			if op[0] == "x" and op[1] in "tdapsrx":
				# TODO: effects
				if op.startswith("xx"):
					op, n = op[:2], op[2:]
					if len(n) != 2 or any(c not in string.hexdigits for c in n):
						raise PokeImportError(f"bad argument to xx: {n}")
				elif op != "xd":
					n = next_token(op, "#")
					if op == "xa":
						if next_token("xa") != ":":
							raise PokeImportError("xa expects two arguments, xaN:M")
						m = next_token("xa", "#")
						n = f"{n}:{m}"
				ret.ops.append(f"{op}{n}")
			elif op[0] in "cdefgab" and op[1:] in ("#", "+", "-", "") or op in ("r", "l", "]"):
				if op[1:] == "-":
					last_op = f"{'cdefgab'['cdefgab'.index(op[0]) - 1]}#"
				else:
					last_op = op.replace("+", "#")
			elif op in ("%", "\\", "/", "v", "w", "o", "q", "s"):
				n = next_token(op, "#")
				if op in "\\/":
					n = str(255 * int(n) // 100)
				ret.ops.append(op + n)
			elif op == "!":
				n = next_token(op, "#")
				if next_token("!") != ":":
					raise PokeImportError("! expects two arguments, !N:M")
				m = next_token("!", "#")
				ret.ops.append(f"!{n}:{m}")
			elif len(op) == 1 and op in "<>[;" + string.ascii_uppercase:
				# TODO: Macros
				ret.ops.append(op)
			else:
				raise PokeImportError(f"unknown MML command: {op}")
		if last_op == "l":
			raise PokeImportError(f"expected numeric argument to l, got {n}")
		elif last_op:
			ret.ops.append(last_op)
		return ret


def write_pmmusic(bgms: Sequence[MinLibSound], folder: str):
	with open(os.path.join(folder, "sounds.pmmusic"), "wt", encoding="utf8") as f:
		f.write("TITLE Pokémon Race mini\n")
		f.write("DESCRIPTION Dumped from the ROM\n")
		f.write("/* Edit this to change the music.\n")
		f.write(" * See pokemini's Music Converter documentation for commands.\n")
		f.write(" * Additional command: xx## where ## is the hex code of the raw byte to insert.\n")
		f.write(" */\n")

		for bgm in bgms:
			#bgm.optimize()
			mml = "\n".join(
				textwrap.wrap(bgm.to_pmmusic_mml(), initial_indent="\t", subsequent_indent="\t")
			)
			f.write(f"\nPAT {bgm.ident} {{\n{mml}\n}}\n")


def read_pmmusic(folder: str) -> Dict[str, MinLibSound]:
	music = {}
	with open(os.path.join(folder, "sounds.pmmusic"), "rt", encoding="utf8") as f:
		collecting = ""
		collection = []
		collection_name = ""
		for line in f:
			line = line.strip()
			if not line:
				continue

			if collecting:
				if line[0] == "}":
					if collecting == "pattern":
						music[collection_name] = MinLibSound.from_pmmusic_mml(
							collection_name, " ".join(collection)
						)
					collecting = ""
				else:
					collection.append(line)
					continue

			if line.startswith("VOLLVL") or line.startswith("VOLLEVEL"):
				if line.split()[1] == "system":
					# TODO: convert to mml
					raise PokeImportError("does not support VOLLVL system yet")
			elif line.startswith("OCTREV") or line.startswith("OCTAVEREV"):
				if line.split()[1] == "yes":
					# TODO: invert
					raise PokeImportError("does not support 'OCTREV yes' yet")
			elif line.startswith("SHORTQ") or line.startswith("SHORTQUANTIZE"):
				if line.split()[1] == "yes":
					# TODO: invert
					raise PokeImportError("does not support 'SHORTQ yes' yet")
			# TODO: do we need warning for MTIME/MBPM?
			elif line.startswith("PAT") or line.startswith("PATTERN"):
				_, collection_name, lbrace, *comments = line.split()
				assert lbrace == "{"  # It's required by pmmusic so idc
				collecting = "pattern"
				collection.clear()
			# TODO: BGM, SFX, *_T, MACRO, INCLUDE
			elif line.split()[0] not in {"TITLE", "COMPOSER", "PROGRAMMER", "DESCRIPTION",
				"OUTFORMAT", "VARHEADER", "OUTHEADER", "OUTFILE"}:
				PokeImportWarning(f"unknown or unsupported directive {line.split()[0]}")

	return music


# TODO: midi? wav? 3MLe's format?
