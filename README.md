# Torque3D-DTS-Importer
DTS Torque3D Importer Tool

A Blender add-on that imports Torque3D shapes (.dts) into Blender.

This is a fork of DynamixThreeSpaceBlenderAddon by Dummiesman, extended with support for newer DTS versions, including the BeamNG DTS version 31.

Short description for the GitHub "About" field: Blender importer for Torque3D shapes (.dts), versions 19–28 and 31 (BeamNG).

Features
Imports meshes with positions, normals, UV channels and vertex colors
Imports the node hierarchy with node transforms
Imports materials (names and flags) and assigns them per face
Reads DTS 27+ shared vertex buffers
Reads BeamNG DTS version 31 (MessagePack container, Zstandard-compressed body)
Supported DTS versions
Version	Source	Status
19–26	Torque3D / TGE-era	Supported (tested on 24 and 26)
27	Torque3D	Should work like 28, not tested
28	Torque3D 4.x	Supported (tested)
29	Torque3D (newer)	Attempted, not tested. Files encrypted with a project password cannot be read
30	—	Not a readable shape format, rejected
31	BeamNG	Supported (tested on a real file)

Versions below 19 (Tribes 2 and similar) are not supported.

Not imported yet
Animation sequences (version 31: not parsed; the material list is located by scanning)
Skinned mesh weights and bones (skinned meshes are read as plain meshes in versions up to 28; type 1 meshes in version 31 raise an error)
Decals, IFL materials, triggers, billboard detail levels

If you have a file that fails to import, please open an issue and attach it.

Installation
Download the latest zip from the Releases page. The zip must contain the add-on folder at its root.
In Blender: Edit → Preferences → Add-ons → Install from Disk… and pick the zip.
Enable DTS Torque3D Importer Tool.
Import with File → Import → Torque3D Shape (*.dts).

If you are updating, remove the old version first and restart Blender, otherwise Blender keeps the old code in memory.

Tested with Blender 4.5. The add-on declares Blender 3.6 as the minimum version.

Requirements for DTS version 31

Version 31 bodies are compressed with Zstandard. Blender does not ship a Python Zstandard module, so the add-on looks for one of these, in order:

the zstandard Python package
the zstd Python package
a system libzstd (loaded through ctypes)

If none is found, the import stops with a message. To install the package into Blender's own Python (Windows example):

"C:\Program Files\Blender Foundation\Blender 4.5\4.5\python\bin\python.exe" -m pip install zstandard

Versions 19–28 do not need any extra libraries.

Notes
Large models can import slowly. A BeamNG car with about 1.7 million triangles takes a while because meshes are built with bmesh.
Vertices that share a position and normal are merged to make the result friendlier for Blender, since DTS stores a separate vertex for every UV/normal combination.
Credits
Dummiesman: author of the original add-on
Graphite: author of this fork
License

See the LICENSE file. This project is derived from the original add-on and keeps its license.
