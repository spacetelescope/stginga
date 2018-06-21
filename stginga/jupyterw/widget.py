"""
Dev notes
=========

GUI interactions:

* Right clicking should do ds9-style stretch adjustment. (*not* the same as
  the ``stretch`` property - here I mean "brightness/contrast" adjustment
  within the bounds of a given stretch)
* The user should be able to pan the view interactively.  This can be via
  middle clicking on the new center, click-and-drag, or scrolling (i.e. with
  touchpad a la what ginga does). The properties ``click_drag``,
  ``click_center``, and ``scroll`` can turn on/off these options
  (as does the "selection" mode).
* Zooming - if ``scroll_pan`` is False (probably the default), zooming is via
  the scroll wheel.
* "Selection mode" - see ``select_points`` method.
* If the user provides an NDData or fits input (assuming the fits file has
  valid WCS), if the cursor is not turned off it shows both the pixel
  coordinates and the WCS coordinates under the cursor.

Initially, *no* keyboard shortcuts should be implemented.  Eventually there
should be a clear mapping from keyboard shortcuts to methods, but until the
methods are stabilized, the keyboard shortcuts should be avoided.

Other requirements:

* Should be able to hanle ~4k x 4k images without significant performance
  lagging.
* Should be able to handle ~1000x markers without significant performance
  degredation.
* Stretch goal: hould be able to handle ~10k x 10k images acceptable
* Extra-stretchy goal: handle very large datasets using a "tiling" approach.
  This will presumably require different ``load_*`` functions, and more
  cleverness on the JS side.

A few more notes:

* We should be subclassing some kind of ipywidget,
  likely Box is the best choice.
* If we do that, then _repr_html is unnecessary (and undesirable), because
  the widget machinery will take care of it.
* Really like to avoid middle-click interactions, or at least I would like
  them to have an alias that works on a trackpad or a two-button mouse.
* I'd like a little more flexibility in adding markers (i.e., not necessarily
  require the use of a table, though that should be one way to do it).
* I also think we need at least minimal ability to change/set marker color,
  shape very early on.

"""
import ipywidgets as ipyw
from astropy.io import fits

from ginga.AstroImage import AstroImage
from ginga.web.jupyterw.ImageViewJpw import EnhancedCanvasView


class ImageWidget(EnhancedCanvasView):
    """
    Image widget for Jupyter notebook using Ginga viewer.

    .. todo:: Any property passed to constructor has to be valid keyword.

    Parameters
    ----------
    logger : obj or `None`
        Ginga logger. For example::

            from ginga.misc.log import get_logger
            logger = get_logger('my_viewer', log_stderr=False,
                                log_file='ginga.log', level=40)

    width, height : int
        Dimension of Jupyter notebook's image widget.

    """
    def __init__(self, logger=None, width=500, height=500):
        EnhancedCanvasView.__init__(self, logger=logger)

        jup_img = ipyw.Image(format='jpeg', width=width, height=height)
        self.set_widget(jup_img)

        # enable all possible keyboard and pointer operations
        self.get_bindings().enable_all(True)

        # coordinates display
        jup_coord = ipyw.HTML('<h3>coordinates show up here</h3>')
        self.add_callback('cursor-changed', self._widget_mouse_move, jup_coord)

        self._widget = ipyw.VBox([jup_img, jup_coord])

    @staticmethod
    def _widget_mouse_move(viewer, button, data_x, data_y, w):
        """
        Callback to display cursor position.
        """
        image = viewer.get_image()
        if image is not None:
            val = 'X: {:.2f}, Y:{:2.f}'
            if image.wcs is not None:
                ra, dec = image.pixtoradec(data_x, data_y)
                val += " (RA: {:.4f}, DEC: {:.4f}".format(ra, dec)
            w.value = val
        else:
            w.value = 'unknown'

    def _repr_html_(self):
        """
        Show widget in Jupyter notebook.
        """
        yield self._widget  # TODO: make this work

    def load_fits(self, fitsorfn):
        """
        Load a FITS file into the viewer.

        Parameters
        ----------
        fitsorfn : str or HDU
            Either a file name or an HDU (*not* an HDUList).
            If file name is given, WCS in primary header is automatically
            inherited. If a single HDU is given, WCS must be in the HDU
            header.

        """
        if isinstance(fitsorfn, str):
            image = AstroImage(logger=self.logger, inherit_primary_header=True)
            image.load_file(fitsorfn)
            self.set_image(image)

        elif isinstance(fitsorfn, (fits.ImageHDU, fits.CompImageHDU,
                                   fits.PrimaryHDU)):
            self.load_hdu(fitsorfn)

    def load_nddata(self, nddata):
        """
        Load an ``NDData`` object into the viewer.

        .. todo:: Add flag/masking support, etc.

        Parameters
        ----------
        nddata : `~astropy.nddata.NDData`
            ``NDData`` with image data and WCS.

        """
        image = AstroImage(logger=self.logger)
        image.set_data(nddata.data)
        image.set_wcs(nddata.wcs)
        self.set_image(image)

    def load_array(self, arr):
        """
        Load a 2D array into the viewer.

        .. note:: Use :meth:`load_nddata` for WCS support.

        Parameters
        ----------
        arr : array-like
            2D array.

        """
        self.load_data(arr)

    def center_on(self, x, y):
        """
        Centers the view on a particular point.
        """
        self.set_pan(x, y)

    def offset_to(self, dx, dy):
        """
        Moves the center to a point that is ``dx`` and ``dy``
        away from the current center.
        """
        pan_x, pan_y = self.get_pan()
        self.set_pan(pan_x + dx, pan_y + dy)

    @property
    def zoom_level(self):
        """
        Zoom level:

        * 1 means real-pixel-size.
        * 2 means zoomed out by a factor of 2
        * 0.5 means 2 screen pixels for 1 data pixel, etc.

        """
        return self.get_zoom()

    def zoom(self, val):
        """
        Zoom in or out by the given factor.

        Parameters
        ----------
        val : int
            The zoom level to zoom the image.
            Negative value to zoom out; positive to zoom in.

        """
        self.zoom_to(val)

#    def select_points(self):
#        """
#        Enter "selection mode".  This turns off ``click_drag``, and any click
#        will create a mark.
#
#        Later enhancements (second round): control the shape/size/color of the
#        selection marks a la the `add_marks` enhancement
#        """
#        raise NotImplementedError

#    def get_selection(self):
#        """
#        Return the locations of points from the most recent round of
#        selection mode.
#
#        Return value should be an astropy table, with "` and "y" columns
#        (or whatever the default column names are from ``add_marks``).  If WCS
#        is present, should *also* have a "coords" column with a `SkyCoord`
#        object.
#        """
#        raise NotImplementedError

#    def stop_selecting(self, clear_marks=True):
#        """
#        Just what it says on the tin.
#
#        If ``clear_marks`` is False, the selected points are kept as visible
#        marks until ``reset_marks`` is called.  Otherwise the marks disappear.
#        ``get_selection()`` should still work even if ``clear_markers`` is
#        False, up until the next ``select_points`` call happens.
#        """
#        raise NotImplementedError

#    @property
#    def is_selecting(self):
#        """
#        True if in selection mode, False otherwise.
#        """
#        raise NotImplementedError

#    def add_marks(self, table, x_colname='x', y_colname='y',
#                  skycoord_colname='coord'):
#        """
#        Creates markers in the image at given points.
#
#        Input is an astropy Table, and the column names for the x/y pixels will
#        be taken from the ``xcolname`` and ``ycolname`` kwargs.  If the
#        ``skycoord_colname`` is present, the table has the row, and WCS is
#        present on the image, mark the positions from the skycoord.  If both
#        skycoord *and* x/y columns are present, raise an error about not knowing
#        which to pick.
#
#
#        Later enhancements (second round): more table columns to control
#        size/style/color of marks, ``remove_mark`` to remove some but not all
#        of the marks, let the initial argument be a skycoord or a 2xN array.
#        """
#        raise NotImplementedError

#    def reset_marks(self):
#        """
#        Delete all marks
#        """
#        raise NotImplementedError

    # NOTE: Ginga has its own color distribution and mapping. Hmm...
    #@property
    #def stretch(self):
    #    """
    #    Settable.
    #
    #    One of the stretch objects from `astropy.visualization`, or something
    #    that matches that API.
    #
    #    Note that this is *not* the same as the
    #
    #    Might be better as getter/setter rather than property since it may be
    #    performance-intensive?
    #    """
    #    raise NotImplementedError

    # NOTE: Ginga has its own color distribution and mapping. Hmm...
    #def cuts(self):
    #    """
    #    Settable.
    #
    #    One of the cut objects from `astropy.visualization`, or something
    #    that matches that API
    #
    #    Might be better as getter/setter rather than property since it may be
    #    performance-intensive?
    #    """
    #    raise NotImplementedError

    # NOTE: This is already a Ginga attribute, cannot overwrite.
    #@property
    #def cursor(self):
    #    """
    #    Settable.
    #    If True, the pixel and possibly wcs is shown in the widget (see below),
    #    if False, the position is not shown.
    #
    #    Possible enhancement: instead of True/False, could be "top", "bottom",
    #    "left", "right", None/False
    #    """
    #    raise NotImplementedError

#    @property
#    def click_drag(self):
#        """
#        Settable.
#        If True, the "click-and-drag" mode is an available interaction for
#        panning.  If False, it is not.
#
#        Note that this should be automatically made `False` when selection mode
#        is activated.
#        """
#        raise NotImplementedError

#    @property
#    def click_center(self):
#        """
#        Settable.
#        If True, middle-clicking can be used to center.  If False, that
#        interaction is disabled.
#
#        In the future this might go from True/False to being a selectable
#        button. But not for the first round.
#        """
#        raise NotImplementedError

#    @property
#    def scroll_pan(self):
#        """
#        Settable.
#        If True, scrolling moves around in the image.  If False, scrolling
#        (up/down) *zooms* the image in and out.
#        """
#        raise NotImplementedError

    def save(self, filename):
        """
        Save out the current image view to given PNG filename.
        """
        self.save_rgb_image_as_file(filename)
