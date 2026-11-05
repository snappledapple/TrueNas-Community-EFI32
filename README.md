# TrueNAS EFI32 Installer

A community USB installer for TrueNAS 27.0.0-RC.1 on early Intel Macs with 32-bit EFI and 64-bit CPUs.

## Download

Choose either option:

- **[MEGA](https://mega.nz/file/03olHabJ#Ql9C_EvIUTAVWqiirUfBEDXjLdx9HTR1cT6MUTR8NWg):** one 2.60 GB ZIP. Extract it to get `TrueNAS-27-RC1-EFI32.img`.
- **[GitHub Releases](https://github.com/snappledapple/TrueNas-Community-EFI32/releases):** download both `.img.part-*` files, `download-manifest.json` and `Join-Image.ps1` into one folder. Open PowerShell there and run:

  ```powershell
  powershell -NoProfile -ExecutionPolicy Bypass -File .\Join-Image.ps1
  ```

The script checks the parts and creates the same `TrueNAS-27-RC1-EFI32.img`. Choose the image files under the release's **Assets**; GitHub's automatic source archives contain the project code.

## Install

You need an 8 GB or larger USB drive and a separate drive dedicated to the TrueNAS OS.

1. Download and prepare the image using either option above.
2. Flash the image with Rufus in **DD mode** or balenaEtcher.
3. Hold **Option** while starting the Mac and select the USB EFI entry.
4. Choose **Install TrueNAS - EFI32 compatibility**, then **Install/Upgrade**.
5. Select the intended OS drive and follow the installer prompts.
6. Shut down, remove the USB and try starting from the installed drive.

**Flashing erases the USB. Installation erases the selected OS drive.** Disconnect other drives where practical.

The Mac firmware must be able to read the OS drive. NVMe detection in the installer does not guarantee boot support.

## Optional SSH

Choose **Temporary SSH** in the installer menu. Connect as `root` on port `2222` using the address and temporary password shown on screen. Verify the displayed host-key fingerprint. Access ends on reboot; no personal credentials are included in the image.

## Compatibility

**Experimental.** The installer has booted on a MacPro2,1. Internal-drive boot, full TrueNAS service startup, updates and rollback remain unverified. Known VM startup issues and build details are in [docs/BUILD.md](docs/BUILD.md).

## License

Our integration code uses the [MIT license](LICENSE). Bundled software retains its own licenses; see [THIRD_PARTY.md](THIRD_PARTY.md).

This is a community project, unaffiliated with TrueNAS or Apple.
