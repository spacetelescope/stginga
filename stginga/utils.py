"""Utility functions for ``stginga``."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from astropy.extern.six.moves import map

# STDLIB
import os

# THIRD-PARTY
import numpy as np
from astropy.io import ascii, fits
from astropy.stats import biweight_location
from astropy.stats import sigma_clip
from astropy import version as astropy_version

# GINGA
from ginga.misc import Future

__all__ = ['calc_stat', 'find_ext', 'find_wfpc2_dq', 'DQParser',
           'autoload_ginga_image']


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

    if ((astropy_version.major==1 and astropy_version.minor==0) or
            (astropy_version.major < 1)):
        arr_masked = sigma_clip(arr, sig=sigma, iters=niter)
    else:
        arr_masked = sigma_clip(arr, sigma=sigma, iters=niter)

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
        raise ValueError('{0} is not a valid algorithm for sky background '
                         'calculations'.format(algorithm))

    return val


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
    with fits.open(imfile) as pf:
        has_ext = ext in pf
    return has_ext


def find_wfpc2_dq(imfile, cachekeyprefix, chipnum):
    """Find DQ file for WFPC2 data.

    The DQ file has ``c1m`` in its name.
    However, extension name could be either ``'DQ'`` or ``'SCI'``.

    Parameters
    ----------
    imfile : str
        Filename for science data (``c0m``).

    cachekeyprefix : str
        Prefix for Ginga cache key. Extension info will be appended to
        create the actual cache key.

    chipnum : int
        Chip number, which is same as extension version.

    Returns
    -------
    has_dq : bool
        `True` if DQ data exist.

    dqfile : str
        Filename for DQ data.

    dqextnum : tuple
        ``(EXTNAME, EXTVER)`` for DQ data.

    cachekey : str
        Ginga cache key for DQ data.

    """
    dqfile = imfile.replace('c0m', 'c1m')
    cachekeyprefix = cachekeyprefix.replace('c0m', 'c1m')
    dqextnum = ('DQ', chipnum)
    has_dq = find_ext(dqfile, dqextnum)

    if not has_dq:
        dqextnum = ('SCI', chipnum)
        has_dq = find_ext(dqfile, dqextnum)

    cachekey = '{0}[{1},{2}]'.format(cachekeyprefix, dqextnum[0], chipnum)
    return has_dq, dqfile, dqextnum, cachekey


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
            names = (self._dqcol, self._sdcol, self._ldcol),
            converters = {self._dqcol: [ascii.convert_numpy(np.uint16)],
                          self._sdcol: [ascii.convert_numpy(np.str)],
                          self._ldcol: [ascii.convert_numpy(np.str)]})

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
        data = np.asarray(data, dtype=np.int)  # Ensure int array
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


#####################################
# Functions tied in with Ginga API. #
#####################################

# TODO: Is this better off as a method in new Ginga plugin mixin class?
def autoload_ginga_image(fv, chname, filename, extnum, cachekey):
    """Automatically load a given image extension into Ginga viewer.
    This is to be called from within a Ginga local plugin.

    Parameters
    ----------
    fv
        Ginga viewer object. This is ``self.fv`` in the plugin.

    chname : str
        Ginga channel name to display the image in.

    filename : str
        Image filename.

    extnum : int
        Image extension number.

    cachekey : str
        Key for Ginga data cache. Usually, this is in the format of
        ``prefix[extname, extver]``.

    Returns
    -------
    image
        Ginga image object.

    """
    chinfo = fv.get_channelInfo(chname)

    # Image already loaded
    if cachekey in chinfo.datasrc:
        #print('Loading {0} from cache'.format(cachekey))
        image = chinfo.datasrc[cachekey]

    # Auto load image data
    else:
        #print('Loading {0} from {1}'.format(cachekey, filename))
        image = fv.load_image(filename, idx=extnum)
        future = Future.Future()
        future.freeze(fv.load_image, filename, idx=extnum)
        image.set(path=filename, idx=extnum, name=cachekey, image_future=future)
        fv.add_image(cachekey, image, chname=chname, silent=True)
        fv.advertise_image(chname, image)

    return image
