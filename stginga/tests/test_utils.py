"""Tests for ``utils.py``."""

import numpy as np
import pytest
from astropy.io import fits
from astropy.utils import minversion
from astropy.utils.data import get_pkg_data_filename
from numpy.testing import assert_allclose, assert_array_equal

from ..utils import (calc_stat, interpolate_badpix, find_ext, DQParser,
                     scale_image)

SCIPY_LT_1_1_0 = not minversion('scipy', '1.1.0')


class TestCalcStat(object):
    def setup_class(self):
        rng = np.random.RandomState(1234)
        self.array = rng.randn(10, 10)

    @pytest.mark.parametrize(
        ('algo', 'ans'),
        [('mean', 0.22538589848374507),
         ('median', 0.21188338677770105),
         ('mode', 0.22139729237840572),
         ('stddev', 0.4925049855366562)])
    def test_algo(self, algo, ans):
        result = calc_stat(self.array, algorithm=algo)
        assert_allclose(result, ans)

    def test_no_support(self):
        assert calc_stat([]) == 0

        with pytest.raises(ValueError):
            calc_stat(self.array, algorithm='foo')


class TestInterpBadPix(object):
    def setup_class(self):
        self.image = np.array([[1, 2, 3],
                               [4, 0, 6],
                               [7, 8, 9]], dtype=np.float)
        self.basis_mask = np.array([[True, True, True],
                                    [True, False, True],
                                    [True, True, True]])
        self.badpix_mask = ~self.basis_mask

    @pytest.mark.parametrize(
        ('algo', 'ans'),
        [('nearest', 2),
         ('linear', 5),
         ('cubic', 5.00000013)])
    def test_algo(self, algo, ans):
        im = self.image.copy()  # Probably redundant but just to be safe
        interpolate_badpix(
            im, self.badpix_mask, self.basis_mask, method=algo)
        assert_array_equal(im[self.basis_mask], self.image[self.basis_mask])
        assert_allclose(im[self.badpix_mask], ans)

    def test_wrong_inputs(self):
        with pytest.raises(ValueError):
            interpolate_badpix(
                self.image, self.badpix_mask, self.basis_mask, method='foo')

        with pytest.raises(ValueError):
            interpolate_badpix(self.image, self.badpix_mask, [])


class TestStuffWithFITS(object):
    @pytest.fixture(autouse=True)
    def setup_class(self, tmpdir):
        self.filename = str(tmpdir.join('test.fits'))
        hdulist = fits.HDUList()
        hduhdr = fits.PrimaryHDU()
        hduhdr.header['INSTRUME'] = 'ACS'
        hdulist.append(hduhdr)
        hduimg = fits.ImageHDU(np.arange(100).reshape(10, 10), name='SCI')
        hdulist.append(hduimg)
        hdulist.writeto(self.filename)

    def test_find_ext(self):
        for extname in ('PRIMARY', 'SCI'):
            assert find_ext(self.filename, extname)

        assert not find_ext(self.filename, 'FOO')
        assert not find_ext(None, 'SCI')

    def test_scale_image(self):
        """WCS handling is not tested."""
        outfile = self.filename.replace('test.fits', 'out.fits')
        scale_image(self.filename, outfile, 0.5, ext='SCI')

        # https://github.com/scipy/scipy/issues/8845
        if SCIPY_LT_1_1_0:
            ans = [[0, 2, 4, 7, 9],
                   [22, 25, 27, 29, 31],
                   [45, 47, 49, 52, 54],
                   [68, 70, 72, 74, 77],
                   [90, 92, 95, 97, 99]]
        else:
            ans = [[0, 2, 5, 7, 9],
                   [22, 25, 27, 29, 31],
                   [45, 47, 50, 52, 54],
                   [68, 70, 72, 74, 77],
                   [90, 92, 95, 97, 99]]

        with fits.open(outfile) as pf:
            assert pf[0].header['INSTRUME'] == 'ACS'
            assert_allclose(pf[0].data, ans)


# https://github.com/spacetelescope/reftools/blob/master/reftools/tests/test_interpretdq.py
def test_dq_parser():
    parsedq = DQParser(get_pkg_data_filename('../data/dqflags_acs.txt'))

    # One pixel
    dqs = parsedq.interpret_dqval(16658)
    assert sorted(dqs['DQFLAG']) == [2, 16, 256, 16384]

    # Array
    dqs = parsedq.interpret_array([1, 1, 16658, 0])
    assert_array_equal(dqs[1][0], [0, 1])
    for i in [2, 16, 256, 16384]:
        assert_array_equal(dqs[i][0], [2])
    for i in [4, 8, 32, 64, 128, 512, 1024, 2048, 4096, 8192, 32768]:
        assert len(dqs[i][0]) == 0
