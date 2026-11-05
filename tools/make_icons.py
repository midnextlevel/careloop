"""Generate code-native journal icons using only Python's standard library."""
import struct
import zlib
from pathlib import Path

for size in (192, 512):
    pixels = bytearray()
    for y in range(size):
        pixels.append(0)
        for x in range(size):
            u, v = x / size, y / size
            color = (36, 89, 75)
            # Open cream book and its central spine, safely within maskable area.
            if .24 < u < .76 and .28 < v < .71:
                color = (247, 241, 220)
                if .49 < u < .51:
                    color = (163, 180, 151)
                if (.29 < u < .44 or .56 < u < .71) and any(abs(v-line) < .008 for line in (.4, .48, .56)):
                    color = (163, 180, 151)
            pixels.extend(color)
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind+data) & 0xffffffff)
    png = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', size, size, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(bytes(pixels))) + chunk(b'IEND', b'')
    (Path(__file__).resolve().parents[1] / 'static' / f'icon-{size}.png').write_bytes(png)
