.. _stginga-plugins:

Plugins
=======

By using ``stginga``, the following plugins are also
available, in addition to the ones that already come with Ginga. Some are
customizable via plugin configuration files, which are available in the
`stginga/examples/configs <https://github.com/spacetelescope/stginga/tree/master/stginga/examples/configs>`_ directory.


.. _stginga-local-plugins:

Local Plugins
-------------

These plugins behave like a regular Ginga plugin:

.. toctree::
   :maxdepth: 2

   backgroundsub
   badpixcorr
   dqinspect
   snrcalc

These plugins are for very specific analysis needs. Therefore, they are
distributed but not loaded by default into the Ginga viewer. To load them,
one way is to use the ``--plugins`` option along with ``stginga`` command
(see :ref:`stginga-run`):

.. toctree::
   :maxdepth: 2

   mosaicauto

These plugins are not actively maintained. If you really, really want to use
them, see instructions at
`experimental/README.rst <https://github.com/spacetelescope/stginga/blob/master/experimental/README.rst>`_:

.. toctree::
   :maxdepth: 2

   mipick
   multiimage
   smoothing


.. _stginga-global-plugins:

Global Plugins
--------------

There is currently none to be distributed.
