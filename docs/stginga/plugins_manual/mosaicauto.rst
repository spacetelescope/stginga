.. _local-plugin-mosaicauto:

MosaicAuto
==========

.. image:: images/mosaicauto_screenshot.png
  :width: 800px
  :alt: MosaicAuto plugin

.. warning:: This can be very memory intensive.

This local plugin is used to automatically create a mosaic of all currently
loaded images in the channel. The position of an image on the mosaic is
determined by its WCS without distortion correction. This is meant as a
quick-look tool, not an
`AstroDrizzle <http://ssb.stsci.edu/doc/stsci_python_x/drizzlepac.doc/html/index.html>`_
replacement. Currently, such a mosaic can only be created once per Ginga
session.

Once the mosaic is successfully created, user can select the desired
image name(s) to highlight associated footprint(s) on the mosaic. User can also
save an image list of the selected image(s). Optionally, the mosaic itself can
be saved using :ref:`ginga:sec-plugins-global-saveimage`.

.. automodule:: stginga.plugins.MosaicAuto
