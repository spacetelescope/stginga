"""This module contains functions to handle ``stginga`` plugins.
See :ref:`stginga-run`.

"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from ginga.misc.Bunch import Bunch

__all__ = ['load_plugins', 'show_plugin_install_info']


def load_plugins(ginga):
    """Load the ``stginga`` plugins.

    Parameters
    ----------
    ginga
        The ginga app object that is provided to ``post_gui_config`` in
        ``ginga_config.py``.

    """
    stglobal_plugins, stlocal_plugins = _get_stginga_plugins()
    for gplg in stglobal_plugins:
        if gplg['module'] in ginga.global_plugins:
            ginga.logger.info('Plugin {0} already loaded in Ginga.  Not adding '
                              'again.'.format(gplg['module']))
        else:
            ginga.add_global_plugin(gplg)
    for lplg in stlocal_plugins:
        if lplg['module'] in ginga.local_plugins:
            ginga.logger.info('Plugin {0} already loaded in Ginga.  Not adding '
                              'again.'.format(lplg['module']))
        else:
            ginga.add_local_plugin(lplg)


def _get_stginga_plugins():
    gpfx = 'stginga.plugins'  # To load custom plugins in Ginga namespace

    global_plugins = [
        Bunch(module='ChangeHistory', tab='History', ws='right', pfx=gpfx,
              start=True),
        ]
    local_plugins = [
        Bunch(module='BackgroundSub', ws='dialogs', pfx=gpfx),
        Bunch(module='DQInspect', ws='dialogs', pfx=gpfx),
        Bunch(module='MultiImage', ws='dialogs', pfx=gpfx),
        Bunch(module='MIPick', ws='dialogs', pfx=gpfx),
        Bunch(module='SNRCalc', ws='dialogs', pfx=gpfx),
        ]
    return global_plugins, local_plugins


def show_plugin_install_info():
    """Print the documentation on how to install the ginga plugins."""
    print('See http://stginga.readthedocs.org/en/latest/run.html')
