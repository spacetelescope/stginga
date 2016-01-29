.. _local-plugin-snrcalc:

SNRCalc
-------

.. image:: images/snrcalc_screenshot.png
  :width: 800px
  :alt: SNRCalc plugin

This local plugin is used to calculate the surface-to-background ratio (SBR)
and the signal-to-noise ratio (SNR), as follow.

SBR is as defined by `Ball <http://www.ballaerospace.com/>`_, *"Take the median
value of the pixels within the image. In the case of a defocused spot, this is
just the median value within the 'top hat' portion of the image. Next, take the
standard deviation of the pixels that are clearly in the background, that is,
have no incident photons on them. Take the ratio of these two quantities, and
you have the signal-to-background ratio."*

Given selected science (:math:`S`) and background (:math:`B`) regions:

.. math::

    \mathrm{SBR} = \frac{\mathrm{MEDIAN}(S)}{\mathrm{STDEV}(B)}

For the science region above, as long as the image has an accompanying error
array (e.g., the ``ERR`` extension), its SNR can also be calculated:

.. math::

    a = \frac{S}{\mathrm{ERR}}

    \mathrm{SNR}_{\mathrm{min}} = \mathrm{MIN}(a)

    \mathrm{SNR}_{\mathrm{max}} = \mathrm{MAX}(a)

    \overline{\mathrm{SNR}} = \mathrm{MEAN}(a)

While SNR is more popular, SBR is useful for images without existing or reliable
errors. User can also define a minimum limit for SBR check, so that the GUI can
provide a quick visual indication on whether the image achieves the desired SBR
or not.

User can save the calculated values in the image header using the "Update HDR"
button. Currently, there is no way to write out the modified image header back
to the image file. However, calculation parameters can be saved to a JSON file,
which then can be reloaded as well.

It is customizable using ``~/.ginga/plugin_SNRCalc.cfg``::

  #
  # SNRCalc plugin preferences file
  #
  # Place this in file under ~/.ginga with the name "plugin_SNRCalc.cfg"

  # Color of signal region for SBR (and SNR)
  sbrcolor = 'blue3'

  # Color of background region for SBR only
  sbrbgcolor = 'magenta'

  # Signal calculation parameters. Can also be changed in the GUI.
  # sigtype can be 'box', 'circular', or 'polygon'
  sigtype = 'circular'

  # Background calculation parameters. Can also be changed in the GUI.
  bgradius = 200
  annulus_width = 10
  sigma = 1.8
  niter = 10

  # This is the min SBR value used unless set_minsbr() method is reimplemented
  # in a subclass.
  default_minsbr = 100

  # If set to True, only use good pixels for calculations.
  # This is only applicable if there is an associated DQ extension.
  # Can also be changed in the GUI.
  ignore_bad_pixels = False
