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


.. automodule:: stginga.plugin_info


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

