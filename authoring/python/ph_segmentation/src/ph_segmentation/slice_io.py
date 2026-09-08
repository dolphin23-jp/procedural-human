from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct
import zlib

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class SliceDecodeError(ValueError):
    pass


@dataclass(frozen=True)
class RgbImage:
    width: int
    height: int
    pixels: bytes

    def rgb_at(self, x: int, y: int) -> tuple[int, int, int]:
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError((x, y))
        offset = (y * self.width + x) * 3
        return tuple(self.pixels[offset : offset + 3])  # type: ignore[return-value]


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _unfilter(raw: bytes, width: int, height: int, channels: int) -> bytes:
    stride = width * channels
    expected = height * (stride + 1)
    if len(raw) != expected:
        raise SliceDecodeError(
            f"unexpected decompressed PNG length: expected {expected}, got {len(raw)}"
        )
    output = bytearray(height * stride)
    source = 0
    for y in range(height):
        filter_type = raw[source]
        source += 1
        row = bytearray(raw[source : source + stride])
        source += stride
        previous_offset = (y - 1) * stride
        for x in range(stride):
            left = row[x - channels] if x >= channels else 0
            up = output[previous_offset + x] if y > 0 else 0
            up_left = output[previous_offset + x - channels] if y > 0 and x >= channels else 0
            if filter_type == 0:
                value = row[x]
            elif filter_type == 1:
                value = (row[x] + left) & 0xFF
            elif filter_type == 2:
                value = (row[x] + up) & 0xFF
            elif filter_type == 3:
                value = (row[x] + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                value = (row[x] + _paeth(left, up, up_left)) & 0xFF
            else:
                raise SliceDecodeError(f"unsupported PNG filter type {filter_type}")
            row[x] = value
        offset = y * stride
        output[offset : offset + stride] = row
    return bytes(output)


def read_png_rgb(path: str | Path) -> RgbImage:
    data = Path(path).read_bytes()
    if not data.startswith(PNG_SIGNATURE):
        raise SliceDecodeError(f"not a PNG file: {path}")

    position = len(PNG_SIGNATURE)
    width = height = bit_depth = color_type = interlace = None
    palette: bytes | None = None
    compressed = bytearray()

    while position < len(data):
        if position + 12 > len(data):
            raise SliceDecodeError("truncated PNG chunk")
        length = struct.unpack(">I", data[position : position + 4])[0]
        chunk_type = data[position + 4 : position + 8]
        payload_start = position + 8
        payload_end = payload_start + length
        if payload_end + 4 > len(data):
            raise SliceDecodeError("truncated PNG payload")
        payload = data[payload_start:payload_end]
        position = payload_end + 4

        if chunk_type == b"IHDR":
            if len(payload) != 13:
                raise SliceDecodeError("invalid IHDR")
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if compression != 0 or filtering != 0:
                raise SliceDecodeError("unsupported PNG compression/filter method")
        elif chunk_type == b"PLTE":
            palette = payload
        elif chunk_type == b"IDAT":
            compressed.extend(payload)
        elif chunk_type == b"IEND":
            break

    if None in (width, height, bit_depth, color_type, interlace):
        raise SliceDecodeError("missing PNG IHDR")
    if bit_depth != 8:
        raise SliceDecodeError("TASK-A05 reader supports only 8-bit PNG source slices")
    if interlace != 0:
        raise SliceDecodeError("TASK-A05 reader does not silently resample interlaced PNGs")

    channels_by_type = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    channels = channels_by_type.get(color_type)
    if channels is None:
        raise SliceDecodeError(f"unsupported PNG color type {color_type}")
    raw = _unfilter(zlib.decompress(bytes(compressed)), width, height, channels)

    rgb = bytearray(width * height * 3)
    for index in range(width * height):
        source = index * channels
        target = index * 3
        if color_type == 0:
            value = raw[source]
            rgb[target : target + 3] = bytes((value, value, value))
        elif color_type == 2:
            rgb[target : target + 3] = raw[source : source + 3]
        elif color_type == 3:
            if palette is None:
                raise SliceDecodeError("indexed PNG is missing PLTE")
            palette_index = raw[source] * 3
            if palette_index + 3 > len(palette):
                raise SliceDecodeError("indexed PNG references palette entry outside PLTE")
            rgb[target : target + 3] = palette[palette_index : palette_index + 3]
        elif color_type == 4:
            value = raw[source]
            rgb[target : target + 3] = bytes((value, value, value))
        else:
            rgb[target : target + 3] = raw[source : source + 3]

    return RgbImage(width=width, height=height, pixels=bytes(rgb))


def write_pgm_mask(path: str | Path, width: int, height: int, mask: bytes | bytearray) -> None:
    if len(mask) != width * height:
        raise ValueError("mask size does not match image dimensions")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    pixels = bytes(255 if value else 0 for value in mask)
    destination.write_bytes(f"P5\n{width} {height}\n255\n".encode("ascii") + pixels)
