"""Stream ISO9660 files without extracting the multi-GB OS payload."""
from pathlib import Path
import hashlib
import json
import struct
import sys


def locate(stream, path):
    base = 0
    stream.seek(16 * 2048)
    descriptor = stream.read(2048)
    if descriptor[:7] != b'\x01CD001\x01':
        stream.seek(0)
        mbr = stream.read(512)
        if len(mbr) != 512 or mbr[510:] != b'\x55\xaa' or mbr[462 + 4] != 0x83:
            raise ValueError('Neither ISO nor expected EFI32 image layout')
        base = struct.unpack_from('<I', mbr, 462 + 8)[0] * 512
        stream.seek(base + 16 * 2048)
        descriptor = stream.read(2048)
    if descriptor[:7] != b'\x01CD001\x01':
        raise ValueError('Missing primary ISO9660 volume descriptor')
    root = descriptor[156:]
    extent, size = struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0]
    for part in path.strip('/').upper().split('/'):
        # Original ISO uses level-1 8.3 aliases; remaster may use level-3 names.
        aliases = {part}
        if '.' in part:
            stem, extension = part.rsplit('.', 1)
            aliases.add(stem[:8] + '.' + extension[:3])
        stream.seek(base + extent * 2048)
        directory = stream.read(size)
        offset = 0
        found = []
        while offset < len(directory):
            length = directory[offset]
            if not length:
                offset = ((offset // 2048) + 1) * 2048
                continue
            record = directory[offset:offset + length]
            name = record[33:33 + record[32]].decode('ascii', errors='replace').split(';')[0].upper().rstrip('.')
            if name in aliases:
                if record[25] & 128:
                    raise ValueError('Multi-extent file unsupported')
                found.append((struct.unpack_from('<I', record, 2)[0], struct.unpack_from('<I', record, 10)[0]))
            offset += length
        if len(found) != 1:
            raise ValueError(f'Expected exactly one ISO file {part}, found {len(found)}')
        extent, size = found[0]
    return base + extent * 2048, size


def digest(path, name):
    with Path(path).open('rb') as stream:
        offset, size = locate(stream, name)
        stream.seek(offset)
        left = size
        h = hashlib.sha256()
        while left:
            block = stream.read(min(left, 8 * 1024**2))
            if not block:
                raise EOFError(name)
            h.update(block)
            left -= len(block)
    return {'bytes': size, 'sha256': h.hexdigest()}


if __name__ == '__main__':
    result = {}
    for name in ('/TrueNAS.update', '/vmlinuz', '/initrd.img'):
        original, rebuilt = [digest(p, name) for p in sys.argv[1:3]]
        if original != rebuilt:
            raise SystemExit(f'Unexpected changed vendor payload: {name}')
        result[name] = rebuilt
    print(json.dumps({'vendor_payload_unchanged': True, 'files': result}, indent=2))
