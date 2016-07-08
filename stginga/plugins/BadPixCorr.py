"""Bad pixel correction local plugin for Ginga."""
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


class BadPixCorr(LocalPlugin, MEFMixin, ParamMixin):
    """Bad pixel correction on an image."""
    def __init__(self, fv, fitsimage):
        # superclass defines some variables for us, like logger
        super(BadPixCorr, self).__init__(fv, fitsimage)

        self.layertag = 'badpixcorr-canvas'
        self.bpixcorrtag = None

        self._corrtype_options = ['single', 'circular']
        self._filltype_options = ['annulus', 'constant', 'spline']
        self._algorithm_options = ['mean', 'median', 'mode']
        self._griddata_options = ['nearest', 'linear', 'cubic']
        self._dummy_value = 0.0
        self._text_label = 'BadPixCorr'
        self._text_label_offset = 4
        self._annulus_dr = 5

        # User preferences. Some are just default values and can also be
        # changed by GUI.
        prefs = self.fv.get_preferences()
        settings = prefs.createCategory('plugin_BadPixCorr')
        settings.load(onError='silent')
        self.bpixcorrcolor = settings.get('bpixcorrcolor', 'green')
        self.bpixannuluscolor = settings.get('bpixannuluscolor', 'magenta')
        self.corrtype = settings.get('corrtype', 'circular')
        self._point_radius = settings.get('point_radius', 5)
        self.filltype = settings.get('filltype', 'annulus')
        self.annulus_radius = settings.get('annulus_radius', 5)
        self.annulus_width = settings.get('annulus_width', 10)
        self.griddata_method = settings.get('griddata_method', 'linear')
        self.algorithm = settings.get('algorithm', 'median')
        self.sigma = settings.get('sigma', 1.8)
        self.niter = settings.get('niter', 10)
        self._dq_fixed_flag = settings.get('dq_fixed_flag', 0)

        # FITS keywords and values from general config
        self.general_mef_settings(prefs)

        # Used for calculation
        self.xcen, self.ycen = self._dummy_value, self._dummy_value
        self.radius = self._dummy_value

        # Stores latest result
        self.fillval = self._dummy_value

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

        fr = Widgets.Frame('Correction Type')
        captions = (('Bad Pix Region:', 'label', 'corr type', 'combobox'),
                    ('Fill From:', 'label', 'fill type', 'combobox'))
        w, b = Widgets.build_info(captions)
        self.w.update(b)

        for name in self._corrtype_options:
            b.corr_type.append_text(name)
        b.corr_type.set_index(self._corrtype_options.index(self.corrtype))
        b.corr_type.add_callback('activated', self.set_corrtype_cb)

        for name in self._filltype_options:
            b.fill_type.append_text(name)
        b.fill_type.set_index(self._filltype_options.index(self.filltype))
        b.fill_type.add_callback('activated', self.set_filltype_cb)

        fr.set_widget(w)
        vbox.add_widget(fr, stretch=0)

        fr = Widgets.Frame('Bad Pix Attributes')
        vbox2 = Widgets.VBox()
        self.w.corrtype_attr_vbox = Widgets.VBox()
        vbox2.add_widget(self.w.corrtype_attr_vbox, stretch=1)
        fr.set_widget(vbox2)
        vbox.add_widget(fr, stretch=0)

        fr = Widgets.Frame('Fill From Attributes')
        vbox2 = Widgets.VBox()
        self.w.filltype_attr_vbox = Widgets.VBox()
        vbox2.add_widget(self.w.filltype_attr_vbox, stretch=1)
        fr.set_widget(vbox2)
        vbox.add_widget(fr, stretch=0)

        self.build_param_gui(vbox)

        captions = (('Fix Bad Pixels', 'button', 'spacer1', 'spacer'), )
        w, b = Widgets.build_info(captions, orientation=self.orientation)
        self.w.update(b)

        b.fix_bad_pixels.set_tooltip('Replace bad pixels with fill value')
        b.fix_bad_pixels.add_callback('activated', lambda w: self.fix_bpix())
        b.fix_bad_pixels.set_enabled(False)

        vbox.add_widget(w, stretch=0)
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

        # Populate default attributes frame
        self.set_corrtype(self.corrtype)
        self.set_filltype(self.filltype)

        self.gui_up = True

    def instructions(self):
        self.tw.set_text("""You can correct a single pixel or a group of pixels within the defined circle. You can compute fill value using an annulus, use a constant fill value, or perform spline interpolation. All X and Y values must be 0-indexed.

To correct single pixel, right-click on the image. To correct pixels inside a circle, draw (or redraw) a region with the right mouse button. Click or drag left mouse button to reposition region. You can also manually fine-tune region parameters by entering values in the respective text boxes.

To calculate from annulus or use spline interpolation, enter values for the inner radius and width. For spline interpolation, all pixels inside the annulus will be used as basis data points for the given interpolation method; Otherwise, those pixels will be sigma-clipped and used to compute a constant fill value, using the given statistics parameters.

To replace bad pixels with a given value: Select "constant" from the "Fill From" drop-down box. Enter the fill value.

Click "Fix Bad Pixels" to replace the bad pixel(s). The associated DQ flags will also be updated accordingly.""")  # noqa

    def redo(self):
        """This updates circle/point values from drawing.
        It also calculates fill value but does not apply it.

        """
        if not self.gui_up:
            return True

        self.w.fix_bad_pixels.set_enabled(False)
        self.w.x.set_text(str(self.xcen))
        self.w.y.set_text(str(self.ycen))

        if self.corrtype == 'circular':
            self.w.r.set_text(str(self.radius))

        if self.filltype != 'spline':
            self.fillval = self._dummy_value
            self.w.fill_value.set_text(str(self.fillval))

        image = self.fitsimage.get_image()
        if image is None:
            return True

        depth = image.get_depth()
        if depth == 3:
            self.logger.error(
                'Bad pixel correction for RGB image is not supported')
            return True

        header = image.get_header()
        extname = header.get(self._ext_key, self._no_keyword).upper()

        # Only calculate for science extension.
        # If EXTNAME does not exist, just assume user knows best.
        if extname not in (self._sci_extname, self._no_keyword):
            self.logger.debug(
                'Bad pixel correction for science data not possible for {0} '
                'extension in {1}'.format(extname, image.get('name')))
            return True

        # Nothing to do
        if self.filltype == 'constant':
            self.w.fix_bad_pixels.set_enabled(True)
            return True

        try:
            obj = self.canvas.getObjectByTag(self.bpixcorrtag)
        except KeyError:
            return True
        if obj.kind != 'compound':
            return True
        sig_obj = obj.objects[1]

        # Just have to make sure signal region exists
        if self.filltype == 'spline':
            self.w.fix_bad_pixels.set_enabled(True)
            return True

        # Extract DQ info
        dqsrc = self.load_dq(image, header)

        sci_masked = image.cutout_shape(sig_obj)

        # Extract DQ mask
        if dqsrc is not False:
            dqsrc_masked = dqsrc.cutout_shape(sig_obj)
            mask = (~dqsrc_masked.mask) & (dqsrc_masked.data == 0)
        else:
            mask = ~sci_masked.mask

        # Extract annulus data
        try:
            sci_data = sci_masked[mask]
        except Exception as e:
            self.logger.error('{0}: {1}'.format(e.__class__.__name__, str(e)))
            return True

        # Calculate fill value from annulus
        self.fillval = utils.calc_stat(
            sci_data, sigma=self.sigma, niter=self.niter,
            algorithm=self.algorithm)
        self.w.fill_value.set_text(str(self.fillval))

        self.w.fix_bad_pixels.set_enabled(True)
        return True

    def update(self, canvas, button, data_x, data_y):
        try:
            obj = self.canvas.getObjectByTag(self.bpixcorrtag)
        except:
            return True

        if obj.kind == 'compound':
            bpx_obj = obj.objects[0]
        else:
            bpx_obj = obj

        if bpx_obj.kind not in ('circle', 'point'):
            return True

        try:
            canvas.deleteObjectByTag(self.bpixcorrtag, redraw=False)
        except:
            pass

        # Update displayed values
        self.xcen = data_x
        self.ycen = data_y

        bpx_obj.move_to(data_x, data_y)
        tag = canvas.add(bpx_obj)
        self.draw_cb(canvas, tag)
        return True

    def drag(self, canvas, button, data_x, data_y):
        try:
            obj = self.canvas.getObjectByTag(self.bpixcorrtag)
        except:
            return True

        if obj.kind == 'compound':
            bpx_obj = obj.objects[0]
        else:
            bpx_obj = obj

        if bpx_obj.kind not in ('circle', 'point'):
            return True

        bpx_obj.move_to(data_x, data_y)

        if obj.kind == 'compound':
            try:
                canvas.deleteObjectByTag(self.bpixcorrtag, redraw=False)
            except:
                pass
            self.bpixcorrtag = canvas.add(bpx_obj)
        else:
            canvas.redraw(whence=3)

        # Update displayed values
        self.xcen = data_x
        self.ycen = data_y

        return True

    def draw_cb(self, canvas, tag):
        obj = canvas.getObjectByTag(tag)
        if obj.kind not in ('circle', 'point'):
            return True
        canvas.deleteObjectByTag(tag, redraw=False)

        if self.bpixcorrtag:
            try:
                canvas.deleteObjectByTag(self.bpixcorrtag, redraw=False)
            except:
                pass

        # Round to nearest pixel
        x, y = round(obj.x), round(obj.y)
        obj.move_to(x, y)

        # Change bad pix region appearance
        obj.color = self.bpixcorrcolor
        obj.linestyle = 'solid'

        if obj.kind == 'circle':
            self.radius = obj.radius
            yt = y + self.radius + self._text_label_offset
        else:  # point
            obj.radius = self._point_radius
            yt = y + self._text_label_offset

        # Update displayed values
        self.xcen = x
        self.ycen = y

        # Annulus fill region
        f_obj = None
        if self.filltype in ('annulus', 'spline'):

            # Expand annulus inner radius if it is now too small
            if obj.kind == 'circle' and self.annulus_radius < self.radius:
                self.annulus_radius = self.radius + self._annulus_dr
                self.w.annulus_radius.set_text(str(self.annulus_radius))

            r1 = self.annulus_radius
            yt = y + r1 + self.annulus_width + self._text_label_offset
            f_obj = self.dc.Annulus(
                x=x, y=y, radius=r1, width=self.annulus_width,
                color=self.bpixannuluscolor)

        # Text label
        obj_lbl = self.dc.Text(
            x, yt, self._text_label, color=self.bpixcorrcolor)

        if f_obj is None:
            obj_final = self.dc.CompoundObject(obj, obj_lbl)
        else:
            obj_final = self.dc.CompoundObject(obj, f_obj, obj_lbl)

        self.bpixcorrtag = canvas.add(obj_final)
        return self.redo()

    def set_corrtype_cb(self, w, index):
        corrtype = self._corrtype_options[index]
        return self.set_corrtype(corrtype)

    def set_corrtype(self, corrtype):
        """This implicitly calls :meth:`draw_cb`."""
        # Remove old params
        self.w.corrtype_attr_vbox.remove_all()
        self.canvas.deleteAllObjects()

        if corrtype not in self._corrtype_options:
            self.logger.error(
                'Undefined bad pixel region type - {0}'.format(corrtype))
            return True

        self.corrtype = corrtype

        # Reset parameters
        self.xcen, self.ycen = self._dummy_value, self._dummy_value
        self.radius = self._dummy_value

        # Universal params
        captions = [('X:', 'label', 'X', 'entry'),
                    ('Y:', 'label', 'Y', 'entry')]

        if corrtype == 'circular':
            self.canvas.set_drawtype(
                'circle', color=self.bpixcorrcolor, linestyle='dash')
            captions += [('Radius:', 'label', 'r', 'entry')]
        else:  # single
            self.canvas.set_drawtype(
                'point', color=self.bpixcorrcolor)

        w, b = Widgets.build_info(captions, orientation=self.orientation)
        self.w.update(b)

        b.x.set_tooltip('X of centroid')
        b.x.set_text(str(self.xcen))
        b.x.add_callback('activated', lambda w: self.set_xcen())

        b.y.set_tooltip('Y of centroid')
        b.y.set_text(str(self.ycen))
        b.y.add_callback('activated', lambda w: self.set_ycen())

        if corrtype == 'circular':
            b.r.set_tooltip('Radius of circular correction region')
            b.r.set_text(str(self.radius))
            b.r.add_callback('activated', lambda w: self.set_radius())

        self.w.corrtype_attr_vbox.add_widget(w, stretch=1)
        return True

    def set_filltype_cb(self, w, index):
        filltype = self._filltype_options[index]
        return self.set_filltype(filltype)

    def set_filltype(self, filltype):
        if filltype not in self._filltype_options:
            self.logger.error(
                'Undefined fill from region type - {0}'.format(filltype))
            return True

        self.filltype = filltype

        # Get the compound object that sits on the canvas.
        has_drawing = True
        try:
            obj = self.canvas.getObjectByTag(self.bpixcorrtag)
        except KeyError:
            has_drawing = False
        if (has_drawing and
                (obj.kind != 'compound' or len(obj.objects) not in (2, 3))):
            has_drawing = False
        if has_drawing:
            obj_0 = obj.objects[0]  # Circle or point

        # Remove old params
        self.w.filltype_attr_vbox.remove_all()
        if has_drawing and self.bpixcorrtag:
            try:
                self.canvas.deleteObjectByTag(self.bpixcorrtag, redraw=False)
            except:
                pass

        if filltype in ('annulus', 'spline'):
            captions = [
                ('Annulus Radius:', 'label', 'Annulus Radius', 'entry'),
                ('Annulus Width:', 'label', 'Annulus Width', 'entry')]
            if filltype == 'annulus':
                captions += [
                    ('Algorithm:', 'label', 'Algorithm', 'combobox'),
                    ('Sigma:', 'label', 'Sigma', 'entry'),
                    ('Number of Iterations:', 'label', 'NIter', 'entry')]
            else:  # spline
                captions += [
                    ('Method:', 'label', 'Spline Method', 'combobox')]
        else:
            captions = []

        if filltype != 'spline':
            captions += [('Fill Value:', 'label', 'Fill Value', 'entry')]

        w, b = Widgets.build_info(captions, orientation=self.orientation)
        self.w.update(b)

        if filltype == 'annulus':
            for name in self._algorithm_options:
                b.algorithm.append_text(name)
            b.algorithm.set_index(
                self._algorithm_options.index(self.algorithm))
            b.algorithm.add_callback('activated', self.set_algorithm_cb)

            b.sigma.set_tooltip('Sigma for clipping')
            b.sigma.set_text(str(self.sigma))
            b.sigma.add_callback('activated', lambda w: self.set_sigma())

            b.niter.set_tooltip('Number of clipping iterations')
            b.niter.set_text(str(self.niter))
            b.niter.add_callback('activated', lambda w: self.set_niter())
        elif filltype == 'spline':
            for name in self._griddata_options:
                b.spline_method.append_text(name)
            b.spline_method.set_index(
                self._griddata_options.index(self.griddata_method))
            b.spline_method.add_callback(
                'activated', self.set_griddata_method_cb)

        if filltype in ('annulus', 'spline'):
            b.annulus_radius.set_tooltip('Set annulus inner radius manually')
            b.annulus_radius.set_text(str(self.annulus_radius))
            b.annulus_radius.add_callback(
                'activated', lambda w: self.set_annulus_radius())

            b.annulus_width.set_tooltip('Set annulus width manually')
            b.annulus_width.set_text(str(self.annulus_width))
            b.annulus_width.add_callback(
                'activated', lambda w: self.set_annulus_width())

            if has_drawing:
                yt = (self.ycen + self.annulus_radius + self.annulus_width +
                      self._text_label_offset)
                obj_ann = self.dc.Annulus(
                    x=self.xcen, y=self.ycen, radius=self.annulus_radius,
                    width=self.annulus_width, color=self.bpixannuluscolor)
                obj_lbl = self.dc.Text(
                    self.xcen, yt, self._text_label, color=self.bpixcorrcolor)
                obj_final = self.dc.CompoundObject(obj_0, obj_ann, obj_lbl)

        elif has_drawing:
            if obj_0.kind == 'circle':
                yt = self.ycen + obj_0.radius + self._text_label_offset
            else:  # point
                yt = self.ycen + self._text_label_offset

            obj_lbl = self.dc.Text(
                self.xcen, yt, self._text_label, color=self.bpixcorrcolor)
            obj_final = self.dc.CompoundObject(obj_0, obj_lbl)

        if filltype != 'spline':
            b.fill_value.set_tooltip('Fill value for bad pixels')
            b.fill_value.set_text(str(self.fillval))
            b.fill_value.add_callback(
                'activated', lambda w: self.set_constant_fillval())
            b.fill_value.set_enabled(True)

            if filltype == 'constant':
                self.w.fill_value.set_editable(True)
            else:
                self.w.fill_value.set_editable(False)

        self.w.filltype_attr_vbox.add_widget(w, stretch=1)

        if has_drawing:
            self.bpixcorrtag = self.canvas.add(obj_final)
            return self.redo()
        else:
            return True

    def set_xcen(self):
        try:
            self.xcen = float(self.w.x.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.bpixcorrtag)
        except KeyError:
            return True
        if obj.kind != 'compound' or len(obj.objects) not in (2, 3):
            return True

        # Reposition all elements to match
        for c_obj in obj.objects:
            if hasattr(c_obj, 'y'):
                y = c_obj.y
            else:
                y = c_obj.get_center_pt()[1]
            c_obj.move_to(self.xcen, y)

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_ycen(self):
        try:
            self.ycen = float(self.w.y.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.bpixcorrtag)
        except KeyError:
            return True
        if obj.kind != 'compound':
            return True
        n_obj = len(obj.objects)
        if n_obj not in (2, 3):
            return True

        # Reposition circle/point to match
        bpx_obj = obj.objects[0]
        bpx_obj.y = self.ycen

        # Reposition label to match
        c_obj = obj.objects[-1]
        if n_obj == 3:
            # Also reposition annulus
            ann_obj = obj.objects[1]
            ann_obj.move_to(ann_obj.x, self.ycen)
            c_obj.y = (self.ycen + ann_obj.radius + ann_obj.width +
                       self._text_label_offset)
        elif bpx_obj.kind == 'circle':  # circle without annulus
            c_obj.y = self.ycen + bpx_obj.radius + self._text_label_offset
        else:  # point only
            c_obj.y = self.ycen + self._text_label_offset

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_radius(self):
        try:
            self.radius = float(self.w.r.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.bpixcorrtag)
        except KeyError:
            return True
        if obj.kind != 'compound':
            return True
        n_obj = len(obj.objects)
        if n_obj not in (2, 3):
            return True

        # Do nothing if point is active, not circle
        bpx_obj = obj.objects[0]
        if bpx_obj.kind == 'point':
            return True

        # Resize circle
        bpx_obj.radius = self.radius

        # Reposition label
        if n_obj == 2:
            obj.objects[1].y = (self.ycen + self.radius +
                                self._text_label_offset)
        # Reposition annulus and label, if needed
        elif self.annulus_radius < self.radius:
            self.annulus_radius = self.radius + self._annulus_dr
            self.w.annulus_radius.set_text(str(self.annulus_radius))
            ann_obj = obj.objects[1]
            ann_obj.radius = self.annulus_radius
            ann_obj.sync_state()
            obj.objects[2].y = (ann_obj.y + ann_obj.radius + ann_obj.width +
                                self._text_label_offset)

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_annulus_radius(self):
        try:
            self.annulus_radius = float(self.w.annulus_radius.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.bpixcorrtag)
        except KeyError:
            return True
        if obj.kind != 'compound' or len(obj.objects) < 3:
            return True

        # Reposition annulus and label
        ann_obj = obj.objects[1]
        ann_obj.radius = self.annulus_radius
        ann_obj.sync_state()
        obj.objects[2].y = (ann_obj.y + ann_obj.radius + ann_obj.width +
                            self._text_label_offset)

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_annulus_width(self):
        try:
            self.annulus_width = float(self.w.annulus_width.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.bpixcorrtag)
        except KeyError:
            return True
        if ((obj.kind != 'compound') or (len(obj.objects) < 3)):
            return True

        # Reposition outer circle of annulus and label
        ann_obj = obj.objects[1]
        ann_obj.width = self.annulus_width
        ann_obj.sync_state()
        obj.objects[2].y = (ann_obj.y + ann_obj.radius + ann_obj.width +
                            self._text_label_offset)

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_griddata_method_cb(w, index):
        method = self._griddata_options[index]
        return self.set_griddata_method(method)

    def set_griddata_method(self, method):
        self.logger.debug('Grid data method: {0}'.format(method))
        self.griddata_method = method
        return True

    def set_algorithm_cb(self, w, index):
        salgo = self._algorithm_options[index]
        return self.set_algorithm(salgo)

    def set_algorithm(self, salgo):
        self.logger.debug('Stats algorithm: {0}'.format(salgo))
        self.algorithm = salgo
        return self.redo()

    def set_sigma(self):
        try:
            self.sigma = float(self.w.sigma.get_text())
        except ValueError:
            return True
        return self.redo()

    def set_niter(self):
        try:
            self.niter = int(self.w.niter.get_text())
        except ValueError:
            return True
        return self.redo()

    def set_constant_fillval(self):
        try:
            self.fillval = float(self.w.fill_value.get_text())
        except ValueError:
            pass
        return True

    def fix_bpix(self):
        """Fix bad pixels, and update contents manager and display."""
        image = self.fitsimage.get_image()
        if image is None:
            self.logger.error('No image to fix')
            return True

        depth = image.get_depth()
        if depth == 3:
            self.logger.error(
                'Bad pixel correction for RGB image is not supported')
            return True

        try:
            obj = self.canvas.getObjectByTag(self.bpixcorrtag)
        except KeyError:
            return True
        if obj.kind != 'compound':
            return True

        imname = image.get('name')
        header = image.get_header()
        data = image.get_data()
        s = 'Bad pixel(s) corrected for {0}; '.format(imname)

        if self.corrtype == 'circular':
            bpx_obj = obj.objects[0]
            mask = image.get_shape_mask(bpx_obj)
            s += 'x={0}, y={1}, r={2}'.format(
                self.xcen, self.ycen, self.radius)
        else:  # single pixel
            mask = np.zeros(data.shape, dtype=np.bool)
            xx = int(self.xcen)
            yy = int(self.ycen)
            mask[yy, xx] = True
            s += 'x={0}, y={1}'.format(xx, yy)

        npix = np.count_nonzero(mask)
        if npix == 0:
            self.logger.debug('No bad pixels to fix')
            return True

        if self.filltype in ('annulus', 'spline'):
            s += ', rannulus={0}, dannulus={1}'.format(
                self.annulus_radius, self.annulus_width)

        # Extract DQ info
        dqsrc = self.load_dq(image, header)
        if dqsrc is not False:
            dqdata = dqsrc.get_data()

        # Fill bad pixel(s) with spline interpolation
        if self.filltype == 'spline':
            sig_obj = obj.objects[1]
            basis_mask = image.get_shape_mask(sig_obj)

            # Only use good pixels
            if dqsrc is not False:
                basis_mask = basis_mask & (dqdata == 0)

            utils.interpolate_badpix(
                data, mask, basis_mask, method=self.griddata_method)
            s += ', spline method={0}'.format(self.griddata_method)
            if npix == 1:
                s += ', fillval={0:E}'.format(data[mask][0])

        # Use given fill value
        else:
            npix = np.count_nonzero(data[mask] != self.fillval)

            if npix == 0:
                self.logger.debug('No bad pixels to fix')
                return True

            data[mask] = self.fillval
            if self.filltype == 'annulus':
                s += ', salgo={0}, sigma={1}, niter={2}'.format(
                    self.algorithm, self.sigma, self.niter)
            s += ', fillval={0:E}'.format(self.fillval)

        s += ', npix={0}'.format(npix)
        self.logger.info(s)

        # Change data in Ginga object.
        # This issues a 'modified' callback, which sets timestamp and
        # calls redo().
        image.set_data(data, metadata=image.metadata)
        # self.fitsimage.auto_levels()

        # Store change history in metadata
        iminfo = self.chinfo.get_image_info(imname)
        iminfo.reason_modified = s

        # Update DQ extension
        if dqsrc is not False:
            dqname = dqsrc.get('name')
            npix = np.count_nonzero(dqdata[mask] != self._dq_fixed_flag)

            if npix == 0:
                self.logger.debug('No bad DQ flags to replace')
                return True

            # Switch to DQ image so ChangeHistory shows the log, see
            # https://github.com/spacetelescope/stginga/issues/113
            self.chinfo.switch_image(dqsrc)

            dqdata[mask] = self._dq_fixed_flag
            s = ('Bad pixel flag(s) replaced in {0}; dqflag={1}, '
                 'npix={2}'.format(dqname, self._dq_fixed_flag, npix))
            self.logger.info(s)

            # This issues a 'modified' callback, which sets timestamp and
            # calls redo().
            dqsrc.set_data(dqdata, metadata=dqsrc.metadata)

            # Store change history in metadata
            iminfo = self.chinfo.get_image_info(dqname)
            iminfo.reason_modified = s

        return True

    def params_dict(self):
        """Return current parameters as a dictionary."""
        pardict = {'plugin': str(self),
                   'corrtype': self.corrtype, 'filltype': self.filltype}

        image = self.fitsimage.get_image()
        if image is None:
            return pardict

        pardict['image'] = image.get('path')
        pardict['ext'] = image.get('idx')
        pardict['xcen'] = self.xcen
        pardict['ycen'] = self.ycen

        if self.corrtype == 'circular':
            pardict['radius'] = self.radius

        if self.filltype in ('annulus', 'spline'):
            pardict['annulus_radius'] = self.annulus_radius
            pardict['annulus_width'] = self.annulus_width

        if self.filltype == 'annulus':
            pardict['algorithm'] = self.algorithm
            pardict['sigma'] = self.sigma
            pardict['niter'] = self.niter
        elif self.filltype == 'spline':
            pardict['griddata_method'] = self.griddata_method

        if self.fillval != 'spline':
            pardict['fillval'] = self.fillval

        return pardict

    def ingest_params(self, pardict):
        """Ingest dictionary containing plugin parameters into plugin
        GUI and internal variables."""
        if ((pardict['plugin'] != str(self)) or
                (pardict['corrtype'] not in self._corrtype_options) or
                (pardict['filltype'] not in self._filltype_options)):
            self.logger.error('Cannot ingest parameters')
            return True

        # Clear existing canvas
        if self.bpixcorrtag:
            try:
                self.canvas.deleteObjectByTag(self.bpixcorrtag, redraw=True)
            except:
                pass

        # Ingest values from file. Retain current value if not found.

        self.set_corrtype(pardict['corrtype'])
        self.w.corr_type.set_index(self._corrtype_options.index(self.corrtype))

        self.xcen = pardict.get('xcen', self.xcen)
        self.ycen = pardict.get('ycen', self.ycen)
        self.radius = pardict.get('radius', self.radius)
        self.annulus_radius = pardict.get(
            'annulus_radius', self.annulus_radius)
        self.annulus_width = pardict.get('annulus_width', self.annulus_width)
        self.algorithm = pardict.get('algorithm', self.algorithm)
        self.sigma = pardict.get('sigma', self.sigma)
        self.niter = pardict.get('niter', self.niter)
        self.griddata_method = pardict.get(
            'griddata_method', self.griddata_method)
        self.fillval = pardict.get('fillval', self.fillval)

        self.set_filltype(pardict['filltype'])
        self.w.fill_type.set_index(self._filltype_options.index(self.filltype))

        # Draw on canvas
        if self.corrtype == 'circular':
            bpx_obj = self.dc.Circle(
                x=self.xcen, y=self.ycen, radius=self.radius,
                color=self.bpixcorrcolor)
            yt = self.ycen + self.radius + self._text_label_offset
        else:  # single
            bpx_obj = self.dc.Point(
                x=self.xcen, y=self.ycen, radius=self._point_radius,
                color=self.bpixcorrcolor)
            yt = self.ycen + self._text_label_offset

        if self.filltype in ('annulus', 'spline'):
            yt = (self.ycen + self.annulus_radius + self.annulus_width +
                  self._text_label_offset)
            sig_obj = self.dc.Annulus(
                x=self.xcen, y=self.ycen, radius=self.annulus_radius,
                width=self.annulus_width, color=self.bpixannuluscolor)
        else:
            sig_obj = None

        lbl_obj = self.dc.Text(
            self.xcen, yt, self._text_label, color=self.bpixcorrcolor)

        if sig_obj is None:
            final_obj = self.dc.CompoundObject(bpx_obj, lbl_obj)
        else:
            final_obj = self.dc.CompoundObject(bpx_obj, sig_obj, lbl_obj)

        self.bpixcorrtag = self.canvas.add(final_obj)
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
        return 'badpixcorr'


# Replace module docstring with config doc for auto insert by Sphinx.
# In the future, if we need the real docstring, we can append instead of
# overwrite.
__doc__ = generate_cfg_example('plugin_BadPixCorr', package='stginga')
