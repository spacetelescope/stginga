1.5 (2024-03-21)
----------------

Other Changes and Additions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Compatibility with Ginga 5. [#234]

- This version requires Python 3.9 or later.
  Also bumped minimum versions of other dependencies to
  ``astropy>=5``, ``ginga>=4.1``, and ``scipy>=1``. [#234]

1.4 (2023-11-28)
----------------

Bug Fixes
^^^^^^^^^

- BackgroundSub and BadPixCorr plugins now no longer creates a zero-radius
  circle when user clicks instead of drags on draw. [#228, #229]

Other Changes and Additions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

- This version requires Python 3.8 or later.
- Keeping the code up-to-date with new upstream changes.
- Universal wheel for PyPI release.
- Astroconda is no longer supported.

1.3 (2021-06-11)
----------------

New Features
^^^^^^^^^^^^

- New ``stginga.utils.scale_image_with_dq`` function to rescale image after
  cleaning bad pixels first. [#200]
- Exposed rescaling of WCS as ``stginga.utils.scale_wcs`` function. [#200]
- Added a new ``rescale`` keyword for ``stginga.utils.interpolate_badpix``
  function. [#200]

Other Changes and Additions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

- This version requires Python 3.7 or later. [#207]
- This version should be compatible with Ginga 3.2.

1.2 (2020-07-20)
----------------

New Features
^^^^^^^^^^^^

- Telescope name can now be extracted programmatically from header.
  It looks for ``TELESCOP`` header keyword by default. This can be customized
  using ``telescopekey`` in your ``~/ginga/general.cfg``. [#189]
- ``DQInspect`` now understands the FGS instrument for both HST and JWST by
  default. [#189]

API changes
^^^^^^^^^^^

- ``DQInspect`` now requires also the telescope name to construct ``dqdict``.
  Please update your ``~/.ginga/plugin_DQInspect.cfg`` file, if applicable.
  [#189]

Other Changes and Additions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

- This version should be compatible with Ginga 3.1.

1.1 (2020-02-03)
----------------

New Features
^^^^^^^^^^^^

- JWST ASDF file support. This feature is experimental and
  subject to change. [#177]

Bug fixes
^^^^^^^^^

- Fixed circle region type typo in example config files. [#167]
- Fixed JWST DQ definitions for ``DQInspect`` plugin. [#183]

Other Changes and Additions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

- Compatibility with Ginga 3.0. [#179]
- Infrastructure update in accordance to Astropy APE 17. [#182]

1.0 (2018-11-08)
----------------

This version was successfully tested with Ginga 2.7.2 in Python 3.7.

API changes
^^^^^^^^^^^

- Updated ACS DQ flags definition for ``DQInspect``.

Other Changes and Additions
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Python 2 support is dropped. Minimum Python version supported is now 3.5.

0.3 (2018-02-23)
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
- All ``stginga`` plugins are now under ``Custom`` category in Ginga's
  Operations menu. [#152]

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
