"""Local console pairing; the generated password is never logged."""
import sys
sys.path.insert(0, '/usr/local/lib/efi32-installer')
from live_ssh import enable, stop
from .dialog import dialog_menu, dialog_msgbox, dialog_yesno


async def temporary_ssh(self):
    async def start_password():
        if not await dialog_yesno('Temporary SSH access',
                'Enable root SSH on port 2222 for this live boot?\n'
                'A new random password and host key are generated in RAM.\n'
                'Only enable this on a network you trust.'):
            return
        try:
            info = enable()
            message = (f"User: {info['user']}   Port: {info['port']}\n"
                       f"Addresses: {' '.join(info['addresses'])}\n"
                       f"Temporary password: {info['temporary_password']}\n"
                       f"Host key: {info['fingerprint']}\n\n"
                       'Reboot or Disable SSH to remove access.\n'
                       'This password does not become the installed admin password.')
            await dialog_msgbox('SSH enabled for this boot', message)
        except Exception as error:
            await dialog_msgbox('SSH setup failed', str(error))

    async def disable():
        stop()
        await dialog_msgbox('Temporary SSH', 'SSH disabled; temporary credentials removed.')

    await dialog_menu('Temporary installer SSH', {
        'Enable SSH with a new temporary password': start_password,
        'Disable SSH': disable,
    })
    await self._main_menu()
