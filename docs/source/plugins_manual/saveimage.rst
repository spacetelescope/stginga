.. _local-plugin-saveimage:

SaveImage
=========

.. image:: images/saveimage_screenshot.png
  :width: 400px
  :alt: SaveImage plugin

This local plugin is used to save any changes made in Ginga back to output
images. For example, a background-subtracted image that was modified by
:ref:`local-plugin-backgroundsub`. Currently, only FITS images (single or
multiple extensions) are supported.

Given the output directory (e.g., ``/mypath/outputs/``), a suffix
(e.g., ``stginga``), and a selected image (e.g., ``image1.fits``), the output
file will be ``/mypath/outputs/image1_stginga.fits``. The modified extension(s)
will have new header or data extracted from Ginga, while those not modified will
remain untouched. Relevant change log entries from Ginga's ``ChangeHistory``
global plugin will be inserted into the history of its ``PRIMARY`` header.

It is customizable using ``~/.ginga/plugin_SaveImage.cfg``::

  #
  # SaveImage plugin preferences file
  #
  # Place this in file under ~/.ginga with the name "plugin_SaveImage.cfg"

  # Default output parameters. Can also be changed in the GUI.
  output_directory = '.'
  output_suffix = 'stginga'

  # Clobber existing output files or not
  clobber = False

  # Only list modified images from the channel
  modified_only = True

  # Maximum mosaic size to allow for writing out.
  # This is useful to prevent super large mosaic from being written.
  # Default is 10k x 10k
  max_mosaic_size = 1e8

  # Maximum number of rows that will turn off auto column resizing (for speed)
  max_rows_for_col_resize = 5000
