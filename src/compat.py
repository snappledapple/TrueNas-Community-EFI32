"""Version-pinned EFI32 live-installer support. No unattended disk selection."""
from pathlib import Path
import argparse
import asyncio
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types

BASE = Path('/usr/local/lib/efi32-installer')
OUTER_SHA = 'bb9f07d3ada5b2117eb8d917e5775afed17c0ab62977b7a942465ddfcdeb8446'
PAYLOAD_SHA = '03e8dccf6432740ccbd13be4339ab77e5f7e8e2357474aeecf206713f7796b17'
EFI_CHECK = 'os.path.exists("/sys/firmware/efi")'
LAUNCH = '"python3", "-m", "truenas_install",'
HOOK = '                                if os.path.exists("/sys/firmware/efi") and old_root is None:'
# Keep the video option used by both the live installer and proven Mac helper.
NOEFI_SQL = """UPDATE system_advanced SET adv_kernel_extra_options=TRIM(COALESCE(adv_kernel_extra_options,'') || ' noefi nomodeset') WHERE id=1;"""


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs)


def pinned(data, expected):
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError('Unsupported installer version: source checksum differs')
    return data.decode('utf-8')


def live_guard():
    if os.geteuid() != 0:
        raise RuntimeError('Live installer root privileges required')
    tokens = Path('/proc/cmdline').read_text().split()
    if not {'boot=live', 'noefi', 'efi32_compat=1'}.issubset(tokens):
        raise RuntimeError('Boot the EFI32 compatibility installer entry')
    if Path('/sys/firmware/efi/fw_platform_size').read_text().strip() != '32':
        raise RuntimeError('Expected 32-bit EFI firmware')
    if run(['findmnt', '-n', '-o', 'FSTYPE', '/'], text=True).stdout.strip() != 'overlay':
        raise RuntimeError('Refusing outside the live RAM overlay')
    if not Path('/cdrom/TrueNAS.update').is_file():
        raise RuntimeError('Installer media is not mounted at /cdrom')


def patch_payload(source):
    if source.count(EFI_CHECK) != 2 or source.count(HOOK) != 1:
        raise RuntimeError('Unexpected EFI branch layout')
    # Run while the selected disk ESP is mounted. Stock x64 and BIOS files stay.
    source = source.replace(HOOK, '                                from efi32_compat import install_ia32\n'
                            '                                install_ia32(root)\n\n' + HOOK)
    source = source.replace(EFI_CHECK, 'False')
    compile(source, 'efi32-payload', 'exec')
    return source


def source_preflight():
    original = Path('/usr/lib/python3/dist-packages/truenas_installer/install_vendor.py')
    outer = pinned(original.read_bytes(), OUTER_SHA)
    payload = run(['unsquashfs', '-cat', '/cdrom/TrueNAS.update',
                   'truenas_install/__main__.py']).stdout
    patch_payload(pinned(payload, PAYLOAD_SHA))  # Before the first format command.
    if outer.count(LAUNCH) != 1:
        raise RuntimeError('Unexpected payload launcher layout')
    return outer


def descendants(disk):
    yield disk
    for child in disk.get('children', []):
        yield from descendants(child)


def validate_selection(names, wipe_names, topology, media_names, pools, swaps):
    """Pure policy check, independently exercised without block-device access."""
    if wipe_names:
        raise RuntimeError('An unselected disk contains another boot-pool. Shut down and '
                           'disconnect the previous OS disk; this installer will not erase it.')
    if not names or len(names) != len(set(names)):
        raise RuntimeError('Choose at least one distinct destination')
    if not media_names:
        raise RuntimeError('Could not identify the installer source disk')
    if pools:
        raise RuntimeError('Existing ZFS pools are imported; export them before installation')
    identities = []
    for name in names:
        if not re.fullmatch(r'[A-Za-z0-9_-]+', name):
            raise RuntimeError('Invalid disk name')
        matches = [d for d in topology if d.get('kname') == name]
        if len(matches) != 1:
            raise RuntimeError('Destination is no longer present')
        disk = matches[0]
        if disk.get('type') != 'disk' or disk.get('ro') or int(disk['size']) < 8_000_000_000:
            raise RuntimeError('Destination is read-only, too small, or not a whole disk')
        if name in media_names:
            raise RuntimeError('Cannot install over the running installer USB')
        for node in descendants(disk):
            if any(node.get('mountpoints') or []) or '/dev/' + node['kname'] in swaps:
                raise RuntimeError('Destination or a child partition is mounted or active swap')
            if node.get('holders'):
                raise RuntimeError('Destination is held by another block device')
        identities.append({k: disk.get(k) for k in ('kname', 'size', 'model', 'serial')})
    return identities


def selection_guard(disks, wipe_disks):
    topology = json.loads(run(['lsblk', '-b', '-J', '-o',
                              'NAME,KNAME,SIZE,MODEL,SERIAL,TYPE,RO,MOUNTPOINTS'], text=True).stdout)['blockdevices']
    for disk in topology:
        for node in descendants(disk):
            holders = Path('/sys/class/block') / node['kname'] / 'holders'
            node['holders'] = [p.name for p in holders.iterdir()] if holders.exists() else []
    source = run(['findmnt', '-n', '-o', 'SOURCE', '/cdrom'], text=True).stdout.strip()
    if not source.startswith('/dev/'):
        raise RuntimeError('Installer source is not an identifiable block device')
    media = run(['lsblk', '-s', '-n', '-o', 'KNAME', source], text=True).stdout.split()
    pools = run(['zpool', 'list', '-H', '-o', 'name'], text=True).stdout.split()
    swaps = {line.split()[0] for line in Path('/proc/swaps').read_text().splitlines()[1:]}
    result = validate_selection([d.name for d in disks], [d.name for d in wipe_disks],
                                topology, set(media), pools, swaps)
    for disk, identity in zip(disks, result):
        if disk.size != identity['size']:
            raise RuntimeError('Destination size changed since selection')
    return result


async def install(disks, wipe_disks, set_pmbr, authentication, post_install, sql, callback):
    from truenas_installer.exception import InstallError
    try:
        live_guard()
        outer = source_preflight()
        identities = selection_guard(disks, wipe_disks)
        replaced = outer.replace(LAUNCH, f'"python3", {str(BASE / "compat.py")!r}, "--payload",')
        module = types.ModuleType('truenas_installer.efi32_vendor')
        module.__package__ = 'truenas_installer'
        exec(compile(replaced, 'install_vendor.py', 'exec'), module.__dict__)
        # All sensitive authentication parameters remain in the vendor stdin flow.
        with tempfile.TemporaryDirectory(prefix='efi32-approved-', dir='/run') as directory:
            state = Path(directory) / 'selection.json'
            state.write_text(json.dumps(identities))
            state.chmod(0o600)
            previous = os.environ.get('EFI32_SELECTION')
            os.environ['EFI32_SELECTION'] = str(state)
            try:
                # Recheck source/media/destinations immediately before vendor formatting.
                if selection_guard(disks, wipe_disks) != identities:
                    raise RuntimeError('Destination identity changed')
                await module.install(disks, [], set_pmbr, authentication, post_install,
                                     (sql or '') + '\n' + NOEFI_SQL, callback)
            finally:
                if previous is None:
                    os.environ.pop('EFI32_SELECTION', None)
                else:
                    os.environ['EFI32_SELECTION'] = previous
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        raise InstallError(str(error)) from error


def install_ia32(root):
    """Called only after the vendor mounted the selected disk ESP at root/boot/efi."""
    esp = Path(root) / 'boot/efi'
    if not os.path.ismount(esp):
        raise RuntimeError('Target ESP is not mounted')
    grub = Path(root) / 'boot/grub'
    uuid = run(['chroot', root, 'grub-probe', '-t', 'fs_uuid', '/boot/grub'], text=True).stdout.strip()
    relative = run(['chroot', root, 'grub-mkrelpath', '/boot/grub/grub.cfg'], text=True).stdout.strip()
    if not re.fullmatch(r'[0-9a-fA-F-]+', uuid) or not re.fullmatch(r'/[A-Za-z0-9_./@+-]+', relative):
        raise RuntimeError('Unexpected GRUB filesystem UUID or config path')
    if not (grub / 'grub.cfg').is_file():
        raise RuntimeError('Installed GRUB menu is missing')
    # Matching GRUB 2.14 IA32 modules avoid mixing vendor x64/PC modules with this core.
    shutil.copytree(BASE / 'i386-efi', grub / 'i386-efi', dirs_exist_ok=True)
    target = esp / 'EFI/BOOT'
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(BASE / 'installed-BOOTIA32.EFI', target / 'BOOTIA32.EFI')
    cfg = (f'insmod zfs\nsearch --no-floppy --fs-uuid --set=bootpool {uuid}\n'
           f'set root=$bootpool\nset prefix=($bootpool){relative.rsplit("/", 1)[0]}\n'
           f'configfile ($bootpool){relative}\n')
    (target / 'efi32.cfg').write_text(cfg)
    run(['chroot', root, 'grub-script-check', '/boot/efi/EFI/BOOT/efi32.cfg'])
    (esp / 'EFI/BOOT/efi32-install.json').write_text(json.dumps({
        'loader': 'GRUB IA32 2.14', 'boot_pool_uuid': uuid, 'menu_path': relative,
        'uses_installed_kernel_and_initrd': True}, indent=2) + '\n')
    run(['sync', '-f', str(target)])


def payload_mode():
    live_guard()
    state = Path(os.environ.get('EFI32_SELECTION', '/nonexistent'))
    if not state.is_file() or not str(state).startswith('/run/efi32-approved-'):
        raise RuntimeError('Missing parent installation selection')
    identities = json.loads(state.read_text())
    raw = sys.stdin.read()
    params = json.loads(raw)
    if (params.get('disks') != [d['kname'] for d in identities] or
            params.get('pool_name') != 'boot-pool' or params.get('old_root') is not None):
        raise RuntimeError('Unexpected payload destination or upgrade request')
    for disk in identities:
        current = json.loads(run(['lsblk', '-b', '-J', '-d', '-o', 'KNAME,SIZE,MODEL,SERIAL',
                                  '/dev/' + disk['kname']], text=True).stdout)['blockdevices']
        if len(current) != 1 or current[0] != disk:
            raise RuntimeError('Destination identity changed after formatting')
    source = Path.cwd() / 'truenas_install/__main__.py'
    patched = patch_payload(pinned(source.read_bytes(), PAYLOAD_SHA))
    sys.path.insert(0, str(BASE))
    sys.modules['efi32_compat'] = sys.modules[__name__]
    sys.path.insert(0, str(Path.cwd()))
    sys.stdin = io.StringIO(raw)
    exec(compile(patched, str(source), 'exec'), {'__name__': '__main__',
         '__package__': 'truenas_install', '__file__': str(source)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--payload', action='store_true', required=True)
    parser.parse_args()
    payload_mode()
