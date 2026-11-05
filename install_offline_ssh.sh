#!/bin/sh
# Inside an isolated tooling container, operating only on extracted live root.
set -eu
R=$(realpath "$1")
test -f "$R/usr/lib/python3/dist-packages/truenas_installer/install.py"
test ! -e "$R/.efi32-packages-added"
if test -e "$R/etc/resolv.conf" || test -L "$R/etc/resolv.conf"; then
    cp -a "$R/etc/resolv.conf" "$R/etc/resolv.conf.efi32-original"
    rm "$R/etc/resolv.conf"
fi
cp /etc/resolv.conf "$R/etc/resolv.conf"
if test -e "$R/usr/sbin/policy-rc.d"; then
    cp -a "$R/usr/sbin/policy-rc.d" "$R/usr/sbin/policy-rc.d.efi32-original"
fi
printf '#!/bin/sh\nexit 101\n' > "$R/usr/sbin/policy-rc.d"
chmod 755 "$R/usr/sbin/policy-rc.d"
restore() {
    rm -f "$R/etc/resolv.conf"
    if test -e "$R/etc/resolv.conf.efi32-original" || test -L "$R/etc/resolv.conf.efi32-original"; then
        mv "$R/etc/resolv.conf.efi32-original" "$R/etc/resolv.conf"
    fi
    rm -f "$R/usr/sbin/policy-rc.d"
    if test -e "$R/usr/sbin/policy-rc.d.efi32-original"; then
        mv "$R/usr/sbin/policy-rc.d.efi32-original" "$R/usr/sbin/policy-rc.d"
    fi
}
trap restore EXIT
cat > "$R/tmp/efi32-debian.list" <<'EOF'
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://deb.debian.org/debian trixie main
deb [signed-by=/usr/share/keyrings/debian-archive-keyring.gpg] https://security.debian.org/debian-security trixie-security main
EOF
chroot "$R" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get \
    -o Dir::Etc::sourcelist=/tmp/efi32-debian.list -o Dir::Etc::sourceparts=- update
chroot "$R" /usr/bin/env DEBIAN_FRONTEND=noninteractive apt-get \
    -o Dir::Etc::sourcelist=/tmp/efi32-debian.list -o Dir::Etc::sourceparts=- \
    -o Dpkg::Options::=--force-confold install -y --no-install-recommends --no-remove openssh-server
chroot "$R" apt-get clean
rm "$R/tmp/efi32-debian.list"
find "$R/var/lib/apt/lists" -type f -delete
touch "$R/.efi32-packages-added"
