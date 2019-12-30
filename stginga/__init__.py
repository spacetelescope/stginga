# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""
Ginga products specific to STScI data analysis.
"""

# Set up the version
from pkg_resources import get_distribution, DistributionNotFound

try:
    __version__ = get_distribution(__name__).version
except DistributionNotFound:
    # package is not installed
    __version__ = 'unknown'

# UI
from .plugin_info import *  # noqa
