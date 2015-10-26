"""DQ flag inspection local plugin for Ginga (Qt)."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from astropy.extern.six.moves import map

# STDLIB
import os
import warnings

# THIRD-PARTY
import numpy as np
from astropy.io import ascii, fits

# GINGA
from ginga import GingaPlugin, colors
from ginga.misc import Future, Widgets
from ginga.RGBImage import RGBImage
from ginga.qtw.QtHelp import QtCore, QtGui
from ginga.util.dp import masktorgb
from ginga.util.nstools import get_pkg_data_filename

__all__ = []

# Default DQ flags (HST)
_def_tab = """# TELESCOPE = HST
# INSTRUMENT = GENERIC
DQFLAG SHORT_DESCRIPTION LONG_DESCRIPTION
0      "OK"              "Good pixel"
1      "LOST"            "Lost during compression"
2      "FILLED"          "Replaced by fill value"
4      "BADPIX"          "Bad detector pixel or beyond aperture"
8      "MASKED"          "Masked by aperture feature"
16     "HOT"             "Hot pixel"
32     "CTE"             "CTE tail"
64     "WARM"            "Warm pixel"
128    "BADCOL"          "Bad column"
256    "SATURATED"       "Full-well or A-to-D saturated pixel"
512    "BADREF"          "Bad pixel in reference file (FLAT)"
1024   "TRAP"            "Charge trap"
2048   "ATODSAT"         "A-to-D saturated pixel"
4096   "CRDRIZ"          "Cosmic ray and detector artifact (AstroDrizzle, CR-SPLIT)"
8192   "CRREJ"           "Cosmic ray (CRREJ)"
16384  "USER"            "Manually flagged by user"
32768  "UNUSED"          "Not used"
"""
dqdict = {None: _def_tab}


class DQInspect(GingaPlugin.LocalPlugin):
    """DQ inspection on an image."""
    def __init__(self, fv, fitsimage):
        # superclass defines some variables for us, like logger
        super(DQInspect, self).__init__(fv, fitsimage)

        self.layertag = 'dqinspect-canvas'
        self.pxdqtag = None

        self._cache_key = 'dq_by_flags'
        self._ndim = 2
        self._dummy_value = 0
        self._no_keyword = 'N/A'
        self._text_label = 'DQInspect'
        self._text_label_offset = 4

        # User preferences and related internal cache
        prefs = self.fv.get_preferences()
        settings = prefs.createCategory('plugin_DQInspect')
        settings.load(onError='silent')
        self.dqstr = settings.get('dqstr', 'long')
        self.dqdict = settings.get('dqdict', dqdict)
        self.pxdqcolor = settings.get('pxdqcolor', 'red')
        self.imdqcolor = settings.get('imdqcolor', 'blue')
        self.imdqalpha = settings.get('imdqalpha', 1.0)
        self._dqparser = {}
        self._curpxmask = {}
        self._curshape = None

        # FITS keywords and values from general config
        gen_settings = prefs.createCategory('general')
        gen_settings.load(onError='silent')
        self._dq_extname = gen_settings.get('dqextname', 'DQ')
        self._ext_key = gen_settings.get('extnamekey', 'EXTNAME')
        self._extver_key = gen_settings.get('extverkey', 'EXTVER')
        self._ins_key = gen_settings.get('instrumentkey', 'INSTRUME')

        # For GUI display of info and results
        self.xcen, self.ycen = self._dummy_value, self._dummy_value
        self._point_radius = 3

        self.dc = self.fv.getDrawClasses()

        canvas = self.dc.DrawingCanvas()
        canvas.enable_draw(True)
        canvas.enable_edit(False)
        canvas.set_drawtype('point', color=self.pxdqcolor)
        canvas.set_callback('draw-event', self.draw_cb)
        canvas.set_callback('cursor-down', self.drag)
        canvas.set_callback('cursor-move', self.drag)
        canvas.set_callback('cursor-up', self.update)
        canvas.setSurface(self.fitsimage)
        self.canvas = canvas

        self.gui_up = False

    def build_gui(self, container):
        top = Widgets.VBox()
        top.set_border_width(4)

        vbox, sw, orientation = Widgets.get_oriented_box(container)
        vbox.set_border_width(4)
        vbox.set_spacing(2)

        msgFont = self.fv.getFont('sansFont', 12)
        tw = Widgets.TextArea(wrap=True, editable=False)
        tw.set_font(msgFont)
        self.tw = tw

        fr = Widgets.Frame('Instructions')
        vbox2 = Widgets.VBox()
        vbox2.add_widget(tw)
        vbox2.add_widget(Widgets.Label(''), stretch=1)
        fr.set_widget(vbox2)
        vbox.add_widget(fr, stretch=0)

        fr = Widgets.Frame('Single Pixel')
        captions = [('X:', 'label', 'X', 'entry'),
                    ('Y:', 'label', 'Y', 'entry'),
                    ('DQ Flag:', 'label', 'DQ', 'llabel')]
        w, b = Widgets.build_info(captions, orientation=orientation)
        self.w.update(b)

        b.x.set_tooltip('X of pixel')
        b.x.set_text(str(self.xcen))
        b.x.widget.editingFinished.connect(self.set_xcen)

        b.y.set_tooltip('Y of pixel')
        b.y.set_text(str(self.ycen))
        b.y.widget.editingFinished.connect(self.set_ycen)

        b.dq.set_tooltip('DQ value of pixel')
        b.dq.set_text(self._no_keyword)
        b.dq.widget.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        self.pxdqlist = QtGui.QListWidget()

        splitter = Widgets.Splitter('vertical')
        splitter.add_widget(w)
        splitter.widget.addWidget(self.pxdqlist)
        fr.set_widget(splitter)
        vbox.add_widget(fr, stretch=1)

        fr = Widgets.Frame('Whole Image')
        captions = [('Number of pixels:', 'llabel', 'npix', 'llabel',
                     'spacer1', 'spacer')]
        w, b = Widgets.build_info(captions, orientation=orientation)
        self.w.update(b)

        b.npix.set_tooltip('Number of affected pixels')
        b.npix.set_text(self._no_keyword)
        b.npix.widget.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        self.imdqlist = QtGui.QListWidget()
        self.imdqlist.setSelectionMode(
            QtGui.QAbstractItemView.ExtendedSelection)
        self.imdqlist.itemSelectionChanged.connect(self.mark_dqs)

        splitter = Widgets.Splitter('vertical')
        splitter.add_widget(w)
        splitter.widget.addWidget(self.imdqlist)
        fr.set_widget(splitter)
        vbox.add_widget(fr, stretch=1)

        top.add_widget(sw, stretch=1)

        btns = Widgets.HBox()
        btns.set_border_width(4)
        btns.set_spacing(3)

        btn = Widgets.Button('Close')
        btn.add_callback('activated', lambda w: self.close())
        btns.add_widget(btn, stretch=0)
        btns.add_widget(Widgets.Label(''), stretch=1)

        top.add_widget(btns, stretch=0)
        container.add_widget(top, stretch=1)

        self.gui_up = True

        # Populate fields based on active image
        self.redo()

    def instructions(self):
        self.tw.set_text("""It is important that you have all the possible DQ definition files defined in your plugin configuration file if you do not want to use default values! Otherwise, results might be inaccurate. The DQ definition file is select by {0} keyword in the image header.

To inspect a single pixel: Select a pixel by right-clicking on the image. Click or drag left mouse button to reposition pixel marker. You can also manually fine-tune the position by entering values in the respective text boxes. All X and Y values must be 0-indexed. DQ flags that went into the pixel will be listed along with their respective definitions.

To inspect the whole image: Select one or more desired DQ flags from the list. Affected pixel(s) will be marked on the image.""".format(
            self._ins_key, self._ext_key, self._dq_extname))

    def redo(self):
        """This updates DQ flags from canvas selection."""
        self.w.x.set_text(str(self.xcen))
        self.w.y.set_text(str(self.ycen))

        # Clear previous single-pixel results
        self.pxdqlist.clear()
        self.w.dq.set_text(self._no_keyword)

        image = self.fitsimage.get_image()
        depth = image.get_depth()
        if depth == 3:
            self.logger.error('DQ inspection for RGB image is not supported')
            return True

        header = image.get_header()
        extname = header.get(self._ext_key, self._no_keyword).upper()
        instrument = header.get(self._ins_key, None)

        # If displayed extension is not DQ, extract DQ array with same EXTVER
        if extname != self._dq_extname:
            imfile = image.metadata['path']
            imname = image.metadata['name'].split('[')[0]
            extver = header.get(self._extver_key, self._dummy_value)
            dq_extnum = (self._dq_extname, extver)

            with fits.open(imfile) as pf:
                dqsrc = dq_extnum in pf

            # Do not continue if no DQ extension
            if not dqsrc:
                self.logger.error(
                    '{0} extension not found for {1}'.format(dq_extnum, imfile))
                return True

            chname = self.fv.get_channelName(self.fitsimage)
            chinfo = self.fv.get_channelInfo(chname)
            dqname = '{0}[{1},{2}]'.format(imname, self._dq_extname, extver)

            if dqname in chinfo.datasrc:  # DQ already loaded
                self.logger.debug('Loading {0} from cache'.format(dqname))
                dqsrc = chinfo.datasrc[dqname]
            else:  # Force load DQ data
                self.logger.debug('Loading {0} from {1}'.format(dqname, imfile))
                dqsrc = self.fv.load_image(imfile, idx=dq_extnum)
                future = Future.Future()
                future.freeze(self.fv.load_image, imfile, idx=dq_extnum)
                dqsrc.set(path=imfile, idx=dq_extnum, name=dqname,
                          image_future=future)
                chinfo.datasrc[dqname] = dqsrc
                self.fv.make_callback('add-image', chname, dqsrc)

        # Use displayed image
        else:
            dqname = image.metadata['name']
            dqsrc = image

        data = dqsrc.get_data()
        if data.ndim != self._ndim:
            self.logger.error('Expected ndim={0} but data has '
                              'ndim={1}'.format(self._ndim, data.ndim))
            return True

        # Get cached DQ parser first, if available
        if instrument in self._dqparser:
            self.logger.debug(
                'Using cached DQ parser for {0}'.format(instrument))
            dqparser = self._dqparser[instrument]

        # Create new parser and cache it.
        # Look in package data first. If not found, assume external data.
        # If no data file provided, use default.
        else:
            self.logger.debug(
                'Creating new DQ parser for {0}'.format(instrument))

            if instrument in self.dqdict:
                dqfile = get_pkg_data_filename(self.dqdict[instrument])
                if dqfile:
                    self.logger.info('Using package data {0}'.format(dqfile))
                elif os.path.isfile(self.dqdict[instrument]):
                    dqfile = self.dqdict[instrument]
                    self.logger.info('Using external data {0}'.format(dqfile))
                else:
                    dqfile = _def_tab
                    self.logger.warn(
                        '{0} not found for {1}, using default'.format(
                            self.dqdict[instrument], instrument))
            else:
                dqfile = _def_tab
                self.logger.warn(
                    '{0} is not supported, using default'.format(instrument))

            dqparser = DQParser(dqfile)
            self._dqparser[instrument] = dqparser

        # Get cached results first, if available
        if self._cache_key in dqsrc.metadata:
            self.logger.debug('Using cached DQ results for {0}'.format(dqname))
            pixmask_by_flag = dqsrc.get(self._cache_key)

        # Interpret DQ flags for all pixels.
        # Cache {flag: np_index}
        else:
            self.logger.debug('Interpreting all DQs for {0}...'.format(dqname))
            pixmask_by_flag = dqparser.interpret_array(data)
            dqsrc.metadata[self._cache_key] = pixmask_by_flag

        # Parse DQ into individual flag definitions
        pixval = data[int(self.ycen), int(self.xcen)]
        dqs = dqparser.interpret_dqval(pixval)
        self.w.dq.set_text(str(pixval))
        for row in dqs:
            item = QtGui.QListWidgetItem(
                '{0:<5d}\t{1}'.format(row[dqparser._dqcol], row[self.dqstr]))
            self.pxdqlist.addItem(item)

        # No need to do the rest if image has not changed
        if pixmask_by_flag is self._curpxmask:
            return True

        # Populate a list of all valid DQ flags for that image.
        # Only list DQ flags present anywhere in the image.
        self.imdqlist.clear()
        self.w.npix.set_text(self._no_keyword)
        self._curpxmask = pixmask_by_flag
        self._curshape = data.shape
        for key in sorted(self._curpxmask):
            if len(self._curpxmask[key][0]) == 0:
                continue
            row = dqparser.tab[dqparser.tab[dqparser._dqcol] == key]
            item = QtGui.QListWidgetItem('{0:<5d}\t{1}'.format(
                row[dqparser._dqcol][0], row[self.dqstr][0]))
            self.imdqlist.addItem(item)

        return True

    def mark_dqs(self):
        """Mark all pixels affected by selected DQ flag(s)."""
        if not self.gui_up:
            return True

        # Clear existing canvas
        if self.pxdqtag:
            try:
                self.canvas.deleteObjectByTag(self.pxdqtag, redraw=False)
            except:
                pass

        if self._curshape is None:
            return True

        # Recreate pixel marking and label
        p_obj = self.dc.Point(self.xcen, self.ycen, self._point_radius,
                              color=self.pxdqcolor)
        lbl_obj = self.dc.Text(self.xcen, self.ycen + self._text_label_offset,
                               self._text_label, color=self.pxdqcolor)

        # Pixel list is set by redo().
        # To save memory, composite mask is generated on the fly.
        mask = np.zeros(self._curshape, dtype=np.bool)
        selected_items = self.imdqlist.selectedItems()
        for item in selected_items:
            key = int(str(item.text()).split()[0])
            mask[self._curpxmask[key]] = True

        # Generate canvas mask overlay
        npix = np.count_nonzero(mask)
        if npix > 0:
            self.logger.debug('Overlaying mask for {0} pixels'.format(npix))
            self.w.npix.set_text('{0}/{1} ({2:.3f}%)'.format(
                npix, mask.size, 100 * npix / mask.size))
            m_obj = self.dc.Image(0, 0,
                masktorgb(mask, color=self.imdqcolor, alpha=self.imdqalpha))
            self.pxdqtag = self.canvas.add(
                self.dc.CompoundObject(m_obj, p_obj, lbl_obj))
        else:
            self.w.npix.set_text('0')
            self.pxdqtag = self.canvas.add(
                self.dc.CompoundObject(p_obj, lbl_obj))

        return True

    def update(self, canvas, button, data_x, data_y):
        try:
            obj = self.canvas.getObjectByTag(self.pxdqtag)
        except:
            return True

        if obj.kind == 'compound':
            pix_obj = obj.objects[0]
            for c_obj in obj.objects[1:]:
                if c_obj.kind == 'point':
                    pix_obj = c_obj
        else:
            pix_obj = obj

        if pix_obj.kind != 'point':
            return True

        try:
            canvas.deleteObjectByTag(self.pxdqtag, redraw=False)
        except:
            pass

        # Update displayed values
        self.xcen = data_x
        self.ycen = data_y

        pix_obj.move_to(data_x, data_y)
        tag = canvas.add(pix_obj)
        self.draw_cb(canvas, tag)
        return True

    def drag(self, canvas, button, data_x, data_y):
        try:
            obj = self.canvas.getObjectByTag(self.pxdqtag)
        except:
            return True

        if obj.kind == 'compound':
            pix_obj = obj.objects[0]
            for c_obj in obj.objects[1:]:
                if c_obj.kind == 'point':
                    pix_obj = c_obj
        else:
            pix_obj = obj

        if pix_obj.kind != 'point':
            return True

        pix_obj.move_to(data_x, data_y)

        if obj.kind == 'compound':
            try:
                canvas.deleteObjectByTag(self.pxdqtag, redraw=False)
            except:
                pass
            self.pxdqtag = canvas.add(pix_obj)
        else:
            canvas.redraw(whence=3)

        # Update displayed values
        self.xcen = data_x
        self.ycen = data_y

        return True

    def draw_cb(self, canvas, tag):
        obj = canvas.getObjectByTag(tag)
        if obj.kind != 'point':
            return True
        canvas.deleteObjectByTag(tag, redraw=False)

        if self.pxdqtag:
            try:
                canvas.deleteObjectByTag(self.pxdqtag, redraw=False)
            except:
                pass

        # Round to nearest pixel
        x, y = round(obj.x), round(obj.y)
        obj.move_to(x, y)

        # Change bad pix region appearance
        obj.radius = self._point_radius

        # Text label
        yt = y + self._text_label_offset
        obj_lbl = self.dc.Text(
            x, yt, self._text_label, color=self.pxdqcolor)

        # Update displayed values
        self.xcen = x
        self.ycen = y

        self.pxdqtag = canvas.add(self.dc.CompoundObject(obj, obj_lbl))
        self.redo()
        return self.mark_dqs()

    def set_xcen(self):
        try:
            self.xcen = float(self.w.x.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.pxdqtag)
        except KeyError:
            return True
        if obj.kind != 'compound':
            return True

        # Reposition all elements to match
        for c_obj in obj.objects:
            if c_obj.kind != 'image':
                c_obj.move_to(self.xcen, c_obj.y)

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_ycen(self):
        try:
            self.ycen = float(self.w.y.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.pxdqtag)
        except KeyError:
            return True
        if obj.kind != 'compound':
            return True

        for c_obj in obj.objects:
            # Reposition point to match
            if c_obj.kind == 'point':
                c_obj.y = self.ycen
            # Reposition label to match
            elif c_obj.kind != 'image':
                c_obj.y = self.ycen + self._text_label_offset

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def close(self):
        chname = self.fv.get_channelName(self.fitsimage)
        self.fv.stop_local_plugin(chname, str(self))
        return True

    def start(self):
        self.instructions()

        # insert canvas, if not already
        p_canvas = self.fitsimage.get_canvas()
        try:
            obj = p_canvas.getObjectByTag(self.layertag)
        except KeyError:
            # Add drawing layer
            p_canvas.add(self.canvas, tag=self.layertag)

        self.resume()

    def pause(self):
        self.canvas.ui_setActive(False)

    def resume(self):
        # turn off any mode user may be in
        self.modes_off()

        self.canvas.ui_setActive(True)
        self.fv.showStatus('Draw a region with the right mouse button')

    def stop(self):
        # remove the canvas from the image
        p_canvas = self.fitsimage.get_canvas()
        try:
            p_canvas.deleteObjectByTag(self.layertag)
        except:
            pass
        self.gui_up = False
        self.fv.showStatus("")

    def __str__(self):
        """
        This method should be provided and should return the lower case
        name of the plugin.
        """
        return 'dqinspect'


# -------------------------------------------------------------------- #
# STScI reftools.interpretdq.DQParser class modified for Ginga plugin. #
# -------------------------------------------------------------------- #

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
