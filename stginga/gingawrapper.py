"""Wrapper script to run Ginga optimized for STScI data."""

# STDLIB
import sys

# GINGA
from ginga.rv import main as gmain

# Suppress logging "no handlers" message from Ginga
import logging
logging.raiseExceptions = False

__all__ = ['run_stginga']


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
    plg_to_remove = []
    _remove_plugins(plg_to_remove, gmain.plugins)

    # Add custom plugins.
    # If we use this, we do not have to use ginga_config.py
    stglobal_plugins, stlocal_plugins = _get_stginga_plugins()
    gmain.plugins += stglobal_plugins
    gmain.plugins += stlocal_plugins

    # Enforce Qt (--toolkit or -t) -- DISABLED
    # new_argv = ['--toolkit=qt' if 'toolkit' in s else s for s in sys_argv]
    # if '-t' in new_argv:
    #     new_argv[new_argv.index('-t') + 1] = 'qt'

    # Auto start core global plugins
    for gplgname in ('ChangeHistory', ):
        gplg = _locate_plugin(gmain.plugins, gplgname)
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


if __name__ == '__main__':
    """Run from command line."""
    run_stginga(sys.argv)
