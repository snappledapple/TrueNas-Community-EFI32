#!/bin/sh
# Linux + Docker. Does not open physical drives or run an installer.
set -eu
if test "$#" != 2; then
    echo 'Usage: sh build.sh /path/to/official.iso /path/to/new-empty-build-directory' >&2
    exit 2
fi
ISO=$(realpath "$1")
test -f "$ISO" && test ! -L "$ISO"
test "$(sha256sum "$ISO" | cut -d' ' -f1)" = 515a0252e72f1a6c86d603fa4d1661333029fe9a4804d0a7a28d24fe4f63498e
test ! -e "$2"
mkdir -p "$2"
WORK=$(realpath "$2")
SOURCE=$(CDPATH='' cd -- "$(dirname "$0")" && pwd)
cp "$ISO" "$WORK/official-base.iso"
mkdir "$WORK/source"
cp "$SOURCE/"*.py "$SOURCE/"*.sh "$SOURCE/"*.cfg "$WORK/source/"
cp "$SOURCE/README.md" "$SOURCE/LICENSE" "$SOURCE/THIRD_PARTY.md" "$WORK/source/"
cp -a "$SOURCE/src" "$WORK/source/"
DEBIAN=debian:trixie-slim@sha256:a72b4433de1cf7d6bae0c4cee74d0547f58601a643b3375f070c51600d63b6b2
ALPINE=alpine:3.24@sha256:be2656061b536c1883c4034790e21d0a09c5aaaf51968b89368a3c0371ea2c9a
docker run --rm -v "$WORK:/work" "$ALPINE" sh /work/source/build_grub.sh
CID=$(docker run --rm -d -v "$WORK:/work" "$DEBIAN" sleep infinity)
trap 'docker stop "$CID" >/dev/null' EXIT
docker exec "$CID" sh -ec 'apt-get update; apt-get install -y --no-install-recommends squashfs-tools xorriso mtools dosfstools python3 ca-certificates; apt-get clean'
docker exec "$CID" sh -ec 'xorriso -osirrox on -indev /work/official-base.iso -extract /live/filesystem.squashfs /work/original-live.squashfs; unsquashfs -no-progress -processors 2 -d /work/live-root /work/original-live.squashfs'
# Bind only these character devices: build workspaces mounted nodev cannot use
# the extracted root's own device nodes. No block devices or host /proc are passed.
docker run --rm -v "$WORK:/work" \
    -v /dev/null:/work/live-root/dev/null \
    -v /dev/random:/work/live-root/dev/random \
    -v /dev/urandom:/work/live-root/dev/urandom \
    "$DEBIAN" sh /work/source/install_offline_ssh.sh /work/live-root
docker exec "$CID" python3 /work/source/prepare_root.py /work/live-root
docker exec "$CID" sh -ec 'chroot /work/live-root dpkg-query -W > /work/component-versions.txt; mksquashfs /work/live-root /work/public-live.squashfs -comp xz -b 1M -processors 2 -no-progress; sh /work/source/remaster.sh; python3 /work/source/build_image.py /work/public-installer.iso /work/public-esp.img /work/TrueNAS-27-RC1-EFI32-community.img'
echo "Build candidate: $WORK/TrueNAS-27-RC1-EFI32-community.img"
echo 'Validate privacy, firmware boot, installation and direct boot before release.'
