"""DQ flag inspection local plugin for Ginga."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

# STDLIB
import os

# THIRD-PARTY
import numpy as np
from astropy.utils.data import get_pkg_data_filename

# GINGA
from ginga import GingaPlugin
from ginga.gw import Widgets
from ginga.misc import Bunch
from ginga.RGBImage import RGBImage
from ginga.util.dp import masktorgb

# STGINGA
from stginga import utils

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


class DQInspect(GingaPlugin.LocalPlugin):
    """DQ inspection on an image."""
    def __init__(self, fv, fitsimage):
        # superclass defines some variables for us, like logger
        super(DQInspect, self).__init__(fv, fitsimage)

        self.layertag = 'dqinspect-canvas'
        self.pxdqtag = None

        self._cache_key = 'dq_by_flags'  # Ginga cannot use this anywhere else
        self._ndim = 2
        self._dummy_value = 0
        self._no_keyword = 'N/A'
        self._text_label = 'DQInspect'
        self._text_label_offset = 4

        # TODO: Could be improved and expanded?
        self._def_imdqcolors = ['blue', 'magenta', 'green']

        # TODO: Need better DQ definitions for supported instruments.
        # For DQ parser. Default defines only existing pkg data.
        self._def_parser = utils.DQParser(_def_tab)
        self._def_dqdict = {'NIRCAM': 'data/dqflags_jwst.txt',
                            'NIRSPEC': 'data/dqflags_jwst.txt',
                            'NIRISS': 'data/dqflags_jwst.txt',
                            'MIRI': 'data/dqflags_jwst.txt',
                            'ACS': 'data/dqflags_acs.txt',
                            'WFC3': 'data/dqflags_wfc3.txt',
                            'COS': 'data/dqflags_hstgen.txt',
                            'STIS': 'data/dqflags_hstgen.txt',
                            'WFPC2': 'data/dqflags_hstgen.txt'}

        # User preferences
        prefs = self.fv.get_preferences()
        self.settings = prefs.createCategory('plugin_DQInspect')
        self.settings.load(onError='silent')
        self.pxdqcolor = self.settings.get('pxdqcolor', 'red')

        # Internal cache
        self._dqparser = {}
        self._curpxmask = {}
        self._curshape = None

        # FITS keywords and values from general config
        gen_settings = prefs.createCategory('general')
        gen_settings.load(onError='silent')
        self._sci_extname = gen_settings.get('sciextname', 'SCI')
        self._dq_extname = gen_settings.get('dqextname', 'DQ')
        self._ext_key = gen_settings.get('extnamekey', 'EXTNAME')
        self._extver_key = gen_settings.get('extverkey', 'EXTVER')
        self._ins_key = gen_settings.get('instrumentkey', 'INSTRUME')

        # For GUI display of info and results
        self.xcen, self.ycen = self._dummy_value, self._dummy_value
        self._point_radius = 3

        # For DQ treeviews
        self.pxdqcolumns = [('Flag', 'FLAG'), ('Description', 'DESCRIP')]
        self.pxdqlist = None
        self.imdqcolumns = self.pxdqcolumns
        self.imdqllist = None

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

        # TODO: Need to test this when we have a plugin that modifies DQ.
        # Overrides redo() issued by image.set_data() by recalculating.
        fv.add_callback(
            'add-image-info', lambda *args: self.redo(ignore_image_cache=True))

        fv.add_callback('remove-image', lambda *args: self.redo())

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

        fr = Widgets.Expander('Instructions')
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
        b.x.add_callback('activated', lambda w: self.set_xcen())

        b.y.set_tooltip('Y of pixel')
        b.y.set_text(str(self.ycen))
        b.y.add_callback('activated', lambda w: self.set_ycen())

        b.dq.set_tooltip('DQ value of pixel')
        b.dq.set_text(self._no_keyword)

        # TODO: Need to find Ginga equivalent.
        #b.dq.widget.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        # Create the Treeview
        self.pxdqlist = Widgets.TreeView(auto_expand=True,
                                         sortable=True,
                                         selection='multiple',
                                         use_alt_row_color=True)
        self.pxdqlist.setup_table(self.pxdqcolumns, 1, 'FLAG')

        splitter = Widgets.Splitter('vertical')
        splitter.add_widget(w)
        splitter.add_widget(self.pxdqlist)
        fr.set_widget(splitter)
        vbox.add_widget(fr, stretch=1)

        fr = Widgets.Frame('Whole Image')
        captions = [('Number of pixels:', 'llabel', 'npix', 'llabel',
                     'spacer1', 'spacer')]
        w, b = Widgets.build_info(captions, orientation=orientation)
        self.w.update(b)

        b.npix.set_tooltip('Number of affected pixels')
        b.npix.set_text(self._no_keyword)

        # TODO: Need to find Ginga equivalent.
        #b.npix.widget.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)

        # Create the Treeview
        self.imdqlist = Widgets.TreeView(auto_expand=True,
                                         sortable=True,
                                         selection='multiple',
                                         use_alt_row_color=True)
        self.imdqlist.setup_table(self.imdqcolumns, 1, 'FLAG')
        self.imdqlist.add_callback('selected', self.mark_dqs_cb)

        splitter = Widgets.Splitter('vertical')
        splitter.add_widget(w)
        splitter.add_widget(self.imdqlist)
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

    def recreate_pxdq(self, dqparser, dqs, pixval):
        """Refresh single pixel results table with given data."""
        if not self.gui_up:
            return

        dqstr = self.settings.get('dqstr', 'long')
        treedict = Bunch.caselessDict()

        for row in dqs:
            flag = row[dqparser._dqcol]
            val = row[dqstr]
            treedict[str(flag)] = Bunch.Bunch(FLAG=flag, DESCRIP=val)

        self.pxdqlist.set_tree(treedict)
        #self.pxdqlist.sort_on_column(self.pxdqlist.leaf_idx)
        self.w.dq.set_text(str(pixval))

    def recreate_imdq(self, dqparser):
        """Refresh image DQ results table with given data."""
        if not self.gui_up:
            return

        dqstr = self.settings.get('dqstr', 'long')
        treedict = Bunch.caselessDict()

        for key in self._curpxmask:
            if len(self._curpxmask[key][0]) == 0:
                continue

            row = dqparser.tab[dqparser.tab[dqparser._dqcol] == key]
            flag = row[dqparser._dqcol][0]
            val = row[dqstr][0]
            treedict[str(flag)] = Bunch.Bunch(FLAG=flag, DESCRIP=val)

        self.imdqlist.set_tree(treedict)
        #self.imdqlist.sort_on_column(self.imdqlist.leaf_idx)

    def clear_pxdq(self, keep_loc=False):
        """Clear single pixel results, with the option to remember/forget
        coordinates as well."""
        if not self.gui_up:
            return

        if not keep_loc:
            self.w.x.set_text(self._dummy_value)
            self.w.y.set_text(self._dummy_value)

        self.w.dq.set_text(self._no_keyword)
        self.pxdqlist.clear()

    def clear_imdq(self, keep_cache=False):
        """Clear image DQ results, with the option to remember/forget
        internal cache."""
        if not keep_cache:
            self._curpxmask = None
            self._curshape = None

        if not self.gui_up:
            return

        self.w.npix.set_text(self._no_keyword)
        self.imdqlist.clear()

    def _load_dqparser(self, instrument):
        """Create new DQParser for given instrument."""
        dqdict = self.settings.get('dqdict', self._def_dqdict)

        if instrument not in dqdict:
            self.logger.warn(
                '{0} is not supported, using default'.format(instrument))
            return self._def_parser

        try:
            dqfile = get_pkg_data_filename(dqdict[instrument],
                                           package='stginga')
        except Exception as e:
            dqfile = dqdict[instrument]
            if os.path.isfile(dqfile):
                self.logger.info('Using external data {0}'.format(dqfile))
            else:
                self.logger.warn('{0} not found for {1}, using default'.format(
                    dqfile, instrument))
                dqfile = None
        else:
            self.logger.info('Using package data {0}'.format(dqfile))

        if dqfile is None:
            return self._def_parser

        try:
            dqp = utils.DQParser(dqfile)
        except Exception as e:
            self.logger.warn('Cannot extract DQ info from {0}, using '
                             'default'.format(dqfile))
            dqp = self._def_parser

        return dqp

    def redo(self, ignore_image_cache=False):
        """This updates DQ flags from canvas selection.

        Parameters
        ----------
        ignore_image_cache : bool
            Set to `True` to ignore cached parser results for the
            active image. This is useful if image buffer is modified.

        """
        if not self.gui_up:
            return True

        self.w.x.set_text(str(self.xcen))
        self.w.y.set_text(str(self.ycen))

        # Clear previous single-pixel results
        self.clear_pxdq(keep_loc=True)

        image = self.fitsimage.get_image()
        if image is None:
            return self._reset_imdq_on_error()

        depth = image.get_depth()
        if depth == 3:
            self.logger.error('DQ inspection for RGB image is not supported')
            return self._reset_imdq_on_error()

        header = image.get_header()
        extname = header.get(self._ext_key, self._no_keyword).upper()
        instrument = header.get(self._ins_key, None)

        # If displayed extension is not DQ, extract DQ array with same EXTVER
        if extname != self._dq_extname:
            # Non-DQ array is modified, which does not affect DQ, so no need
            # to reset cache no matter what is passed in.
            ignore_image_cache = False

            imfile = image.metadata['path']
            imname = image.metadata['name'].split('[')[0]
            extver = header.get(self._extver_key, self._dummy_value)

            if instrument != 'WFPC2':
                dq_extnum = (self._dq_extname, extver)
                dqname = '{0}[{1},{2}]'.format(imname, self._dq_extname, extver)
                dqsrc = utils.find_ext(imfile, dq_extnum)

            # Special handling for WFPC2, lots of assumptions
            else:
                dqsrc, imfile, dq_extnum, dqname = utils.find_wfpc2_dq(
                    imfile, imname, extver)

            # Do not continue if no DQ extension
            if not dqsrc:
                self.logger.error('{0} extension not found for '
                                  '{1}'.format(dq_extnum, imfile))
                return self._reset_imdq_on_error()

            chname = self.fv.get_channelName(self.fitsimage)
            dqsrc = utils.autoload_ginga_image(
                self.fv, chname, imfile, dq_extnum, dqname)

        # Use displayed image
        else:
            dqname = image.metadata['name']
            dqsrc = image

        data = dqsrc.get_data()
        if data.ndim != self._ndim:
            self.logger.error('Expected ndim={0} but data has '
                              'ndim={1}'.format(self._ndim, data.ndim))
            return self._reset_imdq_on_error()

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
            dqparser = self._load_dqparser(instrument)
            self._dqparser[instrument] = dqparser

        # Get cached results first, if available.
        # The cache is attached to image object, so that if image is closed etc,
        # the cache is automatically removed.
        if self._cache_key in dqsrc.metadata and not ignore_image_cache:
            self.logger.debug('Using cached DQ results for {0}'.format(dqname))
            pixmask_by_flag = dqsrc.get(self._cache_key)

        # Interpret DQ flags for all pixels.
        # Cache {flag: np_index}
        else:
            self.logger.debug('Interpreting all DQs for {0}...'.format(dqname))
            pixmask_by_flag = dqparser.interpret_array(data)
            dqsrc.metadata[self._cache_key] = pixmask_by_flag

        # Parse DQ into individual flag definitions
        ix = int(self.xcen)
        iy = int(self.ycen)
        if (0 <= iy < data.shape[0]) and (0 <= ix < data.shape[1]):
            pixval = data[iy, ix]
            dqs = dqparser.interpret_dqval(pixval)
            self.recreate_pxdq(dqparser, dqs, pixval)
        else:
            self.logger.warn('{0}[{1}, {2}] is out of range; data shape is '
                             '{3}'.format(dqname, iy, ix, data.shape))

        # No need to do the rest if image has not changed
        if pixmask_by_flag is self._curpxmask:
            return True

        # Populate a list of all valid DQ flags for that image.
        # Only list DQ flags present anywhere in the image.
        self._curpxmask = pixmask_by_flag
        self._curshape = data.shape
        self.clear_imdq(keep_cache=True)
        self.recreate_imdq(dqparser)

        return self.mark_dqs_cb(self.w, self.imdqlist.get_selected())

    def _reset_imdq_on_error(self):
        self.clear_imdq()
        return self.mark_dqs_cb(self.w, {})

    def mark_dqs_cb(self, w, res_dict):
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
            self.fitsimage.redraw()  # Need this to clear mask immediately
            return True

        # Recreate pixel marking and label
        p_obj = self.dc.Point(self.xcen, self.ycen, self._point_radius,
                              color=self.pxdqcolor)
        lbl_obj = self.dc.Text(self.xcen, self.ycen + self._text_label_offset,
                               self._text_label, color=self.pxdqcolor)

        # Pixel list is set by redo().
        # To save memory, composite mask is generated on the fly.
        imdqcolors = self.settings.get('imdqcolors', self._def_imdqcolors)
        n_color = len(imdqcolors)
        mask = np.zeros(self._curshape, dtype=np.bool)
        m_objs = []

        # Evenly distribute alpha between all individual masks
        n_key = len(res_dict)
        if n_key > 0:
            imdqalpha = 1.0 / n_key

        # Only valid DQs are selectable and passed in here
        for i, key in enumerate(res_dict):
            ikey = int(key)
            mask[self._curpxmask[ikey]] = True  # Composite mask for npix count

            # Mask only for that DQ flag, for individual color display
            cur_col = imdqcolors[i % n_color]
            cur_mask = np.zeros(self._curshape, dtype=np.bool)
            cur_mask[self._curpxmask[ikey]] = True
            m_objs.append(self.dc.Image(
                0, 0, masktorgb(cur_mask, color=cur_col, alpha=imdqalpha)))

            # TODO: Better way to report colors used? Cannot set as treeview
            # columns because treeview resets on update.
            self.logger.info('{0}: {1}'.format(key, cur_col))

        # Report number of affected pixels
        npix = np.count_nonzero(mask)
        if npix > 0:
            self.w.npix.set_text('{0}/{1} ({2:.3f}%)'.format(
                npix, mask.size, 100 * npix / mask.size))
        else:
            self.w.npix.set_text('0')

        # Generate canvas mask overlay
        m_objs += [p_obj, lbl_obj]
        self.pxdqtag = self.canvas.add(self.dc.CompoundObject(*m_objs))

        self.fitsimage.redraw()  # Need this to clear mask immediately
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
        return self.redo()

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
        self._reset_imdq_on_error()

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
        self._reset_imdq_on_error()

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
