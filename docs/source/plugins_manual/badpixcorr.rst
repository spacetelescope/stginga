.. _local-plugin-badpixcorr:

BadPixCorr
==========

.. image:: images/badpixcorr_screenshot.png
  :width: 800px
  :alt: BadPixCorr plugin

This local plugin is used to fix bad pixels. Currently, it only handles fixing
a single bad pixel or bad pixels within a circular region. The corresponding
DQ flags will also be set to the given new flag value (default is zero).
Correction parameters can be saved to a JSON file, which then can be reloaded
as well. The corrected image can be saved using :ref:`local-plugin-saveimage`.

It is customizable using ``~/.ginga/plugin_BadPixCorr.cfg``::

  #
  # BadPixCorr plugin preferences file
  #
  # Place this in file under ~/.ginga with the name "plugin_BadPixCorr.cfg"

  # Color to mark bad pixel(s)
  bpixcorrcolor = 'green'

  # Color of annulus region used for correction
  bpixannuluscolor = 'magenta'

  # Default bad pixel(s) properties. Some can also be changed in the GUI.
  # corrtype can be 'single' or 'circular'
  corrtype = 'circular'
  point_radius = 5

  # Default correction parameters. Can also be changed in the GUI.
  # filltype can be 'annulus', 'constant', or 'spline'
  # griddata can be 'nearest', 'linear', or 'cubic'
  # algorithm can be 'mean', 'median', or 'mode'
  filltype = 'annulus'
  annulus_radius = 5
  annulus_width = 10
  griddata_method = 'linear'
  algorithm = 'median'
  sigma = 1.8
  niter = 10

  # DQ flag to indicate that the bad pixel has been fixed
  dq_fixed_flag = 0
