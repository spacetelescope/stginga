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


Running Ginga
-------------


The Easy Way
^^^^^^^^^^^^

To start Ginga with STScI plugins preloaded (currently available in Qt only)::

    runstginga [args]

The accepted command line arguments are the same as Ginga, with the following
exceptions:

* There is no need to use ``--plugins`` and ``--modules`` to load STScI plugins.
* Toolkit (``--toolkit`` or ``-t``) is always set to Qt.


The Hard Way (1)
^^^^^^^^^^^^^^^^

Alternately, you can create a ``$HOME/.ginga/ginga_config.py`` file with the
following contents::

    def pre_gui_config(ginga):
        pass

    def post_gui_config(ginga):
        from ginga.misc.Bunch import Bunch

        # Prefix for custom plugins
        qtpfx = 'ginga.qtw.plugins'  # Qt

        # Add STScI local plugins (Qt)
        ginga.add_local_plugin(
            Bunch(module='BackgroundSub', ws='dialogs', pfx=qtpfx))
        ginga.add_local_plugin(
            Bunch(module='DQInspect', ws='dialogs', pfx=qtpfx))

Then you can run Ginga natively as follows::

    ginga --toolkit=qt [args]


The Hard Way (2)
^^^^^^^^^^^^^^^^

You can also run Ginga natively without ``ginga_config.py`` as follows::

    ginga --toolkit=qt --plugins=ginga.qtw.plugins.BackgroundSub,ginga.qtw.plugins.DQInspect [args]


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

