"""Assemble only regular files; never open a device path for writing."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import stat
import struct
import subprocess


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def regular(path, exists=True):
    if path.is_symlink() or (path.exists() and not stat.S_ISREG(path.stat().st_mode)):
        raise SystemExit('Regular files only: ' + str(path))
    if exists and not path.is_file():
        raise SystemExit('Missing input: ' + str(path))


parser = argparse.ArgumentParser()
parser.add_argument('iso', type=Path)
parser.add_argument('esp', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
for path in (args.iso, args.esp):
    regular(path)
regular(args.output, False)
if args.output.exists():
    raise SystemExit('Refusing to replace an existing output')
manifest_path = args.output.with_suffix('.manifest.json')
if manifest_path == args.output:
    raise SystemExit('Image output must differ from its manifest')
regular(manifest_path, False)
if manifest_path.exists():
    raise SystemExit('Refusing to replace an existing manifest')
if args.esp.stat().st_size != 256 * 1024**2:
    raise SystemExit('Expected 256 MiB ESP image')
if args.iso.stat().st_size < 17 * 2048 or args.iso.stat().st_size % 2048:
    raise SystemExit('Expected a nonempty sector-aligned ISO9660 image')
with args.esp.open('rb') as stream:
    stream.seek(82)
    if stream.read(8) != b'FAT32   ':
        raise SystemExit('Expected FAT32 ESP')
with args.iso.open('rb') as stream:
    stream.seek(16 * 2048)
    if stream.read(7) != b'\x01CD001\x01':
        raise SystemExit('Expected ISO9660 primary volume descriptor')
esp_start = 2048
esp_sectors = args.esp.stat().st_size // 512
iso_start = esp_start + esp_sectors
iso_sectors = (args.iso.stat().st_size + 511) // 512
total = ((iso_start + iso_sectors + 2047) // 2048) * 2048
mbr = bytearray(512)
struct.pack_into('<I', mbr, 440, 0x544e3332)  # Generic TN32 format signature.
for offset, kind, start, size in ((446, 0xef, esp_start, esp_sectors),
                                (462, 0x83, iso_start, iso_sectors)):
    mbr[offset:offset + 16] = struct.pack('<B3sB3sII', 0x80 if offset == 446 else 0,
                                       b'\xfe\xff\xff', kind, b'\xfe\xff\xff', start, size)
mbr[510:] = b'\x55\xaa'
with args.output.open('xb') as out:
    out.truncate(total * 512)
    out.seek(0)
    out.write(mbr)
    for start, path in ((esp_start, args.esp), (iso_start, args.iso)):
        out.seek(start * 512)
        with path.open('rb') as src:
            shutil.copyfileobj(src, out, 8 * 1024**2)
    out.flush()
    os.fsync(out.fileno())
manifest = {'image': args.output.name, 'bytes': args.output.stat().st_size,
            'sha256': sha(args.output), 'payload_iso_sha256': sha(args.iso),
            'esp_sha256': sha(args.esp), 'contains_machine_specific_settings': False,
            'physical_boot_accepted': False, 'public_release_accepted': False}
with manifest_path.open('x') as stream:
    stream.write(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(manifest))
