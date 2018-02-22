0.3 (unreleased)
----------------

This is the last release to support Python 2.

New Features
^^^^^^^^^^^^
- Use new notification system for ``ChangeHistory`` that goes with Ginga 2.7.
  [#147,#149,ejeschke/ginga#621]
- Added example to auto-start ``MultiDim`` in ``ginga_config.py``. [#144]

API changes
^^^^^^^^^^^
- ``MIPick``, ``MultiImage``, and ``Smoothing`` plugins are moved to
  "experimental" folder. So is the custom layout that goes with ``MultiImage``
  and ``MIPick``. These are no longer actively supported. [#152]
- ``WBrowser`` now supports docstring rendering while offline when Internet
  connection is unavalable. [#152]

Bug fixes
^^^^^^^^^
- Use toolkit-agnostic treeview deselection for ``MosaicAuto``. [#142]

Other Changes and Additions
^^^^^^^^^^^^^^^^^^^^^^^^^^^
- Updated ``astropy-helpers`` to v2.0.4. [#152]
- Deprecated Jupyter notebook support is removed. [#152]

0.2.1 (2017-07-20)
------------------

Bug fix for MosaicAuto so that select-footprint-by-point-and-click feature
would work on Ginga 2.6.4 or earlier.

0.2 (2017-07-19)
----------------

This version is compatible with Astropy 2.0. stginga now uses Ginga's new-style
drawings interface. Also include other changes to keep up with Ginga's own
changes; So if this version does not work with your older Ginga version,
it is time to upgrade Ginga.

Other changes:

* Improvements to MosaicAuto plugin.
* Added some default Cone Search catalogs for Catalog plugin.
* Updated astropy-helpers to v2.0.
* Removed deprecated code for nbconvert.
* Fixed doc build and PEP 8 warnings.

0.1 (2016-06-21)
----------------

New Features
^^^^^^^^^^^^

Since this is the first release, everything is a new feature.

API changes
^^^^^^^^^^^

Since this is the first release, there are no API changes yet.

Bug fixes
^^^^^^^^^

Since this is the first release, there are no bug fixes yet.

Other Changes and Additions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

N/A
