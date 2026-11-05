# Third-party components

The repository's MIT license covers the integration code. Software bundled in the disk image retains its own copyright, license and notices.

- **TrueNAS 27.0.0-RC.1:** the OS payload, kernel and initrd come from the [official ISO](https://iso.sys.truenas.net/TrueNAS-27-RC/27.0.0-RC.1/). Original notices remain in the live filesystem and OS payload.
- **GRUB 2.14-r0, Alpine 3.24 x86:** the additional IA32 loader and modules use GPL-3.0-or-later. The matching [Alpine recipe and patches](https://github.com/alpinelinux/aports/tree/507b6419f67731e13ad07794b80c23c9df70330d/main/grub) are at aports commit `507b6419f67731e13ad07794b80c23c9df70330d`. [Upstream source](https://ftp.gnu.org/gnu/grub/grub-2.14.tar.xz). GPLv3 is included as `GRUB-COPYING.txt` in the release and on the USB.
- **OpenSSH server 1:10.0p1-7+deb13u2:** installed from signed Debian trixie/security packages. Notices are in `/usr/share/doc/openssh-server/copyright` and the dependency copyright files. [OpenSSH source](https://www.openssh.com/portable.html); [Debian sources](https://sources.debian.org/src/openssh/).

`COMPONENTS.txt` in the release lists the live filesystem's package versions. Preserve that list and the original notices when redistributing an image. Build and release preparation is described in `docs/BUILD.md` in the source repository.
