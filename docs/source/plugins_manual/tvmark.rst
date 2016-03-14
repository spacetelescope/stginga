.. _local-plugin-tvmark:

TVMark
------

.. image:: images/tvmark_screenshot.png
  :width: 800px
  :alt: TVMark plugin

This local plugin allows non-interactive marking of points of interest by
reading in a file containing a table with RA and DEC positions of those points.
Any text file that can be read by :ref:`Astropy ASCII Tables <astropy:io-ascii>`
is acceptable but it *must* contain both ``'ra'`` and ``'dec'`` columns.
An attempt will be made to convert RA and DEC values to degrees.
If the unit conversion fails, they will be assumed to be in degrees already.

Alternately, if the file has ``'x'`` and ``'y'`` columns containing the direct
pixel locations, you can read these columns instead by unchecking the
"Use RADEC" box. Pixel values must be 1-indexed (i.e., first pixel starts from
1, not 0). This is useful when you want to mark the physical pixels regardless
of WCS (e.g., marking hot pixels on a detector). RA and DEC will still be
displayed if the image has WCS information but they will not affect the
markings.

To mark different groups (e.g., displaying galaxies as green circles and
background as cyan crosses, as shown above):

1. Select green circle from the drop-down menus. Alternately, enter desired
   size or width.
2. Make sure "Use RADEC" box is checked, if applicable.
3. Using "Load Coords" button, load the file containing RA and DEC (or X and Y)
   positions for galaxies *only*.
4. Repeat Step 1 but now select cyan cross from the drop-down menus.
5. Repeat Step 2 but choose the file containing background positions *only*.

Selecting an entry (or multiple entries) from the table listing will
highlight the marking(s) on the image. The highlight uses the same shape
and color, but a slightly thicker line. Clicking on a marking on the image
will highlight it and its neighbors (if they are close enough) both on the
image and the table listing.

You can also highlight all the markings within a region both on the image
and the table listing by drawing a rectangle on the image using the right mouse
button while this plugin is active.

Pressing the "Clear" button will clear the markings but does not clear the
plugin's memory; That is, when you press "Redraw", the same markings will
reappear on the same image. However, pressing "Forget" will clear the markings
both from display and memory; That is, you will need to reload your file(s) to
recreate the markings.

To redraw the same positions with different marking parameters, press "Forget"
and repeat the steps above, as necessary. However, if you simply wish to change
the line width (thickness), pressing "Clear" and then "Redraw" after you entered
the new width value will suffice.

If images of very different pointings/dimensions are displayed in the same
channel, markings that belong to one image but fall outside another will not
appear in the latter.

To create a table that this plugin can read, one can use results from
:ref:`ginga:sec-plugins-pick` or :ref:`local-plugin-mipick`, in addition to
creating a table by hand, using :ref:`Astropy ASCII Tables <astropy:io-ascii>`,
etc.

Used together with :ref:`local-plugin-tvmask`, you can overlay both point
sources and masked regions in Ginga.

This plugin is customizable using ``~/.ginga/plugin_TVMark.cfg``::

  #
  # TVMark plugin preferences file
  #
  # Place this in file under ~/.ginga with the name "plugin_TVMark.cfg"

  # Marking type -- 'circle' or 'cross'
  marktype = 'circle'

  # Marking color -- Any color name accepted by Ginga
  markcolor = 'green'

  # Marking size or radius
  marksize = 5

  # Marking line width (thickness)
  markwidth = 1

  # Radius (pix) used to find closest marking when user clicks on display
  searchradius = 10

  # True -- Use 'ra' and 'dec' columns to extract RA/DEC positions. This option
  #         uses image WCS to convert to pixel locations.
  # False -- Use 'x' and 'y' columns to extract pixel locations directly.
  #          This does not use WCS.
  use_radec = True
