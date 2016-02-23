.. _local-plugin-mipick:

MIPick
======

.. image:: images/mipick_screenshot.png
  :width: 800px
  :alt: MIPick plugin

This local plugin is like :ref:`Pick plugin <ginga:sec-plugins-pick>` but it
also works with :ref:`global-plugin-multiimage` to show postage stamps of the
same region in different images. The pick region, instead of being fixed to
image pixel coordinates, uses the image sky coordinates.
Also, as images are cycled through the main viewer, the region
will automatically update, again always fixed on the same section of sky.
