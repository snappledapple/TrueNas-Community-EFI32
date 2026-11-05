"""Read-only partition/content verification before flashing a regular .img."""
from pathlib import Path
import hashlib
import json
import stat
import struct
import sys

image, manifest_path = map(Path, sys.argv[1:3])
for path in (image, manifest_path):
    if path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode):
        raise SystemExit('Regular input files only')
manifest = json.loads(manifest_path.read_text())
assert image.stat().st_size == manifest['bytes']
with image.open('rb') as stream:
    header = stream.read(512)
    assert header[510:] == b'\x55\xaa'
    assert struct.unpack_from('<I', header, 440)[0] == 0x544e3332
    assert header[478:510] == b'\x00' * 32
    p1, p2 = [struct.unpack_from('<B3sB3sII', header, offset) for offset in (446, 462)]
    assert p1[0] == 0x80 and p1[2] == 0xef and p1[4] == 2048 and p1[5] == 524288
    assert p2[0] == 0 and p2[2] == 0x83 and p2[4] == p1[4] + p1[5]
    assert (p2[4] + p2[5]) * 512 <= manifest['bytes']
    stream.seek(p1[4] * 512 + 82)
    assert stream.read(8) == b'FAT32   '
    stream.seek(p2[4] * 512 + 16 * 2048)
    assert stream.read(7) == b'\x01CD001\x01'
    for part, expected in ((p1, manifest['esp_sha256']), (p2, manifest['payload_iso_sha256'])):
        stream.seek(part[4] * 512)
        left, digest = part[5] * 512, hashlib.sha256()
        while left:
            data = stream.read(min(left, 8 * 1024**2))
            if not data:
                raise EOFError('Partition truncated')
            digest.update(data)
            left -= len(data)
        assert digest.hexdigest() == expected
    stream.seek(0)
    assert hashlib.file_digest(stream, 'sha256').hexdigest() == manifest['sha256']
print(json.dumps({'passed': True, 'mbr_matches_proven_mac_format': True,
                  'fat32_esp': True, 'iso9660_payload': True,
                  'partition_hashes_match': True, 'whole_image_sha256': manifest['sha256']}))
