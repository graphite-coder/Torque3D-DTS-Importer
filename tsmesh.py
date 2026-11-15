import struct
from typing import List, BinaryIO

from .tsalloc import *

class TSDrawPrimitiveType:
    Triangles = 0 << 30
    Strip = 1 << 30
    Fan = 2 << 30

    Indexed = 1 << 29
    NoMaterial = 1 << 28

    MaterialMask = ~(Strip|Fan|Triangles|Indexed|NoMaterial)
    TypeMask     = Strip|Fan|Triangles

class TSDrawPrimitive:
    def __init__(self, start, num_elements, material_and_flags):
        self.start = start
        self.num_elements = num_elements
        self.material_index = material_and_flags

        self.has_no_material = (material_and_flags & TSDrawPrimitiveType.NoMaterial) == TSDrawPrimitiveType.NoMaterial
        self.type = material_and_flags & TSDrawPrimitiveType.TypeMask
        self.material_index = material_and_flags & TSDrawPrimitiveType.MaterialMask

        
class TSNullMesh:
    pass

class TSMesh:
    def __init__(self):
            self._vertices: List[tuple[float, float, float]] = []
            self._tvertices: List[tuple[float, float]] = []
            self._t2vertices: List[tuple[float, float]] = []
            self._colors: List[tuple[float, float, float, float]] = []
            self._normals: List[tuple[float, float, float]] = []
            self._primitives: List[TSDrawPrimitive] = []
            self._indices: List[int] = []
            self._parent_mesh: int = -1

    @property
    def vertices(self) -> List[tuple[float, float, float]]:
        return self._vertices
    
    @property
    def normals(self) -> List[tuple[float, float, float]]:
        return self._normals
    
    @property
    def tvertices(self) -> List[tuple[float, float]]:
        return self._tvertices
    
    @property
    def t2vertices(self) -> List[tuple[float, float]]:
        return self._t2vertices
    
    @property
    def colors(self) -> List[tuple[float, float, float, float]]:
        return self._colors
    
    @property
    def primitives(self) -> List[TSDrawPrimitive]:
        return self._primitives
    
    @property
    def indices(self) -> List[int]:
        return self._indices
    
    def copy_vertex_data_from(self, other):
        """Copies mesh vertex data from a parent mesh"""
        self._vertices = other._vertices.copy()
        self._tvertices = other._tvertices.copy()
        self._t2vertices = other._t2vertices.copy()
        self._colors = other._colors.copy()

    def assemble_msgpack(self, reader):
        """Reads a standard mesh from a DTS v31 (MessagePack) stream."""
        num_frames = reader.read()
        num_mat_frames = reader.read()
        self._parent_mesh = reader.read()

        bounds = reader.read()  # 6 floats
        center = reader.read()  # 3 floats
        radius = reader.read()

        count, blob = reader.read_array(12)
        floats = struct.unpack(f'<{count * 3}f', blob)
        self._vertices = [floats[x:x + 3] for x in range(0, count * 3, 3)]

        count, blob = reader.read_array(8)
        floats = struct.unpack(f'<{count * 2}f', blob)
        self._tvertices = [floats[x:x + 2] for x in range(0, count * 2, 2)]

        count, blob = reader.read_array(8)
        floats = struct.unpack(f'<{count * 2}f', blob)
        self._t2vertices = [floats[x:x + 2] for x in range(0, count * 2, 2)]

        count, blob = reader.read_array(4)
        self._colors = [(blob[x] / 255.0, blob[x + 1] / 255.0, blob[x + 2] / 255.0, blob[x + 3] / 255.0)
                        for x in range(0, count * 4, 4)]

        count, blob = reader.read_array(12)
        floats = struct.unpack(f'<{count * 3}f', blob)
        self._normals = [floats[x:x + 3] for x in range(0, count * 3, 3)]

        reader.read_array(1)  # encoded normals, not needed

        count, blob = reader.read_array(12)
        values = struct.unpack(f'<{count * 3}i', blob)
        for x in range(0, count * 3, 3):
            self._primitives.append(TSDrawPrimitive(values[x], values[x + 1], values[x + 2] & 0xFFFFFFFF))

        count, blob = reader.read_array(4)
        self._indices = list(struct.unpack(f'<{count}i', blob))

        reader.read_array(16)  # tangents (vec4), not needed

        verts_per_frame = reader.read()
        flags = reader.read()

    def _read_shape_vertices(self, vertex_data, vertex_format, offset, count, size):
        """Reads this mesh's vertices from the shared shape vertex buffer (DTS 27+).

        Base vertex layout (48 bytes): position (3f), tangent handedness (f), normal (3f), tangent (3f), uv (2f).
        Optional data (second UV set, vertex color) lives at the offsets given by the shape's
        vertex format, relative to the start of each vertex.
        """
        if vertex_data is None or count <= 0:
            return
        if size < 48:
            raise ValueError(f"Unsupported vertex size {size}")

        tex2_offset, _, color_offset, _, _ = vertex_format
        base = struct.Struct('<3ff3f3f2f')

        for x in range(count):
            at = offset + x * size
            values = base.unpack_from(vertex_data, at)
            self._vertices.append(values[0:3])
            self._normals.append(values[4:7])
            self._tvertices.append(values[10:12])

            if tex2_offset >= 0 and at + tex2_offset + 8 <= len(vertex_data):
                self._t2vertices.append(struct.unpack_from('<2f', vertex_data, at + tex2_offset))
            if color_offset >= 0 and at + color_offset + 4 <= len(vertex_data):
                r, g, b, a = vertex_data[at + color_offset:at + color_offset + 4]
                self._colors.append((r / 255.0, g / 255.0, b / 255.0, a / 255.0))

    def assemble(self, ts_alloc, version, vertex_data=None, vertex_format=(-1, -1, -1, 0, 0)):
        ts_alloc.check_guard()

        num_frames = ts_alloc.read32()
        num_mat_names = ts_alloc.read32()
        parent_mesh = ts_alloc.read32()

        self._parent_mesh = parent_mesh

        bounds = [ts_alloc.read_float() for _ in range(6)]
        center = [ts_alloc.read_float() for _ in range(3)]
        radius = ts_alloc.read_float()

        vert_offset = 0
        offset_num_verts = 0
        offset_vert_size = 0

        if version >= 27:
            vert_offset = ts_alloc.read32()
            offset_num_verts = ts_alloc.read32()
            offset_vert_size = ts_alloc.read32()

        if version >= 27 and parent_mesh < 0:
            self._read_shape_vertices(vertex_data, vertex_format, vert_offset, offset_num_verts, offset_vert_size)

        # verts and texture coords
        num_verts = ts_alloc.read32()

        if parent_mesh < 0:
            verts_buffer = ts_alloc.read_float_list(num_verts*3)
            for x in range(0, num_verts*3, 3):
                vertex = (verts_buffer[x], verts_buffer[x+1], verts_buffer[x+2])
                self._vertices.append(vertex)

        num_tverts = ts_alloc.read32()
        if parent_mesh < 0:
            tverts_buffer = ts_alloc.read_float_list(num_tverts*2)
            for x in range(0, num_tverts*2, 2):
                tvertex = (tverts_buffer[x], tverts_buffer[x+1])
                self._tvertices.append(tvertex)

        # 2nd texture channel and colors
        if version > 25:
            num_t2verts = ts_alloc.read32()
            if parent_mesh < 0:
                t2verts_buffer = ts_alloc.read_float_list(num_t2verts*2)
                for x in range(0, num_t2verts*2, 2):
                    tvertex = (t2verts_buffer[x], t2verts_buffer[x+1])
                    self._t2vertices.append(tvertex)

            num_vcolors = ts_alloc.read32()
            if parent_mesh < 0:
                vcolors = ts_alloc.read32_list(num_vcolors)
                for packed_color in vcolors:
                    red   =  packed_color & 0xFF
                    green = (packed_color >> 8)  & 0xFF
                    blue  = (packed_color >> 16) & 0xFF
                    alpha = (packed_color >> 24) & 0xFF

                    self._colors.append((red / 255.0, green / 255.0, blue / 255.0, alpha / 255.0))

        # normals
        if parent_mesh < 0:
            normals_buffer = ts_alloc.read_float_list(num_verts*3)
            for x in range(0, num_verts*3, 3):
                normal = (normals_buffer[x], normals_buffer[x+1], normals_buffer[x+2])
                self._normals.append(normal)

        if version > 21 and parent_mesh < 0:
            ts_alloc.skip8(num_verts) # encoded normals, skip

        # primitives and indices
        sz_prim_in = 0
        sz_ind_in = 0

        starts = []
        elements = []
        material_indices = []
        
        if version > 25:
            # mesh primitives (start, numElements) and indices are stored as 32 bit values
            sz_prim_in = ts_alloc.read32()
            for _ in range(sz_prim_in):
                starts.append(ts_alloc.read32())
                elements.append(ts_alloc.read32())
                material_indices.append(ts_alloc.read32())

            sz_ind_in = ts_alloc.read32()
            self._indices.extend(ts_alloc.read32_list(sz_ind_in))                
        else:
            # mesh primitives (start, numElements) indices are stored as 16 bit values
            sz_prim_in = ts_alloc.read32()
            for _ in range(sz_prim_in):
                starts.append(ts_alloc.read16())
                elements.append(ts_alloc.read16())
            for _ in range(sz_prim_in):
                material_indices.append(ts_alloc.read32())

            sz_ind_in = ts_alloc.read32()
            self._indices.extend(ts_alloc.read16_list(sz_ind_in))

        # setup primitives from data
        for x in range(sz_prim_in):
            start = starts[x]
            num_elements = elements[x]
            material_index = material_indices[x]

            prim = TSDrawPrimitive(start, num_elements, material_index)
            self._primitives.append(prim)
            
        # merge indices (deprecated)
        num_merge_indices = ts_alloc.read32()
        ts_alloc.skip16(num_merge_indices)

        ts_alloc.align32()

        verts_per_frame = ts_alloc.read32()
        flags = ts_alloc.read32()

        ts_alloc.check_guard()

class TSSkinnedMesh(TSMesh):
    def __init__(self):
        super().__init__()

    def assemble(self, ts_alloc, version, vertex_data=None, vertex_format=(-1, -1, -1, 0, 0)):
        super().assemble(ts_alloc, version, vertex_data, vertex_format)

        maxBones = -1 if version < 27 else ts_alloc.read32()

        if version < 27:
            # get initial verts
            sz = ts_alloc.read32()
            if self._parent_mesh < 0:
                ts_alloc.skip32(sz * 3) # initial verts

            if version > 21:
                if self._parent_mesh < 0:
                    ts_alloc.skip32(sz * 3) # normals
                    ts_alloc.skip8(sz) # encoded normals
            else:
                if self._parent_mesh < 0:
                    ts_alloc.skip32(sz * 3) # normals

        sz = ts_alloc.read32()
        ts_alloc.skip32(16 * sz) # initial transforms

        sz = ts_alloc.read32()
        ts_alloc.skip32(sz) # vertex index list
        ts_alloc.skip32(sz) # bone index list
        ts_alloc.skip32(sz) # weight list

        sz = ts_alloc.read32()
        ts_alloc.skip32(sz) # node index list

        ts_alloc.check_guard()

    