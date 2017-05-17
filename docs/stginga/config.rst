.. _stginga-config:

Configuration Files
===================

To use STScI recommended settings, refer to the ``*.cfg`` files in
``stginga/examples/configs``. You can modify your existing configurations
using the given values in the examples, or copy the files directly to your
``$HOME/.ginga`` directory. The latter is *not* recommended unless you know what
you are doing (and remember to **back up your existing Ginga configurations**
before copying). You can further customize Ginga according to your own
preferences afterwards by modifying them again manually.

Note that our versions of *existing* Ginga configuration files do not have
a complete list of possible configuration values. We simply list the values
that we recommend for overriding Ginga defaults. For a full list, please refer
to the respective examples in
`ginga/examples/configs <https://github.com/ejeschke/ginga/tree/master/ginga/examples/configs>`_.

Our own plugin configurations are described with their respective
:ref:`stginga-plugins`. Meanwhile, we explain the importance of overriding some
Ginga defaults for use with STScI data below.


.. _stginga-general-cfg:

general.cfg
-----------

Due to the fact that some plugins can modify image buffers in memory
(e.g., :ref:`local-plugin-backgroundsub`), it is recommended that Ginga's data
cache is set to never expire (at the risk of memory error if you open more
images than your machine can handle). If this is not set, you might lose any
changes to your data buffer when the image is reloaded from file:

.. code-block:: python

    numImages = 0

.. note::

    If you use ``channel_<channelname>.cfg`` (e.g., ``channel_Image.cfg``),
    you also need to set ``numImages`` there appropriately, as it overrides
    the general setting.

In addition, our plugins also use some general settings that are specific to
STScI FITS data structure. If they are not set, HST defaults are used:

.. code-block:: python

    # Inherit PRIMARY (EXT=0) header for multi-extension FITS
    inherit_primary_header = True

    # Header keywords. These can be in PRIMARY header only if it is inherited.
    # Otherwise, Ginga will only look in the specified extension.
    extnamekey = 'EXTNAME'
    extverkey = 'EXTVER'
    sciextname = 'SCI'
    errextname = 'ERR'
    dqextname = 'DQ'
    instrumentkey = 'INSTRUME'
    targnamekey = 'TARGNAME'


.. _stginga-ginga-config-py:

ginga_config.py
---------------

This is the same file as mentioned in :ref:`stginga-run-gingaconfig`.
The following add default catalog services to the :ref:`ginga:plugins-catalogs`
local plugin:

.. code-block:: python

    from ginga.util.catalog import AstroPyCatalogServer

    # TODO: Add MAST interface when available on Astroquery.
    # Add Cone Search services
    catalogs = [
        ('The HST Guide Star Catalog, Version 1.2 (Lasker+ 1996) 1',
         'GSC_1.2'),
        ('The PMM USNO-A1.0 Catalogue (Monet 1997) 1', 'USNO_A1'),
        ('The USNO-A2.0 Catalogue (Monet+ 1998) 1', 'USNO_A2'),
    ]
    bank = ginga.get_ServerBank()
    for longname, shortname in catalogs:
        obj = AstroPyCatalogServer(
            ginga.logger, longname, shortname, '', shortname)
        bank.addCatalogServer(obj)


.. _stginga-contents-cfg:

plugin_Contents.cfg
-------------------

Ginga's default columns for
`Contents plugin <https://ginga.readthedocs.io/en/latest/manual/plugins.html#contents>`_
do not apply to STScI FITS data. Therefore, you should customize it to show
keyword values that are relevant to your own data. However, you should *always*
keep ``NAME`` and ``MODIFIED`` because they are used to identify the image
buffer and specify whether the buffer has changed, respectively. For example:

.. code-block:: python

    # Columns to show from metadata
    # Format: [(col header, keyword1), ... ]
    columns = [ ('Name', 'NAME'), ('Object', 'TARGNAME'), ..., ('Modified', 'MODIFIED')]


.. _stginga-thumbs-cfg:

plugin_Thumbs.cfg
-----------------

Ginga's default keywords for
`Thumbs plugin <https://ginga.readthedocs.io/en/latest/manual/plugins.html#thumbs>`_
do not apply to STScI FITS data. Therefore, you should customize it to show
keyword values that are relevant to your own data. For example:

.. code-block:: python

    tt_keywords = ['EXTNAME', 'EXTVER', 'NAXIS1', 'NAXIS2']
