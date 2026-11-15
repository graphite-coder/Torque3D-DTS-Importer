"""Zstandard decompression for DTS v31 bodies.

Blender does not bundle a Python zstd module. This tries, in order:
  1. the `zstandard` package,
  2. the `zstd` package,
  3. a system libzstd through ctypes.
"""
import ctypes
import ctypes.util


def _decompress_ctypes(data: bytes) -> bytes:
    path = ctypes.util.find_library('zstd')
    candidates = [path] if path else []
    candidates += ['libzstd.so.1', 'libzstd.dylib', 'libzstd.1.dylib', 'libzstd.dll', 'zstd.dll']

    lib = None
    for name in candidates:
        try:
            lib = ctypes.CDLL(name)
            break
        except OSError:
            continue
    if lib is None:
        raise RuntimeError(
            "This DTS file is Zstandard-compressed, but no zstd library was found. "
            "Install the 'zstandard' Python package into Blender's Python, "
            "or make libzstd available on the system.")

    lib.ZSTD_getFrameContentSize.restype = ctypes.c_ulonglong
    lib.ZSTD_getFrameContentSize.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
    lib.ZSTD_decompress.restype = ctypes.c_size_t
    lib.ZSTD_decompress.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t]
    lib.ZSTD_isError.restype = ctypes.c_uint
    lib.ZSTD_isError.argtypes = [ctypes.c_size_t]

    size = lib.ZSTD_getFrameContentSize(data, len(data))
    if size >= 0xFFFFFFFFFFFFFFFE:  # unknown (-1) or error (-2)
        raise RuntimeError("Zstandard frame does not declare its content size")

    out = ctypes.create_string_buffer(size)
    result = lib.ZSTD_decompress(out, size, data, len(data))
    if lib.ZSTD_isError(result) or result != size:
        raise RuntimeError("Zstandard decompression failed")
    return out.raw


def decompress(data: bytes) -> bytes:
    try:
        import zstandard
        return zstandard.ZstdDecompressor().decompress(data)
    except ImportError:
        pass

    try:
        import zstd
        return zstd.decompress(data)
    except ImportError:
        pass

    return _decompress_ctypes(data)
