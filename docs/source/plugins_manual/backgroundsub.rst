.. _local-plugin-backgroundsub:

BackgroundSub
=============

.. image:: images/backgroundsub_screenshot.png
  :width: 800px
  :alt: BackgroundSub plugin

This local plugin is used to calculate and subtract background value. Currently,
it only handles constant background and there is no way to save the subtracted
image. However, subtraction parameters can be saved to a JSON file, which then
can be reloaded as well.

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

  # If set to True, only use good pixels for calculations.
  # This is only applicable if there is an associated DQ extension.
  # Can also be changed in the GUI.
  ignore_bad_pixels = False
