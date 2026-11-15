"""Minimal MessagePack decoder.

Blender does not ship the `msgpack` package, so the DTS v31 reader uses this
small pure-Python decoder instead. Only decoding is implemented.
"""
import struct


class MsgPackReader:
    def __init__(self, data, pos: int = 0):
        self.data = data
        self.pos = pos

    @property
    def at_end(self) -> bool:
        return self.pos >= len(self.data)

    def read(self):
        """Read the next value from the stream."""
        d = self.data
        b = d[self.pos]
        self.pos += 1

        if b <= 0x7F:
            return b
        if b >= 0xE0:
            return b - 256
        if 0x80 <= b <= 0x8F:
            return self._map(b & 0x0F)
        if 0x90 <= b <= 0x9F:
            return self._array(b & 0x0F)
        if 0xA0 <= b <= 0xBF:
            return self._str(b & 0x1F)

        if b == 0xC0:
            return None
        if b == 0xC2:
            return False
        if b == 0xC3:
            return True

        if b in (0xC4, 0xC5, 0xC6):  # bin 8/16/32
            n = self._uint({0xC4: 1, 0xC5: 2, 0xC6: 4}[b])
            return self._raw(n)

        if b in (0xCA, 0xCB, 0xCC, 0xCD, 0xCE, 0xCF, 0xD0, 0xD1, 0xD2, 0xD3):
            fmt = {0xCA: '>f', 0xCB: '>d', 0xCC: '>B', 0xCD: '>H', 0xCE: '>I',
                   0xCF: '>Q', 0xD0: '>b', 0xD1: '>h', 0xD2: '>i', 0xD3: '>q'}[b]
            value = struct.unpack_from(fmt, d, self.pos)[0]
            self.pos += struct.calcsize(fmt)
            return value

        if b in (0xD9, 0xDA, 0xDB):  # str 8/16/32
            n = self._uint({0xD9: 1, 0xDA: 2, 0xDB: 4}[b])
            return self._str(n)
        if b in (0xDC, 0xDD):  # array 16/32
            return self._array(self._uint(2 if b == 0xDC else 4))
        if b in (0xDE, 0xDF):  # map 16/32
            return self._map(self._uint(2 if b == 0xDE else 4))

        if b in (0xD4, 0xD5, 0xD6, 0xD7, 0xD8):  # fixext
            n = {0xD4: 1, 0xD5: 2, 0xD6: 4, 0xD7: 8, 0xD8: 16}[b]
            return self._ext(n)
        if b in (0xC7, 0xC8, 0xC9):  # ext 8/16/32
            return self._ext(self._uint({0xC7: 1, 0xC8: 2, 0xC9: 4}[b]))

        raise ValueError(f"Unsupported MessagePack type byte 0x{b:02x} at offset {self.pos - 1}")

    def read_array(self, stride: int):
        """Reads a typed array as written by the v31 exporter: (count, element size, raw bytes).

        Returns (count, bytes). Empty arrays are accepted with any element size.
        """
        count = self.read()
        elem_size = self.read()
        blob = self.read()
        if not isinstance(blob, bytes):
            raise ValueError("Expected a binary blob")
        if count > 0 and elem_size != stride:
            raise ValueError(f"Unexpected element size {elem_size}, expected {stride}")
        if len(blob) != count * elem_size:
            raise ValueError("Array size does not match its element count")
        return count, blob

    def _uint(self, size):
        value = int.from_bytes(self.data[self.pos:self.pos + size], 'big')
        self.pos += size
        return value

    def _raw(self, n):
        value = bytes(self.data[self.pos:self.pos + n])
        if len(value) != n:
            raise ValueError("Truncated MessagePack data")
        self.pos += n
        return value

    def _str(self, n):
        return self._raw(n).decode('utf-8', 'replace')

    def _ext(self, n):
        ext_type = self.data[self.pos]
        self.pos += 1
        return (ext_type, self._raw(n))

    def _array(self, n):
        return [self.read() for _ in range(n)]

    def _map(self, n):
        result = {}
        for _ in range(n):
            key = self.read()
            result[key] = self.read()
        return result
