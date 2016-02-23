"""Shared image region handling either from data or WCS coordinates."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

# STDLIB
from math import cos, hypot, radians

# GINGA
from ginga.AstroImage import AstroImage

__all__ = ['Region']


class RegionError(Exception):
    """Generic Region errors."""


class RegionConversionError(RegionError):
    """Could not convert between coordinates."""


class Region(object):
    """Class to manage an image region that is shared between
    all displayed ones in :ref:`local-plugin-multiimage`.

    Its attributes are as documented in :meth:`set_region`.

    Parameters
    ----------
    logger : obj or `None`
        Ginga logger. If not provided, an new logger is created.

    """
    def __init__(self, logger=None):
        super(Region, self).__init__()

        if logger is None:
            import logging
            self.logger = logging.getLogger(__name__)
        else:
            self.logger = logger

        self._radius_scale = cos(radians(45))
        self.x = None
        self.y = None
        self.r = None
        self._coord = None
        self._image = None

    @property
    def coord(self):
        """{'data', 'wcs'}: Coordinate system of the region."""
        return self._coord

    @coord.setter
    def coord(self, val):
        val = val.lower()
        if val not in ('data', 'wcs'):
            raise RegionError('Invalid coordinate system')
        self._coord = val

    @property
    def image(self):
        """``AstroImage``: Reference image for the region."""
        return self._image

    @image.setter
    def image(self, val):
        if not isinstance(val, AstroImage):
            val = None
        self._image = val

    def set_region(self, x, y, r, coord, as_coord=None, image=None):
        """Define the image region.
        This is usually called right after initialization.

        Parameters
        ----------
        x, y, r : float
            The center point and radius of the region.

        coord : {'data', 'wcs'}
            The coordinate system of the given values.

        as_coord : {'data', 'wcs'}
            The native coordinate system to use.

        image : ``AstroImage``
            The reference image.

        """
        self.logger.debug('Setting new region.')
        self.x = x
        self.y = y
        self.r = r
        self.coord = coord
        if coord != as_coord:
            self.x, self.y, self.r = self.get_region(as_coord, image)
            self.coord = as_coord
        if image is not None:
            self.image = image

    def get_region(self, coord=None, image=None):
        """Return the region in the specified coordinate system.

        Parameters
        ----------
        coord : {'data', 'wcs'}
            The coordinate system to return in.

        image : ``AstroImage``
            The reference image, if conversion is needed.

        Returns
        -------
        x, y, r : float
            The center point and radius of the region.

        """
        convert = self.convert_func(to_coord=coord, image=image)
        dx, dy = self.delta()
        cx, cy = convert(self.x, self.y)
        cx1, cy1 = convert(self.x + dx, self.y + dy)
        cr = hypot(cx1 - cx, cy1 - cy)

        self.logger.debug('Region is x={0}, y={1}, r={2}'.format(cx, cy, cr))

        return cx, cy, cr

    def set_center(self, x, y, coord=None, image=None):
        """Set center point of the region.

        Parameters
        ----------
        x, y : float
            The new center point of the region.

        coord : {'data', 'wcs'}
            The coordinate system of the given center.

        image : ``AstroImage``
            The reference image of the given center.

        """
        convert = self.convert_func(from_coord=coord, image=image)
        self.x, self.y = convert(x, y)
        self.logger.debug('New center point x={0}, y={1}'.format(
            self.x, self.y))

    def set_coords(self, coord, image=None):
        """Set region parameters based on given coordinate system.

        Parameters
        ----------
        coord : {'data', 'wcs'}
            The new coordinate system to use.

        image : ``AstroImage``
            The new reference image.

        """
        self.x, self.y, self.r = self.get_region(coord=coord, image=image)
        self.coord = coord
        if image is not None:
            self.image = image

    def set_bbox(self, x1, y1, x2, y2, coord=None, image=None):
        """Set bounding box for the region.

        Parameters
        ----------
        x1, y1, x2, y2 : float
            Locations of the bounding box.

        coord : {'data', 'wcs'}
            The coordinate system of the given locations.

        image : ``AstroImage``
            The reference image of the given locations.

        """
        convert = self.convert_func(from_coord=coord, image=image)
        cx1, cy1 = convert(x1, y1)
        cx2, cy2 = convert(x2, y2)
        self.x = (cx1 + cx2) * 0.5
        self.y = (cy1 + cy2) * 0.5
        self.r = hypot(cx2 - self.x, cy2 - self.y)

    def bbox(self, coord=None, image=None):
        """Compute bounding box for the region.

        Parameters
        ----------
        coord : {'data', 'wcs'}
            The coordinate system to return in.

        image : ``AstroImage``
            The reference image if conversion is needed.

        Returns
        -------
        x1, y1, x2, y2 : float
            Locations of the region bounding box.

        """
        convert = self.convert_func(to_coord=coord, image=image)
        dx, dy = self.delta()
        x1, y1 = convert(self.x - dx, self.y - dy)
        x2, y2 = convert(self.x + dx, self.y + dy)
        (x1, x2) = (x1, x2) if x1 <= x2 else (x2, x1)
        (y1, y2) = (y1, y2) if y1 <= y2 else (y2, y1)

        self.logger.debug('Bounding box x1={0}, x2={1}, y1={2}, y2={3}'.format(
            x1, x2, y1, y2))

        return x1, y1, x2, y2

    def convert_func(self, from_coord=None, to_coord=None, image=None):
        """Determine conversion function to use.

        Parameters
        ----------
        from_coord, to_coord : {'data', 'wcs'}
            Coordinate systems to convert from and to.

        image : ``AstroImage``
            The reference image for conversion.

        Returns
        -------
        convert : func
            Either ``pixtoradec`` or ``radectopix`` method of the image.

        Raises
        ------
        RegionConversionError
            Missing reference image.

        """
        from_coord = self.coord if from_coord is None else from_coord
        to_coord = self.coord if to_coord is None else to_coord
        image = image if image is not None else self.image
        if from_coord == to_coord:
            return lambda x, y: (x, y)
        elif image is None:
            raise RegionConversionError('No reference specified for conversion')
        if to_coord == 'wcs':  # data -> wcs
            convert = image.pixtoradec
        else:  # wcs -> data
            convert = image.radectopix
        return convert

    def delta(self):
        """Compute delta for region center that is used for conversion.

        .. math::

            \\delta = r \\times \\textnormal{COS}(45^{\\circ})

        Returns
        -------
        dx, dy : float
            Delta for region center. They are both the same.

        """
        delta = self.r * self._radius_scale
        return (delta, delta)
