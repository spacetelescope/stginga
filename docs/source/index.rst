.. stginga documentation master file, created by
   sphinx-quickstart on Mon Oct 19 17:08:24 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

``stginga``: Ginga for STScI
============================

``stginga`` is a package that customizes
`Ginga <https://ginga.readthedocs.org/en/latest/>`_ in order to aid data
analysis for the data supported by STScI (e.g., HST or JWST).


Installation
------------

``stginga`` requires:

* `Anaconda <https://www.continuum.io/downloads>`_ for Python 2.7.
* Astropy 1.1 or later, available from
  `Astropy's GitHub page <https://github.com/astropy/astropy>`_.
* The latest version of Ginga, available from
  `Ginga's GitHub page <https://github.com/ejeschke/ginga/>`_.
* The latest version of ``stginga`` available from
  `stginga's GitHub page <https://github.com/spacetelescope/stginga>`_.

To install ``stginga`` from source::

    python setup.py install [--prefix=/my/install/path]


Configuration Files
-------------------

To use STScI recommended settings, copy the ``*.cfg`` files from
``stginga/ginga/examples/configs`` to your ``$HOME/.ginga`` directory.
If you already have existing Ginga configuration files, it is recommended that
you **back up your existing Ginga configurations** before copying the files
over. You can further customize Ginga according to your own preferences
afterwards by modifying them manually.


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

    def pre_gui_config(ginga):
        pass

    def post_gui_config(ginga):
        from ginga.misc.Bunch import Bunch

        # Prefix for custom plugins
        qtpfx = 'stginga.qtw.plugins'  # Qt

        # Add STScI local plugins (Qt)
        ginga.add_local_plugin(
            Bunch(module='BackgroundSub', ws='dialogs', pfx=qtpfx))
        ginga.add_local_plugin(
            Bunch(module='DQInspect', ws='dialogs', pfx=qtpfx))

Then you can run Ginga natively as follows::

    ginga --toolkit=qt [args]


Manually Load the ``stginga`` pluins
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can also run Ginga natively and just specify the plugins directly::

    ginga --toolkit=qt --plugins=stginga.qtw.plugins.BackgroundSub,stginga.qtw.plugins.DQInspect [args]


Using ``stginga``
-----------------

.. toctree::
   :maxdepth: 2

   ref_api


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

