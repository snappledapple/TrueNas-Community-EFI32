#!/bin/sh
# Alpine 3.24 x86 GRUB 2.14, with signature verification enabled.
set -eu
cd /work/source
apk add --no-cache grub=2.14-r0 grub-efi=2.14-r0 ca-certificates >/work/grub-packages.log 2>&1
wget -q -O /etc/apk/keys/alpine-devel@lists.alpinelinux.org-61666e3f.rsa.pub \
    https://alpinelinux.org/keys/alpine-devel@lists.alpinelinux.org-61666e3f.rsa.pub
mkdir -p /work/grub-packages /work/grub-extract assets
cd /work/grub-packages
apk fetch --arch x86 --repository https://dl-cdn.alpinelinux.org/alpine/v3.24/main grub-efi=2.14-r0 >>/work/grub-packages.log 2>&1
for f in ./*.apk; do tar -xzf "$f" -C /work/grub-extract; done
cd /work/source
cp -a /work/grub-extract/usr/lib/grub/i386-efi assets/
grub-script-check installer-grub.cfg
grub-script-check installed-grub.cfg
for item in installer installed; do
    grub-mkstandalone -O i386-efi -d assets/i386-efi \
        --modules="part_msdos part_gpt fat iso9660 zfs normal linux search search_fs_file search_fs_uuid configfile echo reboot halt efi_uga efi_gop all_video serial" \
        --locales="" --fonts="" -o "assets/$item-BOOTIA32.EFI" "boot/grub/grub.cfg=$item-grub.cfg"
done
grub-mkstandalone --version > assets/GRUB_VERSION.txt
sha256sum assets/*EFI
