#!/bin/sh
# Regular-file inputs in /work; execute inside tooling container.
set -eu
cd /work
test -f official-base.iso
test -f public-live.squashfs
test ! -e public-installer.iso
xorriso -indev official-base.iso -outdev public-installer.iso \
    -boot_image any discard \
    -boot_image any system_area=/dev/zero \
    -boot_image any partition_table=off \
    -boot_image any partition_offset=0 \
    -map public-live.squashfs /live/filesystem.squashfs \
    -commit -end > remaster.log 2>&1
python3 source/verify_iso.py official-base.iso public-installer.iso > payload-verification.json
truncate -s 256M public-esp.img
mkfs.fat -F32 -i EF320027 -n TN_EFI32 public-esp.img > esp-build.log
mmd -i public-esp.img ::/EFI ::/EFI/BOOT ::/boot ::/boot/grub
mcopy -i public-esp.img source/assets/installer-BOOTIA32.EFI ::/EFI/BOOT/BOOTIA32.EFI
mcopy -i public-esp.img source/installer-grub.cfg ::/boot/grub/grub.cfg
mcopy -i public-esp.img source/README.md ::/README.md
mcopy -i public-esp.img source/LICENSE ::/INTEGRATION-LICENSE.txt
mcopy -i public-esp.img source/THIRD_PARTY.md ::/THIRD_PARTY.md
mcopy -i public-esp.img /usr/share/common-licenses/GPL-3 ::/GRUB-COPYING.txt
mcopy -i public-esp.img component-versions.txt ::/COMPONENTS.txt
sha256sum public-installer.iso public-live.squashfs public-esp.img > public-build.sha256
