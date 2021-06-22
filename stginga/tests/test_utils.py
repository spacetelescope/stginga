"""Tests for ``utils.py``."""

import numpy as np
import pytest
from astropy.io import fits
from astropy.utils import minversion
from astropy.utils.data import get_pkg_data_filename
from astropy.wcs import WCS
from numpy.testing import assert_allclose, assert_array_equal

from ..utils import (calc_stat, interpolate_badpix, find_ext, DQParser,
                     scale_image, scale_image_with_dq)

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
                               [7, 8, 9]], dtype=float)
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
        self.bad_flag = 1
        hdulist = fits.HDUList()

        hduhdr = fits.PrimaryHDU()
        hduhdr.header['INSTRUME'] = 'ACS'
        hdulist.append(hduhdr)

        w = WCS()
        w.wcs.crpix = [4.5, 4.5]
        w.wcs.crval = [5, 15]
        w.wcs.cd = [[1e-5, -1e-8], [1.5e-8, 1.2e-5]]
        w.wcs.ctype = ['RA---TAN', 'DEC--TAN']
        w.wcs.set()
        img_arr = np.arange(100).reshape(10, 10)
        hduimg = fits.ImageHDU(img_arr, name='SCI')
        hduimg.header.extend(w.to_header())
        hdulist.append(hduimg)

        mask_arr = np.zeros_like(img_arr, dtype=np.uint32)
        mask_arr[2, 2] = self.bad_flag
        mask_arr[4:8, 3:7] = self.bad_flag  # Big area
        mask_arr[8, 8] = self.bad_flag  # Next to edge
        mask_arr[1, 8] = 2  # Should not be corrected
        mask_arr[2, 8] = self.bad_flag | 2  # Should be corrected
        mask_arr[:, 0] = self.bad_flag  # The next 4 lines define edges to be ignored  # noqa
        mask_arr[:, -1] = self.bad_flag
        mask_arr[0, :] = self.bad_flag
        mask_arr[-1:, :] = self.bad_flag
        hdumask = fits.ImageHDU(mask_arr, name='DQ')
        hdulist.append(hdumask)

        hdulist.writeto(self.filename)

    def test_find_ext(self):
        for extname in ('PRIMARY', 'SCI'):
            assert find_ext(self.filename, extname)

        assert not find_ext(self.filename, 'FOO')
        assert not find_ext(None, 'SCI')

    def test_scale_image(self):
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

        with fits.open(self.filename) as pf_orig:
            in_hdr = pf_orig['SCI'].header
            in_wcs = WCS(in_hdr)

        with fits.open(outfile) as pf:
            outhdr = pf[0].header
            outwcs = WCS(outhdr)
            assert_allclose(pf[0].data, ans)

        assert outhdr['INSTRUME'] == 'ACS'
        assert outhdr['CRPIX1'] == 2.5
        assert outhdr['CRPIX2'] == 2.5
        assert outhdr['CDELT1'] == 2
        assert outhdr['CDELT2'] == 2

        for key in ('PC1_1', 'PC1_2', 'PC2_1', 'PC2_2', 'CUNIT1', 'CUNIT2',
                    'CTYPE1', 'CTYPE1', 'CRVAL1', 'CRVAL2', 'RADESYS'):
            assert outhdr[key] == in_hdr[key]

        # FIXME: Why input CRPIX needed to match output RA/Dec is off by 1?
        c1 = in_wcs.pixel_to_world(in_hdr['CRPIX1'] + 1, in_hdr['CRPIX2'] + 1)
        c2 = outwcs.pixel_to_world(outhdr['CRPIX1'], outhdr['CRPIX2'])
        assert_allclose(c1.separation(c2).value, 0)

    def test_scale_image_with_dq(self):
        """Test scaling with mask."""
        outfile = self.filename.replace('test.fits', 'out_masked.fits')
        parsedq = DQParser(
            get_pkg_data_filename('data/dqflags_jwst.txt', package='stginga'))
        scale_image_with_dq(
            self.filename, outfile, 0.5, parsedq, kernel_width=5,
            sci_ext='SCI', dq_ext='DQ', bad_flag=self.bad_flag,
            ignore_edge_pixels=1)
        ans = [[0, 2, 5, 7, 9],
               [22, 23, 27, 30, 31],
               [45, 46, 37, 51, 54],
               [68, 71, 83, 75, 77],
               [90, 92, 95, 97, 99]]
        with fits.open(outfile) as pf:
            assert_allclose(pf[0].data, ans)


# https://github.com/spacetelescope/reftools/blob/master/reftools/tests/test_interpretdq.py
def test_dq_parser():
    parsedq = DQParser(
        get_pkg_data_filename('data/dqflags_acs.txt', package='stginga'))

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
