"""Tools for managing/keeping track of `stginga` plugins."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from ginga.misc.Bunch import Bunch

__all__ = ['load_plugins']

def load_plugins(ginga):
    """
    Loads the stginga plugins
    """
    stglobal_plugins, stlocal_plugins = _get_stginga_plugins()
    for gplg in stglobal_plugins:
        ginga.add_global_plugin(gplg)
    for lplg in stlocal_plugins:
        ginga.add_local_plugin(lplg)


def _get_stginga_plugins():
    gpfx = 'stginga.qtw.plugins'  # To load custom Qt plugins in Ginga namespace

    global_plugins = []
    local_plugins = [Bunch(module='BackgroundSub', tab='BackgroundSub', ws='dialogs', pfx=gpfx),
                     Bunch(module='DQInspect', tab='DQInspect', ws='dialogs', pfx=gpfx)]
    return global_plugins, local_plugins
