"""Split a verified raw image into GitHub-sized assets with a join manifest."""
from pathlib import Path
import argparse
import hashlib
import json
import sys

parser = argparse.ArgumentParser()
parser.add_argument('image', type=Path)
parser.add_argument('output', type=Path)
parser.add_argument('--part-size-mib', type=int, default=1800)
args = parser.parse_args()
image, output = args.image, args.output
if not 1 <= args.part_size_mib <= 1800:
    raise SystemExit('Part size must be between 1 and 1800 MiB')
if image.is_symlink() or not image.is_file():
    raise SystemExit('A regular disk image is required')
output.mkdir(parents=True, exist_ok=False)
chunk_size = args.part_size_mib * 1024**2  # Below GitHub's 2 GiB per-asset limit.
whole = hashlib.sha256()
parts = []
with image.open('rb') as src:
    index = 1
    while data := src.read(min(chunk_size, 8 * 1024**2)):
        name = image.name + f'.part-{index:03d}'
        h = hashlib.sha256()
        count = 0
        with (output / name).open('xb') as dst:
            while data:
                dst.write(data)
                h.update(data)
                whole.update(data)
                count += len(data)
                if count == chunk_size:
                    break
                data = src.read(min(chunk_size - count, 8 * 1024**2))
        parts.append({'file': name, 'bytes': count, 'sha256': h.hexdigest()})
        index += 1
manifest = {'image': image.name, 'bytes': image.stat().st_size,
            'sha256': whole.hexdigest(), 'parts': parts}
(output / 'download-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
(output / 'SHA256SUMS.txt').write_text(''.join(f"{p['sha256']}  {p['file']}\n" for p in parts) +
                                    f"{whole.hexdigest()}  {image.name}\n")
print(json.dumps(manifest))
