"""Embed the model's credited artwork in Windows PE icons without Wine."""
from pathlib import Path
import struct


def icon_entries(icon):
    data = Path(icon).read_bytes()
    reserved, kind, count = struct.unpack_from('<HHH', data)
    assert (reserved, kind) == (0, 1)
    entries = []
    for index in range(count):
        w, h, colors, zero, planes, bits, size, start = struct.unpack_from('<BBBBHHII', data, 6 + index * 16)
        pixels = data[start:start + size]
        assert len(pixels) == size
        entries.append(((w, h, colors, zero, planes, bits, size), pixels))
    return entries


def apply_icon(executable, icon):
    import lief
    binary = lief.PE.parse(str(executable))
    assert binary and binary.has_resources
    # Only replace icon groups/images; preserve Chromium cursors and manifest.
    original_manifest = binary.resources_manager.manifest
    original_sections = {s.name: bytes(s.content) for s in binary.sections if s.name != '.rsrc'}
    for kind in (3, 14):
        binary.resources.delete_child(kind)
    images = lief.PE.ResourceDirectory(3)
    groups = lief.PE.ResourceDirectory(14)
    entries = icon_entries(icon)
    group = bytearray(struct.pack('<HHH', 0, 1, len(entries)))
    for index, (fields, pixels) in enumerate(entries, 1):
        group.extend(struct.pack('<BBBBHHIH', *fields, index))
        item = lief.PE.ResourceDirectory(index)
        leaf = lief.PE.ResourceData(list(pixels)); leaf.id = 1033
        item.add_child(leaf); images.add_child(item)
    item = lief.PE.ResourceDirectory(1)
    leaf = lief.PE.ResourceData(list(group)); leaf.id = 1033
    item.add_child(leaf); groups.add_child(item)
    binary.resources.add_child(images); binary.resources.add_child(groups)
    config = lief.PE.Builder.config_t(); config.resources = True
    temporary = Path(executable).with_suffix('.branded.exe')
    binary.write(str(temporary), config)
    result = lief.PE.parse(str(temporary))
    assert result.resources_manager.manifest == original_manifest
    assert result.optional_header.addressof_entrypoint == binary.optional_header.addressof_entrypoint
    for section in result.sections:
        if section.name in original_sections:
            assert bytes(section.content) == original_sections[section.name], section.name
    assert [bytes(i.pixels) for i in result.resources_manager.icons] == [p for _, p in entries]
    temporary.replace(executable)


def make_assets(root):
    from PIL import Image
    assets = root / 'assets'; assets.mkdir(exist_ok=True)
    image = Image.open(root / 'assets/whale-portrait.png').convert('RGBA')
    image.save(assets / 'whale.png')
    image.save(assets / 'whale.ico', sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)], bitmap_format='bmp')


if __name__ == '__main__':
    make_assets(Path(__file__).resolve().parent)
