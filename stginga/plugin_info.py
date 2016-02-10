"""This module contains functions to handle ``stginga`` plugins.
See :ref:`stginga-run`.

"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

# STDLIB
import warnings

# THIRD-PARTY
from astropy.utils.exceptions import AstropyUserWarning

# GINGA
from ginga import __version__ as ginga_version
from ginga.misc.Bunch import Bunch

__all__ = ['load_plugins', 'show_plugin_install_info']


def load_plugins(ginga):
    """Load the ``stginga`` plugins.
    This also automatically starts necessary core Ginga global plugins.

    Parameters
    ----------
    ginga
        The ginga app object that is provided to ``post_gui_config`` in
        ``ginga_config.py``.

    """
    stglobal_plugins, stlocal_plugins = _get_stginga_plugins()

    # Add custom global plugins
    for gplg in stglobal_plugins:
        if gplg['module'] in ginga.global_plugins:
            ginga.logger.info('Plugin {0} already loaded in Ginga.  Not adding '
                              'again.'.format(gplg['module']))
        else:
            ginga.add_global_plugin(gplg)

    # Add custom local plugins
    for lplg in stlocal_plugins:
        if lplg['module'] in ginga.local_plugins:
            ginga.logger.info('Plugin {0} already loaded in Ginga.  Not adding '
                              'again.'.format(lplg['module']))
        else:
            ginga.add_local_plugin(lplg)

    # Auto start core global plugins
    for gplg in ('ChangeHistory', ):
        ginga.start_global_plugin(gplg)


def _get_stginga_plugins():
    # TODO: When we use stable Ginga release, not the dev, we can remove this
    # and just have version check in setup.py
    if ginga_version < '2.5.20160128021834':
        warnings.warn('Your Ginga version {0} is old, stginga might not work '
                      'properly'.format(ginga_version), AstropyUserWarning)

    gpfx = 'stginga.plugins'  # To load custom plugins in Ginga namespace

    global_plugins = []
    local_plugins = [
        Bunch(module='MultiImage', ws='dialogs', pfx=gpfx),
        Bunch(module='MIPick', ws='dialogs', pfx=gpfx),
        Bunch(module='BackgroundSub', ws='dialogs', pfx=gpfx),
        Bunch(module='BadPixCorr', ws='dialogs', pfx=gpfx),
        Bunch(module='DQInspect', ws='dialogs', pfx=gpfx),
        Bunch(module='SNRCalc', ws='dialogs', pfx=gpfx),
        Bunch(module='SaveImage', ws='dialogs', pfx=gpfx)
        ]
    return global_plugins, local_plugins


def show_plugin_install_info():
    """Print the documentation on how to install the ginga plugins."""
    print('See http://stginga.readthedocs.org/en/latest/run.html')
