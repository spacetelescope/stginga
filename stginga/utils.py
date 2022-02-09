"""Utility functions for ``stginga``."""
# STDLIB
import os
import warnings

# THIRD-PARTY
import numpy as np
from astropy import wcs
from astropy.convolution import convolve_fft, Box2DKernel
from astropy.io import ascii, fits
from astropy.stats import biweight_location
from astropy.stats import sigma_clip
from astropy.utils import minversion
from astropy.utils.exceptions import AstropyUserWarning
from scipy.interpolate import griddata
from scipy.ndimage import zoom

ASTROPY_LT_3_1 = not minversion('astropy', '3.1')
GINGA_LT_3 = not minversion('ginga', '3.0')

__all__ = ['calc_stat', 'interpolate_badpix', 'find_ext', 'DQParser',
           'scale_wcs', 'scale_image', 'scale_image_with_dq']


def calc_stat(data, sigma=1.8, niter=10, algorithm='median'):
    """Calculate statistics for given data.

    Parameters
    ----------
    data : ndarray
        Data to be calculated from.

    sigma : float
        Sigma for sigma clipping.

    niter : int
        Number of iterations for sigma clipping.

    algorithm : {'mean', 'median', 'mode', 'stddev'}
        Algorithm for statistics calculation.

    Returns
    -------
    val : float
        Statistics value.

    Raises
    ------
    ValueError
        Invalid algorithm.

    """
    arr = np.ravel(data)

    if len(arr) < 1:
        return 0.0

    kwargs = {'sigma': sigma}

    if ASTROPY_LT_3_1:
        kwargs['iters'] = niter
    else:
        kwargs['maxiters'] = niter

    arr_masked = sigma_clip(arr, **kwargs)
    arr = arr_masked.data[~arr_masked.mask]

    if len(arr) < 1:
        return 0.0

    algorithm = algorithm.lower()
    if algorithm == 'mean':
        val = arr.mean()
    elif algorithm == 'median':
        val = np.median(arr)
    elif algorithm == 'mode':
        val = biweight_location(arr)
    elif algorithm == 'stddev':
        val = arr.std()
    else:
        raise ValueError(f'{algorithm} is not a valid algorithm for sky '
                         'background calculations')

    return val


def interpolate_badpix(image, badpix_mask, basis_mask, method='linear',
                       rescale=False):
    """Use spline interpolation to fix bad pixel(s).

    Parameters
    ----------
    image : ndarray
        Image to be fixed in-place.

    badpix_mask, basis_mask : ndarray
        Boolean masks of bad pixel(s) and the region used
        as basis for interpolation.

    method : {'nearest', 'linear', 'cubic'}
        See :func:`~scipy.interpolate.griddata`.

    rescale : bool
        See :func:`~scipy.interpolate.griddata`.

    """
    y, x = np.where(basis_mask)
    z = image[basis_mask]
    ynew, xnew = np.where(badpix_mask)
    image[badpix_mask] = griddata((x, y), z, (xnew, ynew), method=method,
                                  rescale=rescale)


def find_ext(imfile, ext):
    """Determine whether given FITS file has the requested extension.

    Parameters
    ----------
    imfile : str
        Filename.

    ext : tuple
        Desired ``(EXTNAME, EXTVER)``.

    Returns
    -------
    has_ext : bool
        `True` if the extension exists.

    Examples
    --------
    >>> find_ext('myimage.fits', ('DQ', 1))

    """
    if imfile is None:  # This is needed to handle Ginga mosaic
        return False
    with fits.open(imfile) as pf:
        has_ext = ext in pf
    return has_ext


# STScI reftools.interpretdq.DQParser class modified for Ginga plugin.
class DQParser(object):
    """Class to handle parsing of DQ flags.

    **Definition Table**

    A "definition table" is an ASCII table that defines
    each DQ flag and its short and long descriptions.
    It can have optional comment line(s) for metadata,
    e.g.::

        # TELESCOPE = ANY
        # INSTRUMENT = ANY

    It must have three columns:

    1. ``DQFLAG`` contains the flag value (``uint16``).
    2. ``SHORT_DESCRIPTION`` (string).
    3. ``LONG_DESCRIPTION`` (string).

    Example file contents::

        # INSTRUMENT = HSTGENERIC
        DQFLAG SHORT_DESCRIPTION LONG_DESCRIPTION
        0      "OK"              "Good pixel"
        1      "LOST"            "Lost during compression"
        ...    ...               ...

    The table format must be readable by ``astropy.io.ascii``.

    Parameters
    ----------
    definition_file : str
        ASCII table that defines the DQ flags (see above).

    Attributes
    ----------
    tab : ``astropy.table.Table``
        Table object from given definition file.

    metadata : ``astropy.table.Table``
        Table object from file metadata.

    """
    def __init__(self, definition_file):
        self._dqcol = 'DQFLAG'
        self._sdcol = 'short'  # SHORT_DESCRIPTION
        self._ldcol = 'long'   # LONG_DESCRIPTION

        # Need to replace ~ with $HOME
        self.tab = ascii.read(
            os.path.expanduser(definition_file),
            names=(self._dqcol, self._sdcol, self._ldcol),
            converters={self._dqcol: [ascii.convert_numpy(np.uint)],
                        self._sdcol: [ascii.convert_numpy(str)],
                        self._ldcol: [ascii.convert_numpy(str)]})

        # Another table to store metadata
        self.metadata = ascii.read(self.tab.meta['comments'], delimiter='=',
                                   format='no_header', names=['key', 'val'])

        # Ensure table has OK flag to detect good pixel
        self._okflag = 0
        if self._okflag not in self.tab[self._dqcol]:
            self.tab.add_row([self._okflag, 'OK', 'Good pixel'])

        # Sort table in ascending order
        self.tab.sort(self._dqcol)

        # Compile a list of flags
        self._valid_flags = self.tab[self._dqcol]

    def interpret_array(self, data):
        """Interpret DQ values for an array.

        .. warning::

            If the array is large and has a lot of flagged elements,
            this can be resource intensive.

        Parameters
        ----------
        data : ndarray
            DQ values.

        Returns
        -------
        dqs_by_flag : dict
            Dictionary mapping each interpreted DQ value to indices
            of affected array elements.

        """
        data = np.asarray(data, dtype=int)  # Ensure int array
        dqs_by_flag = {}

        def _one_flag(vf):
            dqs_by_flag[vf] = np.where((data & vf) != 0)

        # Skip good flag
        list(map(_one_flag, self._valid_flags[1:]))

        return dqs_by_flag

    def interpret_dqval(self, dqval):
        """Interpret DQ values for a single pixel.

        Parameters
        ----------
        dqval : int
            DQ value.

        Returns
        -------
        dqs : ``astropy.table.Table``
            Table object containing a list of interpreted DQ values and
            their meanings.

        """
        dqval = int(dqval)

        # Good pixel, nothing to do
        if dqval == self._okflag:
            idx = np.where(self.tab[self._dqcol] == self._okflag)

        # Find all the possible DQ flags
        else:
            idx = (dqval & self._valid_flags) != 0

        return self.tab[idx]


def scale_wcs(input_hdr, zoom_factor, debug=False):
    """Rescale FITS WCS by the given zoom factor.
    This is used in :func:`scale_image` and :func:`scale_image_with_dq`.

    Both PC and CD matrices are supported. Distortion is not
    taken into account; therefore, this does not work on an
    image with ``CTYPE`` that ends in ``-SIP``.

    .. note::

        WCS transformation provided by Mihai Cara.

        Some warnings are suppressed.

    Parameters
    ----------
    input_hdr : `astropy.io.fits.Header`
        FITS header containing the WCS.

    zoom_factor : float
        See :func:`scipy.ndimage.interpolation.zoom`.

    debug : bool
        If `True`, print extra information to screen.

    Returns
    -------
    hdr : `astropy.io.fits.Header`
        Simple FITS header containing the rescaled WCS.

    Raises
    ------
    ValueError
        Invalid WCS.

    """
    slice_factor = int(1 / zoom_factor)
    old_wcs = wcs.WCS(input_hdr)  # To account for distortion, add "pf" as 2nd arg  # noqa

    # Supress RuntimeWarning about ignoring cdelt because cd is present.
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)
        new_wcs = old_wcs.slice(
            (np.s_[::slice_factor], np.s_[::slice_factor]))

    if old_wcs.wcs.has_pc():  # PC matrix
        wshdr = new_wcs.to_header()

    elif old_wcs.wcs.has_cd():  # CD matrix

        # Supress RuntimeWarning about ignoring cdelt because cd is present
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)
            new_wcs.wcs.cd *= new_wcs.wcs.cdelt

        new_wcs.wcs.set()
        wshdr = new_wcs.to_header()

        for i in range(1, 3):
            for j in range(1, 3):
                key = f'PC{i}_{j}'
                if key in wshdr:
                    newkey = f'CD{i}_{j}'
                    wshdr.rename_keyword(key, newkey)
                    if debug:
                        print(f'{key} -> {newkey}')

    else:
        raise ValueError('Missing CD or PC matrix for WCS')

    hdr = input_hdr.copy()

    if 'XTENSION' in hdr:
        del hdr['XTENSION']
    if 'SIMPLE' in hdr:  # pragma: no cover
        hdr['SIMPLE'] = True
    else:
        hdr.insert(0, ('SIMPLE', True))
    hdr.extend(
        [c if c[0] not in hdr else c[0:] for c in wshdr.cards], update=True)

    if debug:
        old_wcs.printwcs()
        wcs.WCS(wshdr).printwcs()
        wcs.WCS(hdr).printwcs()

    return hdr


# This is needed by QUIP to pre-shrink input images for quick-look mosaic
# in Ginga, but useful enough to put here for stginga's use if needed.
# Warnings are suppressed because WEx that calls QUIP treats all screen outputs
# as error messages.
def scale_image(infile, outfile, zoom_factor, ext=('SCI', 1), clobber=False,
                debug=False):
    """Rescale the image size in the given extension
    by the given zoom factor and adjust WCS accordingly.

    WCS adjustment is done using :func:`scale_wcs`.

    Output image is a single-extension FITS file with only
    the given extension header and data.

    Parameters
    ----------
    infile, outfile : str
        Input and output filenames.

    zoom_factor : float
        See :func:`scipy.ndimage.interpolation.zoom`.

    ext : int, str, or tuple
        Extension to extract.

    clobber : bool
        If `True`, overwrite existing output file.

    debug : bool
        If `True`, print extra information to screen.

    Raises
    ------
    ValueError
        Invalid data.

    """
    if not clobber and os.path.exists(outfile):  # pragma: no cover
        if debug:
            warnings.warn(f'{outfile} already exists',
                          AstropyUserWarning)
        return  # Instead of raising error at the very end

    with fits.open(infile) as pf:
        prihdr = pf['PRIMARY'].header
        hdr = pf[ext].header
        data = pf[ext].data

    # Inherit some keywords from primary header
    for key in ('ROOTNAME', 'TARGNAME', 'INSTRUME', 'DETECTOR',
                'FILTER', 'PUPIL', 'DATE-OBS', 'TIME-OBS'):
        if (key in hdr) or (key not in prihdr):
            continue
        hdr[key] = prihdr[key]

    if data.ndim != 2:  # pragma: no cover
        raise ValueError(f'Unsupported ndim={data.ndim}')

    # Scale the data.
    data = zoom(data, zoom_factor)

    # Adjust WCS
    outhdr = scale_wcs(hdr, zoom_factor, debug=debug)

    # Write to output file
    hdu = fits.PrimaryHDU(data)
    hdu.header = outhdr
    hdu.writeto(outfile, overwrite=clobber)


def scale_image_with_dq(infile, outfile, zoom_factor, dq_parser,
                        kernel_width=99, sci_ext=('SCI', 1), dq_ext=('DQ', 1),
                        bad_flag=1, ignore_edge_pixels=4, overwrite=False,
                        debug=False):
    """Rescale the image size in the given extension by the given block size,
    taking data quality (DQ) flags into account, and adjust WCS accordingly.

    WCS adjustment is done using :func:`scale_wcs`.

    Output image is a single-extension FITS file with only
    the given extension header and data.

    Parameters
    ----------
    infile, outfile : str
        Input and output filenames.

    zoom_factor : float
        See :func:`scipy.ndimage.interpolation.zoom`.

    dq_parser : `DQParser`
        DQ parser for interpreting DQ flag.

    kernel_width : int
        See :class:`astropy.convolution.Box2DKernel`.

    sci_ext, dq_ext : int, str, or tuple
        Science and DQ extensions to extract, respectively.

    bad_flag : int
        DQ flag value to indicate bad pixels to exclude from calculations.
        Compound flag is currently not supported.

    ignore_edge_pixels : int
        Ignore these number of pixels along the edges.
        The default value of 4 is for the reference pixels on JWST NIRCam
        detectors.

    overwrite : bool
        If `True`, overwrite existing output file.

    debug : bool
        If `True`, print extra information to screen.

    Raises
    ------
    ValueError
        Invalid data.

    """
    if not overwrite and os.path.exists(outfile):  # pragma: no cover
        if debug:
            warnings.warn(f'{outfile} already exists',
                          AstropyUserWarning)
        return  # Instead of raising error at the very end

    with fits.open(infile) as pf:
        prihdr = pf['PRIMARY'].header
        hdr = pf[sci_ext].header
        data = pf[sci_ext].data
        dq = pf[dq_ext].data

    if data.ndim != 2:  # pragma: no cover
        raise ValueError(f'Unsupported ndim={data.ndim}')

    # Inherit some keywords from primary header
    for key in ('ROOTNAME', 'TARGNAME', 'INSTRUME', 'DETECTOR',
                'FILTER', 'PUPIL', 'DATE-OBS', 'TIME-OBS'):
        if (key in hdr) or (key not in prihdr):
            continue
        hdr[key] = prihdr[key]

    dqs_by_flags = dq_parser.interpret_array(dq)

    # Edge pixels
    iy_max = data.shape[0] - ignore_edge_pixels
    ix_max = data.shape[1] - ignore_edge_pixels
    edge_mask = np.ones_like(dq, dtype=bool)
    edge_mask[ignore_edge_pixels:iy_max, ignore_edge_pixels:ix_max] = False

    badpix_mask = np.zeros_like(dq, dtype=bool)
    badpix_mask[dqs_by_flags[bad_flag]] = True
    badpix_mask[edge_mask] = False  # Ignore edge

    # Fix bad pixels with convolution
    box_kernel = Box2DKernel(kernel_width)
    smoothed_data = convolve_fft(data, box_kernel, mask=badpix_mask)  # 5 secs
    data[badpix_mask] = smoothed_data[badpix_mask]

    # Should not have NaN in fixed image?
    if not np.all(np.isfinite(data)):
        raise ValueError('Fixed image has NaN(s)')

    # Scale the data.
    data = zoom(data, zoom_factor)

    # Adjust WCS
    outhdr = scale_wcs(hdr, zoom_factor, debug=debug)

    # Write to output file
    hdu = fits.PrimaryHDU(data)
    hdu.header = outhdr
    hdu.writeto(outfile, overwrite=overwrite)
