"""This module contains functions to handle ``stginga`` plugins.
See :ref:`stginga-run`.

"""
# GINGA
from ginga.misc.Bunch import Bunch

__all__ = ['load_plugins', 'show_plugin_install_info']


def load_plugins(ginga):
    """Load the ``stginga`` plugins.

    Parameters
    ----------
    ginga
        The ginga app object that is provided to ``pre_gui_config`` in
        ``ginga_config.py``.

    """
    stglobal_plugins, stlocal_plugins = _get_stginga_plugins()

    # Add custom global plugins
    for gplg in stglobal_plugins:
        if gplg['module'] in ginga.global_plugins:
            ginga.logger.info(f'Plugin {gplg["module"]} already loaded in '
                              'Ginga. Not adding again.')
        else:
            ginga.add_global_plugin(gplg)

    # Add custom local plugins
    for lplg in stlocal_plugins:
        if lplg['module'] in ginga.local_plugins:
            ginga.logger.info(f'Plugin {lplg["module"]} already loaded in '
                              'Ginga. Not adding again.')
        else:
            ginga.add_local_plugin(lplg)


def _get_stginga_plugins():
    gpfx = 'stginga.plugins'  # To load custom plugins in Ginga namespace

    global_plugins = []
    local_plugins = [
        Bunch(module='BackgroundSub', workspace='dialogs', pfx=gpfx,
              category='Custom', ptype='local'),
        Bunch(module='BadPixCorr', workspace='dialogs', pfx=gpfx,
              category='Custom', ptype='local'),
        Bunch(module='DQInspect', workspace='dialogs', pfx=gpfx,
              category='Custom', ptype='local'),
        Bunch(module='SNRCalc', workspace='dialogs', pfx=gpfx,
              category='Custom', ptype='local'),
        ]
    return global_plugins, local_plugins


def show_plugin_install_info():
    """Print the documentation on how to install the ginga plugins."""
    print('See https://stginga.readthedocs.io/en/latest/stginga/run.html')
