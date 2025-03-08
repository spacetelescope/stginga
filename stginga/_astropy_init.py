# Licensed under a 3-clause BSD style license - see LICENSE.rst
try:
    from .version import version as __version__
except ImportError:
    __version__ = 'unknown'
__vdate__ = '2019-12-29'

__all__ = ['__version__']
