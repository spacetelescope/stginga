.. _stginga-plugins:

Plugins
=======

By using ``stginga``, the following plugins (in alphabetical order) are also
available, in addition to the ones that already come with Ginga. Some are
customizable via plugin configuration files, which are available in the
`stginga/examples/configs <https://github.com/spacetelescope/stginga/tree/master/stginga/examples/configs>`_ directory.


.. _local-plugin-backgroundsub:

BackgroundSub
-------------

This plugin is used to calculate and subtract background value. Currently,
it only handles constant background and there is no way to save the subtracted
image. However, subtraction parameters can be saved to a JSON file, which then
can be reloaded as well.

.. image:: _static/backgroundsub_screenshot.png
  :width: 800px
  :alt: BackgroundSub plugin

It is customizable using ``~/.ginga/plugin_BackgroundSub.cfg``::

  #
  # BackgroundSub plugin preferences file
  #
  # Place this in file under ~/.ginga with the name "plugin_BackgroundSub.cfg"

  # Color of the background region outline and label
  bgsubcolor = 'magenta'

  # Default background region properties. Can also be changed in the GUI.
  # bgtype can be 'annulus', 'box', or 'constant'
  bgtype = 'annulus'
  annulus_width = 10

  # Default calculation parameters. Can also be changed in the GUI.
  # algorithm can be 'mean', 'median', or 'mode'
  algorithm = 'median'
  sigma = 1.8
  niter = 10


.. _local-plugin-dqinspect:

DQInspect
---------

This plugin is used to inspect the associated DQ array of a given image.
It shows the different DQ flags that went into a given pixel (middle right)
and also the overall mask of the selected DQ flag(s) (bottom right).

.. image:: _static/dqinspect_screenshot.png
  :width: 800px
  :alt: DQInspect plugin

It is customizable using ``~/.ginga/plugin_DQInspect.cfg``::

  #
  # DQInspect plugin preferences file
  #
  # Place this in file under ~/.ginga with the name "plugin_DQInspect.cfg"

  # Display long or short descriptions
  dqstr = 'long'

  # DQ definition files (JWST)
  dqdict = {'NIRCAM': 'data/dqflags_jwst.txt', 'NIRSPEC': ...}

  # Color to mark a single pixel for inspection
  pxdqcolor = 'red'

  # Color and opacity to mark all affected pixels
  imdqcolor = 'blue'
  imdqalpha = 1.0


.. _local-plugin-mipick:

MIPick
------

TBD


.. _local-plugin-multiimage:

MultiImage
----------

TBD
