"""Utility functions for ``stginga``."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

# THIRD-PARTY
import numpy as np
from astropy.stats import sigma_clip
from scipy import stats

__all__ = ['calc_stat']


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
        val = stats.mode(arr)[0][0]
    elif algorithm == 'stddev':
        val = arr.std()
    else:
        raise ValueError('{0} is not a valid algorithm for sky background '
                         'calculations'.format(algorithm))

    return val


# -------------- #
# FITS FUNCTIONS #
# -------------- #

def _fits_extnamever_lookup(filename, extname, extver):
    """Return ext num for given name and ver."""
    extnum = -1
    with fits.open(filename) as pf:
        for i, hdu in enumerate(pf):
            if hdu.name.startswith(extname) and hdu.ver == extver:
                extnum = i
                break
    return extnum
