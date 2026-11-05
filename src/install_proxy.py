"""Keep the normal vendor UI; guard every installation entry point."""
import sys
sys.path.insert(0, '/usr/local/lib/efi32-installer')
from compat import install
from .exception import InstallError
__all__ = ['install', 'InstallError']
