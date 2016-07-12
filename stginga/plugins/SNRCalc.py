"""SNR and Surface background ratio (SBR) calculation local plugin for
Ginga.
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

# THIRD-PARTY
import numpy as np

# GINGA
from ginga.GingaPlugin import LocalPlugin
from ginga.gw import Widgets
from ginga.util.toolbox import generate_cfg_example

# STGINGA
from stginga import utils
from stginga.plugins.local_plugin_mixin import MEFMixin, ParamMixin

__all__ = []


class SNRCalc(LocalPlugin, MEFMixin, ParamMixin):
    """SNR and SBR calculations on an image."""
    def __init__(self, fv, fitsimage):
        # superclass defines some variables for us, like logger
        super(SNRCalc, self).__init__(fv, fitsimage)

        self.layertag = 'sbrcalc-canvas'
        self.sbrtag = None

        self._sigtype_options = ['box', 'circular', 'polygon']
        self._dummy_value = 0
        # self._default_bgradius_offset = 10
        self._text_label = 'SNR/SBR'
        self._text_label_offset = 4
        self._status_color_ready = 'grey'
        self._status_color_ok = 'green'
        self._status_color_notok = 'red'

        # User preferences
        prefs = self.fv.get_preferences()
        settings = prefs.createCategory('plugin_SNRCalc')
        settings.load(onError='silent')
        self.sbrcolor = settings.get('sbrcolor', 'blue3')
        self.sbrbgcolor = settings.get('sbrbgcolor', 'magenta')
        self.sigtype = settings.get('sigtype', 'circular')
        self.bgradius = settings.get('bgradius', 200)
        self.annulus_width = settings.get('annulus_width', 10)
        self.sigma = settings.get('sigma', 1.8)
        self.niter = settings.get('niter', 10)
        self.default_minsbr = settings.get('default_minsbr', 100)
        self.ignore_badpix = settings.get('ignore_bad_pixels', False)

        # FITS keywords and values from general config
        self.general_mef_settings(prefs)

        # Used for signal calculation
        self.xcen, self.ycen = self._dummy_value, self._dummy_value
        self.radius = self._dummy_value
        self.boxwidth, self.boxheight = self._dummy_value, self._dummy_value
        self._poly_pts = None

        # Used for background calculation
        self.bgxcen, self.bgycen = self._dummy_value, self._dummy_value

        # Used for results
        self._debug_str = ''

        self.dc = self.fv.getDrawClasses()

        canvas = self.dc.DrawingCanvas()
        canvas.enable_draw(True)
        canvas.enable_edit(False)
        canvas.set_callback('draw-event', self.draw_cb)
        canvas.set_callback('cursor-down', self.drag)
        canvas.set_callback('cursor-move', self.drag)
        canvas.set_callback('cursor-up', self.update)
        canvas.setSurface(self.fitsimage)
        self.canvas = canvas

        fv.add_callback('remove-image', lambda *args: self.redo())

        self.gui_up = False

    def build_gui(self, container):
        top = Widgets.VBox()
        top.set_border_width(4)

        vbox, sw, self.orientation = Widgets.get_oriented_box(container)
        vbox.set_border_width(4)
        vbox.set_spacing(2)

        msgFont = self.fv.getFont('sansFont', 12)
        tw = Widgets.TextArea(wrap=True, editable=False)
        tw.set_font(msgFont)
        self.tw = tw

        fr = Widgets.Expander('Instructions')
        fr.set_widget(tw)
        vbox.add_widget(fr, stretch=0)

        fr = Widgets.Frame('Signal Selection')
        captions = (('Type:', 'label', 'Sig type', 'combobox'), )
        w, b = Widgets.build_info(captions)
        self.w.update(b)

        combobox = b.sig_type
        for name in self._sigtype_options:
            combobox.append_text(name)
        b.sig_type.set_index(self._sigtype_options.index(self.sigtype))
        b.sig_type.add_callback('activated', self.set_sigtype_cb)

        fr.set_widget(w)
        vbox.add_widget(fr, stretch=0)

        fr = Widgets.Expander('Signal Attributes')
        vbox2 = Widgets.VBox()
        self.w.sigtype_attr_vbox = Widgets.VBox()
        vbox2.add_widget(self.w.sigtype_attr_vbox, stretch=1)
        fr.set_widget(vbox2)
        vbox.add_widget(fr, stretch=0)

        fr = Widgets.Expander('Background Annulus')
        captions = (
            ('BG X:', 'label', 'BG X', 'entry'),
            ('BG Y:', 'label', 'BG Y', 'entry'),
            ('Spacer6', 'spacer', 'Align with Centroid', 'button'),
            ('BG Radius:', 'label', 'BG r', 'entry'),
            ('BG Annulus Width:', 'label', 'Annulus Width', 'entry'),
            ('Sigma:', 'label', 'Sigma', 'entry'),
            ('Number of Iterations:', 'label', 'NIter', 'entry'))
        w, b = Widgets.build_info(captions, orientation=self.orientation)
        self.w.update(b)

        b.bg_x.set_tooltip('X of background annulus')
        b.bg_x.add_callback('activated', lambda w: self.set_bgxcen())

        b.bg_y.set_tooltip('Y of background annulus')
        b.bg_y.add_callback('activated', lambda w: self.set_bgycen())

        b.align_with_centroid.set_tooltip(
            'Set background X and Y to be same as centroid')
        b.align_with_centroid.add_callback(
            'activated', lambda w: self.align_centers())

        b.bg_r.set_tooltip('Inner radius of background annulus')
        b.bg_r.add_callback('activated', lambda w: self.set_bgradius())

        b.annulus_width.set_tooltip('Set background annulus width manually')
        b.annulus_width.add_callback(
            'activated', lambda w: self.set_annulus_width())

        b.sigma.set_tooltip('Sigma for clipping')
        b.sigma.add_callback('activated', lambda w: self.set_sigma())

        b.niter.set_tooltip('Number of clipping iterations')
        b.niter.add_callback('activated', lambda w: self.set_niter())

        fr.set_widget(w)
        vbox.add_widget(fr, stretch=0)

        captions = (
            ('Ignore bad pixels', 'checkbutton'),
            ('Min SNR:', 'label', 'Min SNR', 'llabel'),
            ('Mean SNR:', 'label', 'Mean SNR', 'llabel'),
            ('Max SNR:', 'label', 'Max SNR', 'llabel'),
            ('Spacer3', 'spacer'),
            ('Median signal:', 'label', 'sig med', 'llabel'),
            ('Background STDEV:', 'label', 'bg std', 'llabel'),
            ('Background mean:', 'label', 'bg mean', 'llabel'),
            ('SBR value:', 'label', 'SBR Value', 'llabel'),
            ('Min SBR:', 'label', 'Min SBR', 'llabel'),
            ('Spacer4', 'spacer'))
        w, b = Widgets.build_info(captions, orientation=self.orientation)
        self.w.update(b)

        b.ignore_bad_pixels.set_tooltip(
            'Only use good pixels (DQ=0) for calculations')
        b.ignore_bad_pixels.set_state(self.ignore_badpix)
        b.ignore_bad_pixels.add_callback('activated', self.set_igbadpix)

        for bitem, tt_text in (
                (b.min_snr, 'Min SNR in inner circle'),
                (b.mean_snr, 'Mean SNR in inner circle'),
                (b.max_snr, 'Max SNR in inner circle'),
                (b.sig_med, 'Median signal in inner circle'),
                (b.bg_std, 'Background std. dev. in annulus'),
                (b.bg_mean, 'Background mean in annulus'),
                (b.sbr_value, 'SBR value'),
                (b.min_sbr,
                 'Calculated SBR below this value raises red flag')):
            bitem.set_tooltip(tt_text)

        vbox.add_widget(w, stretch=0)

        self.sbr_status_label = Widgets.Label('', halign='center')
        self.sbr_status_label.set_font(self.fv.font18)
        vbox2 = Widgets.VBox()
        vbox2.add_widget(self.sbr_status_label)

        self.sbr_status_frame = Widgets.Frame('SBR Status')
        self.sbr_status_frame.set_widget(vbox2)
        vbox.add_widget(self.sbr_status_frame, stretch=0)

        self.build_param_gui(vbox)

        captions = (('Update HDR', 'button', 'spacer1', 'spacer'), )
        w, b = Widgets.build_info(captions, orientation=self.orientation)
        self.w.update(b)

        b.update_hdr.set_tooltip('Update header with SBR and SNR values')
        b.update_hdr.add_callback(
            'activated', lambda w: self.update_header())

        vbox.add_widget(w, stretch=0)

        btns = Widgets.HBox()
        btns.set_border_width(4)
        btns.set_spacing(3)

        btn = Widgets.Button('Close')
        btn.add_callback('activated', lambda w: self.close())
        btns.add_widget(btn, stretch=0)
        btns.add_widget(Widgets.Label(''), stretch=1)

        top.add_widget(sw, stretch=1)
        top.add_widget(btns, stretch=0)
        container.add_widget(top, stretch=1)

        # Populate default attributes frame, results, and status
        self._display_bg_params()
        self.set_sigtype(self.sigtype)

        self.gui_up = True

    def instructions(self):
        self.tw.set_text("""To calculate: Draw (or redraw) a signal region with the right mouse button. For polygon, while still holding right mouse button down, press "v" to change direction or "z" to undo. Click or drag left mouse button to reposition signal region. You can also manually fine-tune region parameters by entering values in the respective text boxes. Background annulus can be adjusted by manually entering its parameter values. All X and Y values must be 0-indexed.\n\nSignal is calculated from the inner region (box, circular, or polygon). Background is calculated from the annulus. SNR is calculated by dividing centroid data from {0} with those from {1} (background annulus is not used); It is set to 0 if image has no {1} extension. SBR is calculated by dividing median of centroid data with standard deviation of sigma-clipped background annulus (both from {0}). If SBR is less than given limit, status box will be {2} instead of {3}.""".format(self._sci_extname, self._err_extname, self._status_color_notok, self._status_color_ok))  # noqa

    def redo(self):
        """Calculate SBR and SNR."""
        if not self.gui_up:
            return True

        self._clear_results()

        self.w.x.set_text(str(self.xcen))
        self.w.y.set_text(str(self.ycen))
        self._debug_str = 'x={0}, y={1}'.format(self.xcen, self.ycen)

        image = self.fitsimage.get_image()
        if image is None:
            return True

        depth = image.get_depth()
        if depth == 3:
            self.logger.error(
                'SNR/SBR calculation for RGB image is not supported')
            return True

        header = image.get_header()
        extname = header.get(self._ext_key, self._no_keyword).upper()

        # Only calculate for science extension.
        # If EXTNAME does not exist, just assume user knows best.
        if extname not in (self._sci_extname, self._no_keyword):
            self.logger.warn(
                'SNR/SBR calculations not possible for {0} extension in '
                '{1}'.format(extname, image.get('name')))
            return True

        try:
            obj = self.canvas.getObjectByTag(self.sbrtag)
        except KeyError:
            return True
        if obj.kind != 'compound':
            return True
        sig_obj = obj.objects[0]
        bg_obj = obj.objects[1]

        if self.sigtype == 'box':
            self.w.box_w.set_text(str(self.boxwidth))
            self.w.box_h.set_text(str(self.boxheight))
            self._debug_str += ', w={0}, h={1}'.format(
                self.boxwidth, self.boxheight)
        elif self.sigtype == 'circular':
            self.w.r.set_text(str(self.radius))
            self._debug_str += ', r={0}'.format(self.radius)
        else:  # polygon
            self._poly_pts = sig_obj.points
            self._debug_str += ', pts={0}'.format(self._poly_pts)

        # Set min SBR here, in case subclass reimplement this method to use
        # image metadata as selection criteria.
        minsbr = self.set_minsbr()

        sci_masked = image.cutout_shape(sig_obj)
        bg_masked = image.cutout_shape(bg_obj)

        # Extract ERR info
        errsrc = self.load_err(image, header)

        # Extract DQ info
        if self.ignore_badpix:
            dqsrc = self.load_dq(image, header)
        else:
            dqsrc = False

        # Extract signal and background masks for SBR.
        # If DQ is present, use drawn regions with good pixels only.
        # Otherwise, use all drawn regions.
        if dqsrc is False:
            mask_sci = ~sci_masked.mask
            mask_bg = ~bg_masked.mask
        else:
            dq_sci_masked = dqsrc.cutout_shape(sig_obj)
            dq_bg_masked = dqsrc.cutout_shape(bg_obj)
            mask_sci = (~dq_sci_masked.mask) & (dq_sci_masked.data == 0)
            mask_bg = (~dq_bg_masked.mask) & (dq_bg_masked.data == 0)

        # Extract signal and background for SBR
        try:
            sci_data = sci_masked.data[mask_sci]
            bg_data = bg_masked.data[mask_bg]
        except Exception as e:
            self.logger.error('{0}: {1}'.format(e.__class__.__name__, str(e)))
            return

        # Calculate SBR
        sig_med = np.median(sci_data)
        bg_std = utils.calc_stat(bg_data, sigma=self.sigma, niter=self.niter,
                                 algorithm='stddev')
        bg_mean = utils.calc_stat(bg_data, sigma=self.sigma, niter=self.niter,
                                  algorithm='mean')
        self.w.sig_med.set_text(str(sig_med))
        self.w.bg_std.set_text(str(bg_std))
        self.w.bg_mean.set_text(str(bg_mean))
        self._debug_str += (
            ', bg_x={0}, bg_y={1}, bg_r={2}, dannulus={3}, '
            'sigma={4}, niter={5}, sig_med={6}, bg_std={7}, '
            'bg_mean={8}'.format(
                bg_obj.x, bg_obj.y, bg_obj.radius, bg_obj.width,
                self.sigma, self.niter, sig_med, bg_std, bg_mean))

        if bg_std != 0:
            sbrval = sig_med / bg_std
            self.w.sbr_value.set_text(str(sbrval))
            self._debug_str += ', sbr={0}, minsbr={1}'.format(sbrval, minsbr)

            # Update SBR status
            if sbrval > minsbr:
                self.set_sbr_status(ok_status=True)
            else:
                self.set_sbr_status(ok_status=False)

        if errsrc is not False:
            err_masked = errsrc.cutout_shape(sig_obj)

            # Extract signal mask for SNR.
            # Only use drawn region with non-zero ERR to avoid div by zero.
            # If DQ is present, also exclude non-good pixels.
            if dqsrc is False:
                mask_snr = (~err_masked.mask) & (err_masked.data != 0)
            else:
                mask_snr = ((~err_masked.mask) & (err_masked.data != 0) &
                            (dq_sci_masked.data == 0))

            # Extract science and error arrays for SNR
            try:
                snr_sci_data = sci_masked.data[mask_snr]
                snr_err_data = err_masked.data[mask_snr]
            except Exception as e:
                self.logger.error(
                    '{0}: {1}'.format(e.__class__.__name__, str(e)))
                return

            # Calculate SNR
            snr_data = snr_sci_data / snr_err_data
            snrmin = snr_data.min()
            snrmean = snr_data.mean()
            snrmax = snr_data.max()
            self.w.min_snr.set_text(str(snrmin))
            self.w.mean_snr.set_text(str(snrmean))
            self.w.max_snr.set_text(str(snrmax))
            self._debug_str += ', snrmin={0}, snrmean={1}, snrmax={2}'.format(
                snrmin, snrmean, snrmax)

        self.logger.debug(self._debug_str)
        self.w.update_hdr.set_enabled(True)
        return True

    def _display_bg_params(self):
        """Display background parameters on GUI."""
        self.w.bg_x.set_text(str(self.bgxcen))
        self.w.bg_y.set_text(str(self.bgycen))
        self.w.bg_r.set_text(str(self.bgradius))
        self.w.annulus_width.set_text(str(self.annulus_width))
        self.w.sigma.set_text(str(self.sigma))
        self.w.niter.set_text(str(self.niter))

    def _clear_results(self):
        # Clear previous results
        self._poly_pts = None
        dummy_text = str(self._dummy_value)
        self.w.min_snr.set_text(dummy_text)
        self.w.mean_snr.set_text(dummy_text)
        self.w.max_snr.set_text(dummy_text)
        self.w.sig_med.set_text(dummy_text)
        self.w.bg_std.set_text(dummy_text)
        self.w.bg_mean.set_text(dummy_text)
        self.w.sbr_value.set_text(dummy_text)
        self.w.min_sbr.set_text(dummy_text)

        # Reset status text/color
        self.set_sbr_status()

        # Disable update header button
        self.w.update_hdr.set_enabled(False)

    def set_sbr_status(self, ok_status=None):
        """Set a very obvious SBR status display.

        Parameters
        ----------
        ok_status : {`None`, `True`, `False`}
            Status to indicate "ready", "OK", or "not OK".

        """
        if ok_status is None:
            self.sbr_status_label.set_color(bg=self._status_color_ready)
            self.sbr_status_label.set_text(self._no_keyword)
        elif ok_status:
            self.sbr_status_label.set_color(bg=self._status_color_ok)
            self.sbr_status_label.set_text('OK')
        else:
            self.sbr_status_label.set_color(bg=self._status_color_notok)
            self.sbr_status_label.set_text('SBR too low!')

    def update(self, canvas, button, data_x, data_y):
        try:
            obj = self.canvas.getObjectByTag(self.sbrtag)
        except:
            return True

        if obj.kind == 'compound':
            sig_obj = obj.objects[0]
        else:
            sig_obj = obj

        if sig_obj.kind not in ('circle', 'polygon', 'rectangle'):
            return True

        try:
            canvas.deleteObjectByTag(self.sbrtag, redraw=False)
        except:
            pass

        # Update displayed values
        self.xcen = data_x
        self.ycen = data_y

        sig_obj.move_to(data_x, data_y)
        tag = canvas.add(sig_obj)
        self.draw_cb(canvas, tag)
        return True

    def drag(self, canvas, button, data_x, data_y):
        try:
            obj = self.canvas.getObjectByTag(self.sbrtag)
        except:
            return True

        if obj.kind == 'compound':
            sig_obj = obj.objects[0]
        else:
            sig_obj = obj

        if sig_obj.kind not in ('circle', 'polygon', 'rectangle'):
            return True

        sig_obj.move_to(data_x, data_y)

        if obj.kind == 'compound':
            try:
                canvas.deleteObjectByTag(self.sbrtag, redraw=False)
            except:
                pass
            self.sbrtag = canvas.add(sig_obj)
        else:
            canvas.redraw(whence=3)

        # Update displayed values
        self.xcen = data_x
        self.ycen = data_y

        return True

    def draw_cb(self, canvas, tag):
        obj = canvas.getObjectByTag(tag)
        if obj.kind not in ('circle', 'polygon', 'rectangle'):
            return True
        canvas.deleteObjectByTag(tag, redraw=False)

        if self.sbrtag:
            try:
                canvas.deleteObjectByTag(self.sbrtag, redraw=False)
            except:
                pass

        # Change signal region appearance
        obj.color = self.sbrcolor
        obj.linestyle = 'solid'

        if obj.kind == 'circle':
            x, y = obj.x, obj.y
            self.radius = obj.radius
        else:  # polygon, rectangle
            x, y = obj.get_center_pt()
            if obj.kind == 'rectangle':
                self.boxwidth = np.abs(obj.x2 - obj.x1)
                self.boxheight = np.abs(obj.y2 - obj.y1)

        # Update displayed values
        self.xcen = x
        self.ycen = y

        # Align annulus with centroid, if not initialized
        if self.bgxcen <= 0 or self.bgycen <= 0:
            self.bgxcen = self.xcen
            self.bgycen = self.ycen
            self.w.bg_x.set_text(str(self.bgxcen))
            self.w.bg_y.set_text(str(self.bgycen))

        # Draw background annulus and text label
        yt = (self.bgycen + self.bgradius + self.annulus_width +
              self._text_label_offset)
        bg_obj = self.dc.Annulus(
            x=self.bgxcen, y=self.bgycen, radius=self.bgradius,
            width=self.annulus_width, color=self.sbrbgcolor)
        lbl_obj = self.dc.Text(self.bgxcen, yt, self._text_label,
                               color=self.sbrcolor)

        self.sbrtag = canvas.add(self.dc.CompoundObject(obj, bg_obj, lbl_obj))
        return self.redo()

    def set_sigtype_cb(self, w, index):
        sigtype = self._sigtype_options[index]
        return self.set_sigtype(sigtype)

    def set_sigtype(self, sigtype):
        """Set signal region shape."""
        if sigtype not in self._sigtype_options:
            self.logger.error(
                'Undefined signal selection type - {0}'.format(sigtype))
            return True

        self.sigtype = sigtype

        # Remove old params
        self.w.sigtype_attr_vbox.remove_all()
        self._clear_results()

        self.canvas.deleteAllObjects()

        # Reset parameters
        self.xcen, self.ycen = self._dummy_value, self._dummy_value
        self.radius = self._dummy_value
        self.boxwidth, self.boxheight = self._dummy_value, self._dummy_value

        captions = [('X:', 'label', 'X', 'entry'),
                    ('Y:', 'label', 'Y', 'entry')]

        if sigtype == 'polygon':
            dtype = 'polygon'

        else:  # box, circular
            if sigtype == 'box':
                dtype = 'rectangle'
                captions += [('Width:', 'label', 'box w', 'entry'),
                             ('Height:', 'label', 'box h', 'entry')]
            else:  # circular
                dtype = 'circle'
                captions += [('Radius:', 'label', 'r', 'entry')]

        w, b = Widgets.build_info(captions, orientation=self.orientation)
        self.w.update(b)

        b.x.set_tooltip('X of centroid')
        b.x.set_text(str(self.xcen))
        b.x.add_callback('activated', lambda w: self.set_xcen())

        b.y.set_tooltip('Y of centroid')
        b.y.set_text(str(self.ycen))
        b.y.add_callback('activated', lambda w: self.set_ycen())

        if sigtype == 'box':
            b.box_w.set_tooltip('Width of box signal region')
            b.box_w.set_text(str(self.boxwidth))
            b.box_w.add_callback('activated', lambda w: self.set_boxwidth())

            b.box_h.set_tooltip('Height of box signal region')
            b.box_h.set_text(str(self.boxheight))
            b.box_h.add_callback('activated', lambda w: self.set_boxheight())

        elif sigtype == 'circular':
            b.r.set_tooltip('Radius of circular signal region')
            b.r.set_text(str(self.radius))
            b.r.add_callback('activated', lambda w: self.set_radius())

        self.w.sigtype_attr_vbox.add_widget(w, stretch=1)
        self.canvas.set_drawtype(dtype, color=self.sbrcolor, linestyle='dash')

        return True

    def align_centers(self):
        """Make background annulus center the same as signal region."""
        try:
            obj = self.canvas.getObjectByTag(self.sbrtag)
        except KeyError:
            return True
        if ((obj.kind != 'compound') or (len(obj.objects) < 3)):
            return True

        self.bgxcen = self.xcen
        self.bgycen = self.ycen
        self.w.bg_x.set_text(str(self.bgxcen))
        self.w.bg_y.set_text(str(self.bgycen))

        # Reposition annulus
        obj.objects[1].move_to(self.bgxcen, self.bgycen)

        # Reposition label
        yt = (self.bgycen + self.bgradius + self.annulus_width +
              self._text_label_offset)
        obj.objects[2].move_to(self.bgxcen, yt)

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_xcen(self):
        """Reposition X for signal region only."""
        try:
            self.xcen = float(self.w.x.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.sbrtag)
        except KeyError:
            return True
        if ((obj.kind != 'compound') or (len(obj.objects) < 3)):
            return True

        sig_obj = obj.objects[0]

        if sig_obj.kind == 'circle':
            sig_obj.x = self.xcen

        else:  # polygon, rectangle
            y = sig_obj.get_center_pt()[1]
            sig_obj.move_to(self.xcen, y)

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_ycen(self):
        """Reposition Y for signal region only."""
        try:
            self.ycen = float(self.w.y.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.sbrtag)
        except KeyError:
            return True
        if ((obj.kind != 'compound') or (len(obj.objects) < 3)):
            return True

        sig_obj = obj.objects[0]

        if sig_obj.kind == 'circle':
            sig_obj.y = self.ycen

        else:  # polygon, rectangle
            x = sig_obj.get_center_pt()[0]
            sig_obj.move_to(x, self.ycen)

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_radius(self):
        """Set radius for circular signal region."""
        try:
            self.radius = float(self.w.r.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.sbrtag)
        except KeyError:
            return True
        if ((obj.kind != 'compound') or (len(obj.objects) < 3)):
            return True

        sig_obj = obj.objects[0]

        if sig_obj.kind != 'circle':
            return True

        sig_obj.radius = self.radius

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_boxwidth(self):
        """Set width for box signal region."""
        try:
            self.boxwidth = float(self.w.box_w.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.sbrtag)
        except KeyError:
            return True
        if ((obj.kind != 'compound') or (len(obj.objects) < 3)):
            return True

        sig_obj = obj.objects[0]

        if sig_obj.kind != 'rectangle':
            return True

        x = sig_obj.get_center_pt()[0]
        sig_obj.x1 = x - 0.5 * self.boxwidth
        sig_obj.x2 = sig_obj.x1 + self.boxwidth

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_boxheight(self):
        """Set height for box signal region."""
        try:
            self.boxheight = float(self.w.box_h.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.sbrtag)
        except KeyError:
            return True
        if ((obj.kind != 'compound') or (len(obj.objects) < 3)):
            return True

        sig_obj = obj.objects[0]

        if sig_obj.kind != 'rectangle':
            return True

        y = sig_obj.get_center_pt()[1]
        sig_obj.y1 = y - 0.5 * self.boxheight
        sig_obj.y2 = sig_obj.y1 + self.boxheight

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_bgxcen(self):
        """Reposition X for background annulus and label."""
        try:
            self.bgxcen = float(self.w.bg_x.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.sbrtag)
        except KeyError:
            return True
        if ((obj.kind != 'compound') or (len(obj.objects) < 3)):
            return True

        # Reposition annulus and label
        for i in (1, 2):
            cobj = obj.objects[i]
            cobj.move_to(self.bgxcen, cobj.y)

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_bgycen(self):
        """Reposition Y for background annulus and label."""
        try:
            self.bgycen = float(self.w.bg_y.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.sbrtag)
        except KeyError:
            return True
        if ((obj.kind != 'compound') or (len(obj.objects) < 3)):
            return True

        # Reposition annulus
        ann_obj = obj.objects[1]
        ann_obj.move_to(ann_obj.x, self.bgycen)

        # Reposition label
        obj.objects[2].y = (ann_obj.y + ann_obj.radius + ann_obj.width +
                            self._text_label_offset)

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_bgradius(self):
        """Set background annulus inner circle radius."""
        try:
            self.bgradius = float(self.w.bg_r.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.sbrtag)
        except KeyError:
            return True
        if ((obj.kind != 'compound') or (len(obj.objects) < 3)):
            return True

        # Reposition annulus
        ann_obj = obj.objects[1]
        ann_obj.radius = self.bgradius
        ann_obj.sync_state()

        # Reposition label
        obj.objects[2].y = (ann_obj.y + ann_obj.radius + ann_obj.width +
                            self._text_label_offset)

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_annulus_width(self):
        """Set width of background annulus."""
        try:
            self.annulus_width = float(self.w.annulus_width.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.sbrtag)
        except KeyError:
            return True
        if ((obj.kind != 'compound') or (len(obj.objects) < 3)):
            return True

        # Reposition annulus
        ann_obj = obj.objects[1]
        ann_obj.width = self.annulus_width
        ann_obj.sync_state()

        # Reposition label
        obj.objects[2].y = (ann_obj.y + ann_obj.radius + ann_obj.width +
                            self._text_label_offset)

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_sigma(self):
        """Set sigma for background calculation."""
        try:
            self.sigma = float(self.w.sigma.get_text())
        except ValueError:
            return True
        return self.redo()

    def set_niter(self):
        """Set number of iterations for background calculation."""
        try:
            self.niter = int(self.w.niter.get_text())
        except ValueError:
            return True
        return self.redo()

    def set_igbadpix(self, w, val):
        self.ignore_badpix = val
        return self.redo()

    def set_minsbr(self):
        """Set SBR limit. This returns value from user preference until
        reimplemented properly by subclass."""
        val = self.default_minsbr
        self.w.min_sbr.set_text(str(val))
        return val

    def update_header(self):
        """Save values to header metadata."""
        image = self.fitsimage.get_image()
        if image is None:
            self.logger.error('No image to update')
            return True

        snrmin = float(self.w.min_snr.get_text())
        snrmean = float(self.w.mean_snr.get_text())
        snrmax = float(self.w.max_snr.get_text())
        sbrval = float(self.w.sbr_value.get_text())

        imname = image.get('name')
        hdr = image.metadata['header']
        hdr['SNRMIN'] = snrmin
        hdr['SNRMEAN'] = snrmean
        hdr['SNRMAX'] = snrmax
        hdr['SBR'] = sbrval

        s = 'SNR* and SBR keywords updated in {0}; {1}'.format(
            imname, self._debug_str)
        self.logger.info(s)

        # ----- Update Contents, History, and Header global plugins ----

        # This sets timestamp
        image.make_callback('modified')

        # Store change history in metadata
        iminfo = self.chinfo.get_image_info(imname)
        iminfo.reason_modified = s

        return True

    def params_dict(self):
        """Return current parameters as a dictionary."""
        pardict = {'plugin': str(self), 'sigtype': self.sigtype}

        image = self.fitsimage.get_image()
        if image is None:
            return pardict

        pardict['image'] = image.get('path')
        pardict['ext'] = image.get('idx')
        pardict['xcen'] = self.xcen
        pardict['ycen'] = self.ycen

        pardict['bgxcen'] = self.bgxcen
        pardict['bgycen'] = self.bgycen
        pardict['bgradius'] = self.bgradius
        pardict['annulus_width'] = self.annulus_width
        pardict['sigma'] = self.sigma
        pardict['niter'] = self.niter

        pardict['ignore_badpix'] = self.ignore_badpix

        pardict['min_snr'] = float(self.w.min_snr.get_text())
        pardict['mean_snr'] = float(self.w.mean_snr.get_text())
        pardict['max_snr'] = float(self.w.max_snr.get_text())

        pardict['sig_med'] = float(self.w.sig_med.get_text())
        pardict['bg_std'] = float(self.w.bg_std.get_text())
        pardict['bg_mean'] = float(self.w.bg_mean.get_text())
        pardict['sbr_value'] = float(self.w.sbr_value.get_text())
        pardict['min_sbr'] = float(self.w.min_sbr.get_text())
        pardict['sbr_status_label'] = self.sbr_status_label.get_text()

        if self.sigtype == 'box':
            pardict['boxwidth'] = self.boxwidth
            pardict['boxheight'] = self.boxheight
        elif self.sigtype == 'circular':
            pardict['radius'] = self.radius
        else:  # polygon
            pardict['poly_pts'] = self._poly_pts

        return pardict

    def ingest_params(self, pardict):
        """Ingest dictionary containing plugin parameters into plugin
        GUI and internal variables."""
        if ((pardict['plugin'] != str(self)) or
                (pardict['sigtype'] not in self._sigtype_options)):
            self.logger.error('Cannot ingest parameters')
            return True

        # Clear existing canvas
        if self.sbrtag:
            try:
                self.canvas.deleteObjectByTag(self.sbrtag, redraw=True)
            except:
                pass

        # Ingest values from file. Retain current value if not found.

        self.set_sigtype(pardict['sigtype'])
        self.w.sig_type.set_index(self._sigtype_options.index(self.sigtype))

        self.xcen = pardict.get('xcen', self.xcen)
        self.ycen = pardict.get('ycen', self.ycen)

        self.bgxcen = pardict.get('bgxcen', self.bgxcen)
        self.bgycen = pardict.get('bgycen', self.bgycen)
        self.bgradius = pardict.get('bgradius', self.bgradius)
        self.annulus_width = pardict.get('annulus_width', self.annulus_width)
        self.sigma = pardict.get('sigma', self.sigma)
        self.niter = pardict.get('niter', self.niter)
        self._display_bg_params()

        self.ignore_badpix = pardict.get('ignore_badpix', self.ignore_badpix)
        self.w.ignore_bad_pixels.set_state(self.ignore_badpix)

        if self.sigtype == 'box':
            self.boxwidth = pardict.get('boxwidth', self.boxwidth)
            self.boxheight = pardict.get('boxheight', self.boxheight)

            x1 = self.xcen - (self.boxwidth * 0.5)
            x2 = x1 + self.boxwidth
            y1 = self.ycen - (self.boxheight * 0.5)
            y2 = y1 + self.boxheight
            sig_obj = self.dc.Rectangle(
                x1=x1, y1=y1, x2=x2, y2=y2, color=self.sbrcolor)

        elif self.sigtype == 'circular':
            self.radius = pardict.get('radius', self.radius)

            sig_obj = self.dc.Circle(x=self.xcen, y=self.ycen,
                                     radius=self.radius, color=self.sbrcolor)

        else:  # polygon
            self._poly_pts = pardict.get('poly_pts', self._poly_pts)

            sig_obj = self.dc.Polygon(
                points=self._poly_pts, color=self.sbrcolor)

        # Draw on canvas
        yt = (self.bgycen + self.bgradius + self.annulus_width +
              self._text_label_offset)
        bg_obj = self.dc.Annulus(
            x=self.bgxcen, y=self.bgycen, radius=self.bgradius,
            width=self.annulus_width, color=self.sbrbgcolor)
        lbl_obj = self.dc.Text(
            self.bgxcen, yt, self._text_label, color=self.sbrcolor)
        self.sbrtag = self.canvas.add(self.dc.CompoundObject(
            sig_obj, bg_obj, lbl_obj))

        return self.redo()

    def close(self):
        self.fv.stop_local_plugin(self.chname, str(self))
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
        self.fv.showStatus('')

    def __str__(self):
        """
        This method should be provided and should return the lower case
        name of the plugin.
        """
        return 'snrcalc'


# Replace module docstring with config doc for auto insert by Sphinx.
# In the future, if we need the real docstring, we can append instead of
# overwrite.
__doc__ = generate_cfg_example('plugin_SNRCalc', package='stginga')
