# Licensed under a 3-clause BSD style license - see LICENSE.rst
import os

from astropy.tests.runner import TestRunner

try:
    from .version import version as __version__
except ImportError:
    __version__ = 'unknown'
__vdate__ = '2019-12-29'

# Create the test function for self test
test = TestRunner.make_test_runner_in(os.path.dirname(__file__))
test.__test__ = False

__all__ = ['__version__', 'test']
