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
gmain.default_layout = ['seq', {}, [
    'vbox',  {'name': 'top', 'width': 1520, 'height': 900},
    {'row': ['hbox', {'name': 'menu'}], 'stretch': 0},
    {'row': [
        'vpanel', {}, [
            'vbox', {},
            {'row': [
                'hpanel', {'name': 'hpnl'}, [
                    'ws', {'name': 'left', 'width': 300, 'group': 2}, [
                        ('Info', [
                            'vpanel', {}, [
                                'ws', {'name': 'uleft', 'height': 300,
                                       'show_tabs': False, 'group': 3}
                            ],
                            [
                                'ws', {'name': 'lleft', 'height': 430,
                                       'show_tabs': True, 'group': 3}
                            ]
                        ])
                    ]
                ],
                [
                    'vbox', {'name': 'main', 'width': 700},
                    {'row': [
                        'ws', {'wstype': 'tabs', 'name': 'channels',
                               'group': 1}
                    ],
                     'stretch': 1
                    },
                    {'row': [
                        'ws', {'wstype': 'stack', 'name': 'cbar',
                               'group': 99}
                    ],
                     'stretch': 0
                    },
                    {'row': [
                        'ws', {'wstype': 'stack', 'name': 'readout',
                               'group': 99}
                    ],
                     'stretch': 0
                    },
                    {'row': [
                        'ws', {'wstype': 'stack', 'name': 'operations',
                               'group': 99}
                    ],
                     'stretch': 0
                    }
                ],
                [
                    'ws', {'name': 'right', 'width': 430, 'group': 2}, [
                        ('Dialogs', [
                            'ws', {'name': 'dialogs', 'group': 2}
                        ])
                    ]
                ]
            ],
             'stretch': 1}, [
                 'ws', {'name': 'toolbar', 'height': 40,
                        'show_tabs': False, 'group': 2}
             ]
        ],
        [
            'hbox', {'name': 'pstamps'}
        ],
    ]},
    {'row': [
        'hbox', {'name': 'status'}
    ],
     'stretch': 0
    }
]]


def run_stginga(sys_argv):
    """Run this from command line.

    This does the following:

    * Set up custom STScI plugins.
    * Automatically starts necessary core Ginga global plugins.
    * Pass command line arguments directly into Ginga.

    .. warning::

        If the same plugin that is loaded here is also loaded
        via ``~/.ginga/ginga_config.py`` or command line,
        you might see duplicates!

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

    # Enforce Qt (--toolkit or -t) -- DISABLED
    #new_argv = ['--toolkit=qt' if 'toolkit' in s else s for s in sys_argv]
    #if '-t' in new_argv:
    #    new_argv[new_argv.index('-t') + 1] = 'qt'

    # Auto start core global plugins
    for gplgname in ('ChangeHistory', ):
        gplg = _locate_plugin(gmain.global_plugins, gplgname)
        gplg.start = True

    # Start Ginga
    gmain.reference_viewer(sys_argv)


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


def _main():
    """Run from command line."""
    run_stginga(sys.argv)


if __name__ == '__main__':
    _main()
