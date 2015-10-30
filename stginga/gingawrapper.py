"""Wrapper script to run Ginga optimized for STScI data."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

# STDLIB
import sys

# GINGA
from ginga import main as gmain
from ginga.misc.Bunch import Bunch

# Suppress logging "no handlers" message from Ginga
import logging
logging.raiseExceptions = False

__all__ = ['run_stginga']

# Manage the default layout. Yes, OMG, hacky hacky
gmain.default_layout = ['seq', {},
                        ['vbox', dict(name='top', width=1520, height=900),
                         dict(row=['hbox', dict(name='menu')],
                              stretch=0),
                         dict(row=['hpanel', dict(name='hpnl'),
                                   ['ws', dict(name='left', width=300, group=2),
                                    # (tabname, layout), ...
                                    [("Info", ['vpanel', {},
                                               ['ws', dict(name='uleft', height=300,
                                                           show_tabs=False, group=3)],
                                               ['ws', dict(name='lleft', height=430,
                                                           show_tabs=True, group=3)],
                                    ]
                                    )]],
                                   ['vbox', dict(name='main', width=700),
                                    dict(row=['ws', dict(wstype='tabs', name='channels',
                                                         group=1)], stretch=1)],
                                   ['ws', dict(name='right', width=430, group=2),
                                    # (tabname, layout), ...
                                    [("Dialogs", ['ws', dict(name='dialogs', group=2)
                                    ]
                                    )]
                                   ],
                         ], stretch=1),
                         dict(row=['ws', dict(name='toolbar', height=40,
                                              show_tabs=False, group=2)],
                              stretch=0),
                         dict(row=['hbox', dict(name='pstamps')]),
                         dict(row=['hbox', dict(name='status')], stretch=0),
                        ]]


def run_stginga(sys_argv):
    """Run this from command line.

    This does the following:

    * Set up custom STScI plugins.
    * Enforce Qt toolkit.
    * Pass command line arguments directly into Ginga.

    .. warning::

        If the same plugin that is loaded here is also loaded
        via ``~/.ginga/ginga_config.py`` or command line,
        you will see duplicates!

    """
    from .plugin_info import _get_stginga_plugins

    # Remove some Ginga default plugins.
    # Use this if we have custom plugins that replaces them.
    # Note: Unable to get this to work from within ginga_config.py
    # Example:
    #     glb_plg_to_remove = ['WBrowser', 'RC', 'SAMP', 'IRAF']
    glb_plg_to_remove = []
    lcl_plg_to_remove = []
    _remove_plugins(glb_plg_to_remove, gmain.global_plugins)
    _remove_plugins(lcl_plg_to_remove, gmain.local_plugins)

    # Add custom plugins.
    # If we use this, we do not have to use ginga_config.py
    stglobal_plugins, stlocal_plugins = _get_stginga_plugins()
    gmain.global_plugins += stglobal_plugins
    gmain.local_plugins += stlocal_plugins

    # Enforce Qt (--toolkit or -t)
    new_argv = ['--toolkit=qt' if 'toolkit' in s else s for s in sys_argv]
    if '-t' in new_argv:
        new_argv[new_argv.index('-t') + 1] = 'qt'

    # Start Ginga
    gmain.reference_viewer(new_argv)


def _locate_plugin(plist, name):
    """Locate a default global plugin for Ginga."""
    result = None
    for plg in plist:
        if plg.module == name:
            result = plg
            break
    return result


def _remove_plugins(rmlist, plist):
    """Remove default global or local plugin(s) from Ginga."""
    for plgname in rmlist:
        plg = _locate_plugin(plist, plgname)
        plist.remove(plg)


if __name__ == '__main__':
    run_stginga(sys.argv)
