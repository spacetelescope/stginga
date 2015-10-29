
"""
Running Ginga With STGinga Plugins
----------------------------------

``stginga`` includes additional plugins to beyond those provided by `ginga`
itself that add functionality.  There are a few different ways to start
ginga in a way that will make it recognize those plugins.


The ``stginga`` script
^^^^^^^^^^^^^^^^^^^^^^

The simplest way is to simple use a script packaged with ``stginga`` that knows
to preload the STScI plugins.  Note that this currently only works when ginga
is run with the qt backend::

    stginga [args]

The accepted command line arguments are the same as for standard ginga,
with the following exceptions:

* There is no need to use ``--plugins`` and ``--modules`` to load STScI plugins.
* Toolkit (``--toolkit`` or ``-t``) is always set to Qt.


Change Local Configuration to Always Load ``stginga``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you wish to have the ``stginga`` plugins *always* loaded when you
start ginga, you can set your local configuration to do this autmatically.

The key is to use ``ginga``'s builtin configuration machinery.  Create a
``$HOME/.ginga/ginga_config.py`` file with the following contents::

    def post_gui_config(ginga):
        from stginga import load_plugins
        load_plugins(ginga)

Then you can run Ginga natively as follows::

    ginga [args]

Depending on how your system is setup, you might need to specify the toolkit,
because ``stginga`` plugins are currently only available for QT::

    ginga --toolkit=qt [args]


Manually load ``stginga`` plugins
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can also run Ginga natively and just specify the plugins you want directly::

    ginga --plugins=stginga.plugins.BackgroundSub,stginga.plugins.DQInspect [args]

"""

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from ginga.misc.Bunch import Bunch

__all__ = ['load_plugins', 'show_plugin_install_info']

def load_plugins(ginga):
    """
    Loads the stginga plugins.

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
    gpfx = 'stginga.plugins'  # To load custom Qt plugins in Ginga namespace

    global_plugins = []
    local_plugins = [Bunch(module='BackgroundSub', ws='dialogs', pfx=gpfx),
                     Bunch(module='DQInspect', ws='dialogs', pfx=gpfx)]
    return global_plugins, local_plugins


def show_plugin_install_info():
    """
    Prints the documentation on how to install the ginga plugins.
    """
    print(__doc__)
