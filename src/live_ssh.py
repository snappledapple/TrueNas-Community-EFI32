"""Opt-in, per-boot SSH. Image contains no authorized keys or passwords."""
from pathlib import Path
import argparse
import json
import os
import re
import secrets
import shutil
import subprocess
import sys

sys.path.insert(0, '/usr/local/lib/efi32-installer')
from compat import live_guard

RUNTIME = Path('/run/efi32-ssh')


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs).stdout.strip()


def active():
    return subprocess.run(['systemctl', 'is-active', '--quiet', 'efi32-live-ssh.service']).returncode == 0


def stop():
    saved = RUNTIME / 'original-root-hash'
    if saved.exists():
        run(['chpasswd', '-e'], input='root:' + saved.read_text().strip() + '\n')
    # Restore before stopping: a caller inside an SSH session may be killed with
    # the service's process group. Console callers also remove all runtime files.
    subprocess.run(['systemctl', 'stop', 'efi32-live-ssh.service'], check=False, capture_output=True)
    if RUNTIME.exists():
        shutil.rmtree(RUNTIME)


def enable(public_key=None):
    live_guard()
    if active():
        raise RuntimeError('SSH is already enabled. Disable it before changing access.')
    stop()
    RUNTIME.mkdir(mode=0o700)
    public_key = public_key.strip() if public_key else None
    if public_key:
        if '\n' in public_key or not re.fullmatch(r'(ssh-ed25519|ecdsa-sha2-nistp256|ssh-rsa) [A-Za-z0-9+/=]+(?: [^\r\n]*)?', public_key):
            raise RuntimeError('Enter one OpenSSH public key without key options')
        (RUNTIME / 'authorized_keys').write_text('restrict,pty ' + public_key + '\n')
        (RUNTIME / 'authorized_keys').chmod(0o600)
        run(['ssh-keygen', '-l', '-f', str(RUNTIME / 'authorized_keys')])
    host_key = RUNTIME / 'host_ed25519'
    run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '', '-f', str(host_key)])
    Path('/run/sshd').mkdir(mode=0o755, exist_ok=True)
    config = RUNTIME / 'sshd_config'
    config.write_text(f'''Port 2222
AddressFamily inet
HostKey {host_key}
PidFile {RUNTIME}/sshd.pid
AuthorizedKeysFile {RUNTIME}/authorized_keys
PermitRootLogin {'prohibit-password' if public_key else 'yes'}
AllowUsers root
AuthenticationMethods {'publickey' if public_key else 'password'}
PubkeyAuthentication {'yes' if public_key else 'no'}
PasswordAuthentication {'no' if public_key else 'yes'}
KbdInteractiveAuthentication no
PermitEmptyPasswords no
UsePAM yes
StrictModes yes
UseDNS no
DisableForwarding yes
PermitUserRC no
PermitTunnel no
PrintMotd no
MaxAuthTries 3
LoginGraceTime 30
MaxStartups 3:50:6
LogLevel INFO
Subsystem sftp internal-sftp
''')
    config.chmod(0o600)
    original = next(line.split(':')[1] for line in Path('/etc/shadow').read_text().splitlines()
                    if line.startswith('root:'))
    saved = RUNTIME / 'original-root-hash'
    saved.write_text(original)
    saved.chmod(0o600)
    # Avoid distro-dependent rejection of locked root accounts in key mode too.
    # Key mode still disables all SSH password authentication; discard this secret.
    temporary = secrets.token_urlsafe(24)
    run(['chpasswd'], input=f'root:{temporary}\n')
    password = None if public_key else temporary
    try:
        run(['/usr/sbin/sshd', '-t', '-f', str(config)])
        run(['systemd-run', '--unit=efi32-live-ssh', '--collect', '--property=Type=exec',
             '/usr/sbin/sshd', '-D', '-e', '-f', str(config)])
        if not active():
            raise RuntimeError('SSH service did not stay active')
    except Exception:
        stop()
        raise
    info = {'user': 'root', 'port': 2222,
            'addresses': run(['hostname', '-I']).split(),
            'fingerprint': run(['ssh-keygen', '-l', '-E', 'sha256', '-f', str(host_key) + '.pub']),
            'temporary_password': password,
            'expires': 'Disable SSH or reboot. Nothing is installed into TrueNAS.'}
    return info


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['password', 'key', 'off'])
    args = parser.parse_args()
    live_guard()
    if args.action == 'off':
        stop()
        print('Temporary SSH disabled.')
    elif args.action == 'key':
        key = sys.stdin.read().strip()
        if not key:
            raise SystemExit('A public key is required')
        print(json.dumps(enable(key), indent=2))
    else:
        if not sys.stdin.isatty():
            raise SystemExit('Password activation requires the local console')
        print(json.dumps(enable(), indent=2))
