.. _local-plugin-mipick:

MIPick
======

.. warning:: This is experimental; not actively maintain and might not work.

.. image:: images/mipick_screenshot.png
  :width: 800px
  :alt: MIPick plugin

This local plugin is mainly a demonstration on how custom plugins can be
integrated with existing plugins. This plugin is based on the
:ref:`Pick plugin <ginga:sec-plugins-pick>`.
However, the pick region, instead of being fixed to image
pixel coordinates, uses the image sky coordinates. If run with
:ref:`local-plugin-multiimage`, the postage stamps will show the same region
in different images.
Also, as images are cycled through the main viewer, the region
will automatically update, again always fixed on the same section of sky.
