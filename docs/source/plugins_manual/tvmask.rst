.. _local-plugin-tvmask:

TVMask
------

.. image:: images/tvmask_screenshot.png
  :width: 800px
  :alt: TVMask plugin

This local plugin allows non-interactive display of mask by reading in a FITS
file, where non-zero is assumed to be masked data.

To display different masks (e.g., some masked as green and some as pink, as
shown above):

1. Select green from the drop-down menu. Alternately, enter desired alpha value.
2. Using "Load Mask" button, load the relevant FITS file.
3. Repeat Step 1 but now select pink from the drop-down menu.
4. Repeat Step 2 but choose another FITS file.
5. To display a third mask as pink too, repeat Step 4 without changing the
   drop-down menu.

Selecting an entry (or multiple entries) from the table listing will
highlight the mask(s) on the image. The highlight uses a pre-defined color and
alpha (customizable below). Clicking on a masked pixel will highlight the
mask(s) both on the image and the table listing.

You can also highlight all the masks within a region both on the image
and the table listing by drawing a rectangle on the image using the right mouse
button while this plugin is active.

Pressing the "Clear" button will clear the masks but does not clear the
plugin's memory; That is, when you press "Redraw", the same masks will
reappear on the same image. However, pressing "Forget" will clear the masks
both from display and memory; That is, you will need to reload your file(s) to
recreate the masks.

To redraw the same masks with different color or alpha, press "Forget"
and repeat the steps above, as necessary.

If images of very different pointings/dimensions are displayed in the same
channel, masks that belong to one image but fall outside another will not
appear in the latter.

To create a mask that this plugin can read, one can use results from
:ref:`ginga:plugins-drawing` (press "Create Mask" after drawing and save the
mask using :ref:`local-plugin-saveimage`), in addition to creating a FITS file
by hand using :ref:`Astropy FITS <astropy:astropy-io-fits>`, etc.

Used together with :ref:`local-plugin-tvmark`, you can overlay both point
sources and masked regions in Ginga.

This plugin is customizable using ``~/.ginga/plugin_TVMask.cfg``::

  #
  # TVMask plugin preferences file
  #
  # Place this in file under ~/.ginga with the name "plugin_TVMask.cfg"

  # Mask color -- Any color name accepted by Ginga
  maskcolor = 'green'

  # Mask alpha (transparency) -- 0=transparent, 1=opaque
  maskalpha = 0.5

  # Highlighted mask color and alpha
  hlcolor = 'white'
  hlalpha = 1.0
