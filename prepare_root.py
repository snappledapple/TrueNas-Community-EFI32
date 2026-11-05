"""Apply inspected additions to an extracted live root, never an installed OS."""
from pathlib import Path
import hashlib
import shutil
import sys

source = Path(__file__).parent
root = Path(sys.argv[1]).resolve()
if not (root / 'usr/lib/python3/dist-packages/truenas_installer/install.py').is_file():
    raise SystemExit('Expected extracted live root')
package = root / 'usr/lib/python3/dist-packages/truenas_installer'
original = (package / 'install.py').read_bytes()
if hashlib.sha256(original).hexdigest() != 'bb9f07d3ada5b2117eb8d917e5775afed17c0ab62977b7a942465ddfcdeb8446':
    raise SystemExit('Outer installer changed; refusing remaster')
(package / 'install_vendor.py').write_bytes(original)
(package / 'install.py').write_bytes((source / 'src/install_proxy.py').read_bytes())
dest = root / 'usr/local/lib/efi32-installer'
dest.mkdir(parents=True, exist_ok=True)
for name in ('compat.py', 'live_ssh.py'):
    shutil.copyfile(source / 'src' / name, dest / name)
shutil.copyfile(source / 'src/ssh_menu.py', package / 'ssh_menu.py')
menu = (package / 'installer_menu.py').read_text()
needle = '                "Shell": self._shell,'
if menu.count(needle) != 1:
    raise SystemExit('Unexpected console menu')
menu = menu.replace(needle, '                "Temporary SSH": self._temporary_ssh,\n' + needle)
# Stop before the stock UI can offer erasing an unrelated boot-pool disk.
start = menu.index('            if wipe_disks:\n')
end = menu.index('\n            break\n', start)
menu = menu[:start] + '''            if wipe_disks:
                await dialog_msgbox("Previous TrueNAS OS disk detected",
                    "Disconnect the unselected previous OS disk(s): " + ", ".join(wipe_disks) +
                    "\\nThen boot this installer again. Those disks will not be erased.")
                return False
''' + menu[end:]
menu += '\nfrom .ssh_menu import temporary_ssh\nInstallerMenu._temporary_ssh = temporary_ssh\n'
compile(menu, 'installer_menu.py', 'exec')
(package / 'installer_menu.py').write_text(menu)
# No server-mode installer RPC on the LAN; the console or explicitly enabled SSH is enough.
wants = root / 'etc/systemd/system/multi-user.target.wants/truenas-installer.service'
if wants.is_symlink():
    wants.unlink()
for service in ('ssh.service', 'ssh.socket', 'sshd.service', 'truenas-installer.service'):
    link = root / 'etc/systemd/system' / service
    if link.exists() or link.is_symlink():
        link.unlink()
    link.symlink_to('/dev/null')
# Host identity is created on each live boot, never published in the filesystem.
for path in (root / 'etc/ssh').glob('ssh_host_*'):
    path.unlink()
for name in ('etc/machine-id', 'var/lib/dbus/machine-id'):
    path = root / name
    if path.is_symlink():
        path.unlink()
    path.write_bytes(b'')
for folder in ('root/.ssh', 'root/.bash_history'):
    path = root / folder
    if path.is_dir():
        shutil.rmtree(path)
    elif path.is_file():
        path.unlink()
# Package logs can contain build-time SSH fingerprints/container hostnames.
# Keep the directory structure, but publish no build-session logs or random seed.
for path in (root / 'var/log').rglob('*'):
    if path.is_file() and not path.is_symlink():
        path.write_bytes(b'')
for name in ('etc/hostid', 'var/lib/systemd/random-seed'):
    path = root / name
    if path.is_file() or path.is_symlink():
        path.unlink()
cli = root / 'usr/local/bin/efi32-ssh'
cli.write_text('#!/bin/sh\nexec python3 /usr/local/lib/efi32-installer/live_ssh.py "$@"\n')
cli.chmod(0o755)
shutil.copytree(source / 'assets/i386-efi', dest / 'i386-efi')
shutil.copyfile(source / 'assets/installed-BOOTIA32.EFI', dest / 'installed-BOOTIA32.EFI')
print('Generic live root prepared. SSH disabled until explicitly paired.')
