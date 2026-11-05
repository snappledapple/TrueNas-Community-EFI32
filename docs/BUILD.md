# Building the installer

Use Linux with Docker and enough space for the official ISO, extracted filesystem and output image. Build scripts write regular files; they do not flash physical drives.

## Inputs

- TrueNAS 27.0.0-RC.1 from the [official release directory](https://iso.sys.truenas.net/TrueNAS-27-RC/27.0.0-RC.1/).
- ISO SHA256: `515a0252e72f1a6c86d603fa4d1661333029fe9a4804d0a7a28d24fe4f63498e`.
- GRUB 2.14-r0 from signed Alpine 3.24 packages.
- OpenSSH and dependencies from signed Debian trixie/security packages.

The scripts pin the container images and the expected TrueNAS installer source. Changing the TrueNAS version requires inspecting its installer, updating the source hashes and retesting. Package repositories can change, so later rebuilds can contain newer Debian packages and produce a different checksum.

## Build

From the source folder:

```sh
sh build.sh /path/to/official.iso /path/to/new-build-folder
```

The output is a disk image with a 256 MiB FAT EFI partition and an ISO9660 payload partition. Use the complete `.img` for USB flashing. The intermediate ISO is not a standalone EFI32 boot image.

## Checks

The build compares `TrueNAS.update`, `vmlinuz` and `initrd.img` with the official ISO. `verify_image.py` checks the MBR, partition filesystems, partition hashes and complete image hash:

```sh
python3 verify_image.py /path/to/image.img /path/to/image.manifest.json
```

## Current compatibility

The USB installer has started on a MacPro2,1, including optional temporary SSH. In a virtual EFI32 installation, the installed kernel loaded from ZFS with the USB detached, but `nscd`, `syslog-ng`, `chrony` and `nginx` reported startup failures. A working web interface was not verified in that environment.

Direct physical SSD boot, full service readiness, OS updates and boot-environment rollback remain unverified. The Mac firmware must be able to read the destination drive; NVMe detection in Linux and SATA-to-IDE bridge detection alone do not prove boot support.

## Release files

Package the complete disk image as one standard ZIP. From the folder containing the image, with 7-Zip installed:

```sh
7z a -tzip -mm=Deflate -mx=1 /path/to/TrueNAS-27-RC1-EFI32.img.zip TrueNAS-27-RC1-EFI32-community.img
```

Use `7z rn` to rename the entry to `TrueNAS-27-RC1-EFI32.img` if the build image has a different name. The ZIP should contain only that image at its root. Fully decompress it and compare the extracted image's SHA256 with the original before uploading.

Host the ZIP on MEGA and put its public share link in the GitHub release notes. This option needs only ZIP extraction. The current ZIP is 2.60 GB, above GitHub's release-asset limit.

For the GitHub download option, create parts under 2 GiB each:

```sh
python3 package_release.py /path/to/image.img /path/to/new-parts-folder
```

Attach both parts, `download-manifest.json` and `Join-Image.ps1` to the GitHub release. The script verifies each part and the reconstructed image. On Linux or macOS, concatenate the parts in numerical order and verify the completed image against `SHA256SUMS.txt`. Both download options must produce the same image hash. Keep large binaries out of Git history.

Attach `SHA256SUMS.txt`, `COMPONENTS.txt`, the integration license, third-party notices and `GRUB-COPYING.txt` to the GitHub release. Collect the matching component source archives and patches as part of release preparation; the final source/notice check for this experimental build is still open.
