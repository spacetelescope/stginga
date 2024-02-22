"""
Background subtraction on an image.

**Plugin Type: Local**

``BackgroundSub`` is a local plugin, which means it is associated with a
channel.  An instance can be opened for each channel.

**Usage**

This plugin is used to calculate and subtract background value.
User draws a shape (e.g., annulus) to define the region from which background
is calculated. In the "Attributes" box, parameters controlling the calculation
can be adjusted. As user modifies the region or changes the parameters,
background value would be recalculated accordingly.
Optionally, if a data quality (DQ) extension is available, pixels marked as
"not good" can be excluded from calculations as well.
Subtraction parameters can be saved to a JSON file, which then can be reloaded.

Finally, if desired, the calculated background can be subtracted off
the displayed image in Ginga. However, the subtracted image only exists in an
in-memory cache in Ginga; if the cache fills up, Ginga will eventually eject
the image if it is not being viewed.
To save the subtracted image out to a different file, use the
:ref:`ginga:sec-plugins-global-saveimage` plugin in Ginga.
Currently, this only handles constant background, therefore unsuitable for
when background has a gradient or a pattern.

"""
# STDLIB
from datetime import datetime

# THIRD-PARTY
import numpy as np

# GINGA
from ginga.GingaPlugin import LocalPlugin
from ginga.gw import Widgets

# STGINGA
from stginga import utils
from stginga.plugins.local_plugin_mixin import HelpMixin, MEFMixin, ParamMixin

__all__ = ['BackgroundSub']


class BackgroundSub(HelpMixin, LocalPlugin, MEFMixin, ParamMixin):

    def __init__(self, fv, fitsimage):
        # superclass defines some variables for us, like logger
        super(BackgroundSub, self).__init__(fv, fitsimage)

        self.help_url = ('https://stginga.readthedocs.io/en/latest/stginga/'
                         'plugins_manual/backgroundsub.html')

        self.layertag = 'backgroundsub-canvas'
        self.bgsubtag = None

        self._bgtype_options = ['annulus', 'box', 'constant']
        self._algorithm_options = ['mean', 'median', 'mode']
        self._dummy_value = 0.0
        self._text_label = 'BGSub'
        self._text_label_offset = 4

        # User preferences. Some are just default values and can also be
        # changed by GUI.
        prefs = self.fv.get_preferences()
        settings = prefs.create_category('plugin_BackgroundSub')
        settings.load(onError='silent')
        self.bgsubcolor = settings.get('bgsubcolor', 'magenta')
        self.bgtype = settings.get('bgtype', 'annulus')
        self.annulus_width = settings.get('annulus_width', 10)
        self.algorithm = settings.get('algorithm', 'median')
        self.sigma = settings.get('sigma', 1.8)
        self.niter = settings.get('niter', 10)
        self.ignore_badpix = settings.get('ignore_bad_pixels', False)

        # FITS keywords and values from general config
        self.general_mef_settings(prefs)

        # Used for calculation
        self.xcen, self.ycen = self._dummy_value, self._dummy_value
        self.radius = 1  # Avoid zero-radius circle
        self.boxwidth, self.boxheight = self._dummy_value, self._dummy_value

        # Stores latest result
        self.bgval = self._dummy_value
        self._debug_str = ''

        self.dc = fv.get_draw_classes()

        # The rest are set by set_bgtype()
        canvas = self.dc.DrawingCanvas()
        canvas.enable_draw(True)
        canvas.enable_edit(False)
        canvas.set_drawtype(self.bgtype, color=self.bgsubcolor,
                            linestyle='dash')
        canvas.set_callback('draw-event', self.draw_cb)
        canvas.add_draw_mode('move', down=self.drag, move=self.drag,
                             up=self.update)
        canvas.set_draw_mode('draw')
        canvas.register_for_cursor_drawing(self.fitsimage)
        canvas.set_surface(self.fitsimage)
        self.canvas = canvas

        fv.add_callback('remove-image', lambda *args: self.redo())

        self.gui_up = False

    def build_gui(self, container):
        top = Widgets.VBox()
        top.set_border_width(4)

        vbox, sw, self.orientation = Widgets.get_oriented_box(container)
        vbox.set_border_width(4)
        vbox.set_spacing(2)

        fr = Widgets.Frame('Background Selection')
        captions = (('Type:', 'label', 'BG type', 'combobox'),
                    ('Move', 'radiobutton', 'Draw', 'radiobutton'))
        w, b = Widgets.build_info(captions)
        self.w.update(b)

        combobox = b.bg_type
        for name in self._bgtype_options:
            combobox.append_text(name)
        b.bg_type.set_index(self._bgtype_options.index(self.bgtype))
        b.bg_type.add_callback('activated', self.set_bgtype_cb)

        mode = self.canvas.get_draw_mode()
        b.move.set_state(mode == 'move')
        b.move.add_callback(
            'activated', lambda w, val: self.set_mode_cb('move', val))
        b.move.set_tooltip('Choose this to position region')
        b.draw.set_state(mode == 'draw')
        b.draw.add_callback(
            'activated', lambda w, val: self.set_mode_cb('draw', val))
        b.draw.set_tooltip('Choose this to draw a new region')

        fr.set_widget(w)
        vbox.add_widget(fr, stretch=0)

        fr = Widgets.Frame('Attributes')
        vbox2 = Widgets.VBox()
        self.w.bgtype_attr_vbox = Widgets.VBox()
        vbox2.add_widget(self.w.bgtype_attr_vbox, stretch=1)
        fr.set_widget(vbox2)
        vbox.add_widget(fr, stretch=0)

        captions = (('Background Value:', 'label',
                     'Background Value', 'entry'), )
        w, b = Widgets.build_info(captions, orientation=self.orientation)
        self.w.update(b)

        b.background_value.set_tooltip('Background value')
        b.background_value.set_text(str(self.bgval))
        b.background_value.add_callback(
            'activated', lambda w: self.set_constant_bg())
        b.background_value.set_editable(False)
        b.background_value.set_enabled(True)

        vbox.add_widget(w, stretch=0)

        self.build_param_gui(vbox)

        captions = (('Subtract', 'button', 'spacer1', 'spacer'), )
        w, b = Widgets.build_info(captions, orientation=self.orientation)
        self.w.update(b)

        b.subtract.set_tooltip('Subtract background')
        b.subtract.add_callback('activated', lambda w: self.sub_bg())
        b.subtract.set_enabled(False)

        vbox.add_widget(w, stretch=0)
        top.add_widget(sw, stretch=1)

        btns = Widgets.HBox()
        btns.set_border_width(4)
        btns.set_spacing(3)

        btn = Widgets.Button('Close')
        btn.add_callback('activated', lambda w: self.close())
        btns.add_widget(btn, stretch=0)
        btn = Widgets.Button('Help')
        btn.add_callback('activated', lambda w: self.help())
        btns.add_widget(btn, stretch=0)
        btns.add_widget(Widgets.Label(''), stretch=1)

        top.add_widget(btns, stretch=0)
        container.add_widget(top, stretch=1)

        # Populate default attributes frame
        self.set_bgtype(self.bgtype)

        self.gui_up = True

    def redo(self):
        if not self.gui_up:
            return True

        self.w.background_value.set_text(str(self._dummy_value))
        self.w.subtract.set_enabled(False)

        if self.bgtype not in ('annulus', 'box'):
            return True

        self.w.x.set_text(str(self.xcen))
        self.w.y.set_text(str(self.ycen))
        self._debug_str = f'x={self.xcen}, y={self.ycen}'

        image = self.fitsimage.get_image()
        if image is None:
            return True

        depth = image.get_depth()
        if depth == 3:
            self.logger.error(
                'Background calculation for RGB image is not supported')
            return True

        header = image.get_header()
        extname = header.get(self._ext_key, self._no_keyword).upper()

        # Only calculate for science extension.
        # If EXTNAME does not exist, just assume user knows best.
        if extname not in (self._sci_extname, self._no_keyword):
            self.logger.warn(
                f'Background calculation not possible for {extname} extension '
                f'in {image.get("name")}')
            return True

        try:
            obj = self.canvas.get_object_by_tag(self.bgsubtag)
        except KeyError:
            return True
        if obj.kind != 'compound':
            return True
        bg_obj = obj.objects[0]

        if self.bgtype == 'annulus':
            self.w.r.set_text(str(self.radius))
            self._debug_str += f', r={self.radius}, dannulus={self.annulus_width}'  # noqa: E501
        else:  # box
            self.w.box_w.set_text(str(self.boxwidth))
            self.w.box_h.set_text(str(self.boxheight))
            self._debug_str += f', w={self.boxwidth}, h={self.boxheight}'

        # Extract DQ info
        if self.ignore_badpix:
            dqsrc = self.load_dq(image, header)
        else:
            dqsrc = False

        bg_masked = image.cutout_shape(bg_obj)

        # Extract DQ mask
        if dqsrc is not False:
            dqsrc_masked = dqsrc.cutout_shape(bg_obj)
            mask = (~dqsrc_masked.mask) & (dqsrc_masked.data == 0)
        else:
            mask = ~bg_masked.mask

        # Extract background data
        try:
            bg_data = bg_masked.data[mask]
        except Exception as e:
            self.logger.warn(f'{e.__class__.__name__}: {repr(e)}')
            self.bgval = self._dummy_value
        else:
            self.bgval = utils.calc_stat(
                bg_data, sigma=self.sigma, niter=self.niter,
                algorithm=self.algorithm)

        self._debug_str += (
            f', bgval={self.bgval}, salgo={self.algorithm}, '
            f'sigma={self.sigma}, niter={self.niter}, '
            f'ignore_badpix={self.ignore_badpix}')
        self.logger.debug(self._debug_str)
        self.w.background_value.set_text(str(self.bgval))

        if self.bgval != 0:
            self.w.subtract.set_enabled(True)

        return True

    def update(self, canvas, event, data_x, data_y, viewer):
        try:
            obj = self.canvas.get_object_by_tag(self.bgsubtag)
        except Exception:
            return True

        if obj.kind == 'compound':
            bg_obj = obj.objects[0]
        else:
            bg_obj = obj

        if bg_obj.kind not in ('compound', 'annulus', 'rectangle'):
            return True

        try:
            canvas.delete_object_by_tag(self.bgsubtag, redraw=False)
        except Exception:
            pass

        # Update displayed values
        self.xcen = data_x
        self.ycen = data_y

        bg_obj.move_to_pt((data_x, data_y))
        tag = canvas.add(bg_obj)
        self.draw_cb(canvas, tag)
        return True

    def drag(self, canvas, event, data_x, data_y, viewer):
        try:
            obj = self.canvas.get_object_by_tag(self.bgsubtag)
        except Exception:
            return True

        if obj.kind == 'compound':
            bg_obj = obj.objects[0]
        else:
            bg_obj = obj

        if bg_obj.kind not in ('compound', 'annulus', 'rectangle'):
            return True

        bg_obj.move_to_pt((data_x, data_y))

        if obj.kind == 'compound':
            try:
                canvas.delete_object_by_tag(self.bgsubtag, redraw=False)
            except Exception:
                pass
            self.bgsubtag = canvas.add(bg_obj)
        else:
            canvas.redraw(whence=3)

        return True

    def draw_cb(self, canvas, tag):
        obj = canvas.get_object_by_tag(tag)
        if obj.kind not in ('annulus', 'rectangle'):
            return True
        canvas.delete_object_by_tag(tag, redraw=False)

        if self.bgsubtag:
            try:
                canvas.delete_object_by_tag(self.bgsubtag, redraw=False)
            except Exception:
                pass

        if self.bgtype not in ('annulus', 'box'):
            return True

        # Change background region appearance
        bg_obj = obj
        bg_obj.color = self.bgsubcolor
        bg_obj.linestyle = 'solid'

        if bg_obj.kind == 'annulus':
            bg_obj.sync_state()
            x = bg_obj.x
            y = bg_obj.y
            y2 = y + bg_obj.radius + bg_obj.width
            self.radius = max(bg_obj.radius, 1.0)
            bg_obj.radius = self.radius
        else:  # rectangle
            x, y = bg_obj.get_center_pt()
            self.boxwidth = np.abs(bg_obj.x2 - bg_obj.x1)
            self.boxheight = np.abs(bg_obj.y2 - bg_obj.y1)
            y2 = max(bg_obj.y1, bg_obj.y2)

        # Update displayed values
        self.xcen = x
        self.ycen = y

        lbl_obj = self.dc.Text(x, y2 + self._text_label_offset,
                               self._text_label, color=self.bgsubcolor)
        self.bgsubtag = canvas.add(self.dc.CompoundObject(bg_obj, lbl_obj))
        self.set_mode('move')
        return self.redo()

    def set_mode_cb(self, mode, tf):
        """Called when one of the Move/Draw radio buttons is selected."""
        if tf:
            self.canvas.set_draw_mode(mode)
        return True

    def set_mode(self, mode):
        self.canvas.set_draw_mode(mode)
        self.w.move.set_state(mode == 'move')
        self.w.draw.set_state(mode == 'draw')

    def set_bgtype_cb(self, w, index):
        bgtype = self._bgtype_options[index]
        return self.set_bgtype(bgtype)

    def set_bgtype(self, bgtype):
        if bgtype not in self._bgtype_options:
            self.logger.error(
                f'Undefined background selection type - {bgtype}')
            return True

        self.bgtype = bgtype

        # Remove old params
        self.w.bgtype_attr_vbox.remove_all()
        self.w.background_value.set_text(str(self._dummy_value))
        self.w.subtract.set_enabled(False)
        self.set_mode('draw')

        self.canvas.delete_all_objects()

        # Reset parameters
        self.xcen, self.ycen = self._dummy_value, self._dummy_value
        self.radius = 1  # Avoid zero-radius circle
        self.boxwidth, self.boxheight = self._dummy_value, self._dummy_value

        captions = [('X:', 'label', 'X', 'entry'),
                    ('Y:', 'label', 'Y', 'entry')]

        if bgtype == 'constant':
            self.canvas.enable_draw(False)
            self.w.background_value.set_editable(True)

        else:  # annulus, box
            self.canvas.enable_draw(True)

            if bgtype == 'annulus':
                self.canvas.set_drawtype(
                    'annulus', width=self.annulus_width, color=self.bgsubcolor,
                    linestyle='dash')
                captions += [('Radius:', 'label', 'r', 'entry'),
                             ('Annulus Width:', 'label',
                              'Annulus Width', 'entry')]
            else:  # box
                self.canvas.set_drawtype(
                    'rectangle', color=self.bgsubcolor, linestyle='dash')
                captions += [('Width:', 'label', 'box w', 'entry'),
                             ('Height:', 'label', 'box h', 'entry')]

            captions += [
                ('Algorithm:', 'label', 'Algorithm', 'combobox'),
                ('Sigma:', 'label', 'Sigma', 'entry'),
                ('Number of Iterations:', 'label', 'NIter', 'entry'),
                ('Ignore bad pixels', 'checkbutton')]
            w, b = Widgets.build_info(captions, orientation=self.orientation)
            self.w.update(b)

            b.x.set_tooltip('X of centroid')
            b.x.set_text(str(self.xcen))
            b.x.add_callback('activated', lambda w: self.set_xcen())

            b.y.set_tooltip('Y of centroid')
            b.y.set_text(str(self.ycen))
            b.y.add_callback('activated', lambda w: self.set_ycen())

            if bgtype == 'annulus':
                b.r.set_tooltip('Inner radius of annulus')
                b.r.set_text(str(self.radius))
                b.r.add_callback('activated', lambda w: self.set_radius())

                b.annulus_width.set_tooltip('Set annulus width manually')
                b.annulus_width.set_text(str(self.annulus_width))
                b.annulus_width.add_callback(
                    'activated', lambda w: self.set_annulus_width())

            else:  # box
                b.box_w.set_tooltip('Width of box')
                b.box_w.set_text(str(self.boxwidth))
                b.box_w.add_callback(
                    'activated', lambda w: self.set_boxwidth())

                b.box_h.set_tooltip('Height of box')
                b.box_h.set_text(str(self.boxheight))
                b.box_h.add_callback(
                    'activated', lambda w: self.set_boxheight())

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

            b.ignore_bad_pixels.set_tooltip(
                'Only use good pixels (DQ=0) for calculations')
            b.ignore_bad_pixels.set_state(self.ignore_badpix)
            b.ignore_bad_pixels.add_callback('activated', self.set_igbadpix)

            self.w.bgtype_attr_vbox.add_widget(w, stretch=1)
            self.w.background_value.set_editable(False)

        return True

    def set_xcen(self):
        """Reposition X."""
        try:
            self.xcen = float(self.w.x.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.get_object_by_tag(self.bgsubtag)
        except KeyError:
            return True
        if ((obj.kind != 'compound') or (len(obj.objects) < 2)):
            return True

        # Reposition all elements to match
        for c_obj in obj.objects:
            if hasattr(c_obj, 'y'):
                y = c_obj.y
            else:
                y = c_obj.get_center_pt()[1]
            c_obj.move_to_pt((self.xcen, y))

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_ycen(self):
        """Reposition Y."""
        try:
            self.ycen = float(self.w.y.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.get_object_by_tag(self.bgsubtag)
        except KeyError:
            return True
        if ((obj.kind != 'compound') or (len(obj.objects) < 2)):
            return True

        bg_obj = obj.objects[0]

        if bg_obj.kind == 'annulus':
            x = bg_obj.x
            y2 = self.ycen + bg_obj.radius + bg_obj.width
        else:  # rectangle
            x = bg_obj.get_center_pt()[0]
            y2 = self.ycen + 0.5 * self.boxheight

        # Reposition background region
        bg_obj.move_to_pt((x, self.ycen))

        # Reposition label to match
        obj.objects[1].y = y2 + self._text_label_offset

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_radius(self):
        """Set inner radius for annulus."""
        try:
            self.radius = float(self.w.r.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.get_object_by_tag(self.bgsubtag)
        except KeyError:
            return True
        if ((obj.kind != 'compound') or (len(obj.objects) < 2)):
            return True

        bg_obj = obj.objects[0]

        if bg_obj.kind != 'annulus':
            return True

        # Reposition inner circle
        bg_obj.radius = self.radius
        bg_obj.sync_state()

        # Reposition label to match
        obj.objects[1].y = (bg_obj.y + bg_obj.radius + bg_obj.width +
                            self._text_label_offset)

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_boxwidth(self):
        """Set width for box."""
        try:
            self.boxwidth = float(self.w.box_w.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.get_object_by_tag(self.bgsubtag)
        except KeyError:
            return True
        if ((obj.kind != 'compound') or (len(obj.objects) < 2)):
            return True

        bg_obj = obj.objects[0]

        if bg_obj.kind != 'rectangle':
            return True

        # Expand or shrink box around same center
        x = bg_obj.get_center_pt()[0]
        bg_obj.x1 = x - 0.5 * self.boxwidth
        bg_obj.x2 = bg_obj.x1 + self.boxwidth

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_boxheight(self):
        """Set height for box."""
        try:
            self.boxheight = float(self.w.box_h.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.get_object_by_tag(self.bgsubtag)
        except KeyError:
            return True
        if ((obj.kind != 'compound') or (len(obj.objects) < 2)):
            return True

        bg_obj = obj.objects[0]

        if bg_obj.kind != 'rectangle':
            return True

        # Expand or shrink box around same center
        y = bg_obj.get_center_pt()[1]
        bg_obj.y1 = y - 0.5 * self.boxheight
        bg_obj.y2 = bg_obj.y1 + self.boxheight

        # Reposition label to match
        obj.objects[1].y = bg_obj.y2 + self._text_label_offset

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_annulus_width(self):
        """Set annulus width."""
        try:
            self.annulus_width = float(self.w.annulus_width.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.get_object_by_tag(self.bgsubtag)
        except KeyError:
            return True
        if obj.kind != 'compound':
            return True

        bg_obj = obj.objects[0]
        if bg_obj.kind != 'annulus':
            return True

        # Reposition outer circle
        bg_obj.width = self.annulus_width
        bg_obj.sync_state()

        # Reposition label to match
        obj.objects[1].y = (bg_obj.y + bg_obj.radius + bg_obj.width +
                            self._text_label_offset)

        self.fitsimage.redraw(whence=3)
        return self.redo()

    def set_algorithm_cb(self, w, index):
        salgo = self._algorithm_options[index]
        return self.set_algorithm(salgo)

    def set_algorithm(self, salgo):
        self.logger.debug(f'BGSub algorithm: {salgo}')
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

    def set_igbadpix(self, w, val):
        self.ignore_badpix = val
        return self.redo()

    def set_constant_bg(self):
        self.w.subtract.set_enabled(False)
        try:
            self.bgval = float(self.w.background_value.get_text())
        except ValueError:
            return True
        if self.bgval != 0:
            self.w.subtract.set_enabled(True)
        self._debug_str = ''
        return True

    def sub_bg(self):
        """Subtract background, and update contents manager and display."""
        if self.bgval == 0:  # Nothing to do
            return True

        image = self.fitsimage.get_image()
        if image is None:
            self.logger.error('No image to subtract')
            return True

        new_data = image.get_data() - self.bgval
        s = f"{self.bgval} subtracted from {image.metadata['name']}"
        if self._debug_str:
            s += f' ({self._debug_str})'
        self.logger.info(s)

        # Change data in Ginga object and recalculate BG in annulus.
        # This issues a 'modified' callback, which sets timestamp and
        # calls redo().
        image.set_data(new_data, metadata=image.metadata)
        # self.fitsimage.auto_levels()

        # Store change history in metadata
        info = {'time_modified': datetime.utcnow(), 'reason_modified': s}
        self.fv.update_image_info(image, info)

        return True

    def params_dict(self):
        """Return current parameters as a dictionary."""
        pardict = {'plugin': str(self),
                   'bgtype': self.bgtype, 'bgval': self.bgval}

        image = self.fitsimage.get_image()
        if image is None:
            return pardict

        pardict['image'] = image.get('path')
        pardict['ext'] = image.get('idx')

        # Nothing else to add
        if self.bgtype == 'constant':
            return pardict

        pardict['xcen'] = self.xcen
        pardict['ycen'] = self.ycen
        pardict['algorithm'] = self.algorithm
        pardict['sigma'] = self.sigma
        pardict['niter'] = self.niter
        pardict['ignore_badpix'] = self.ignore_badpix

        if self.bgtype == 'annulus':
            pardict['radius'] = self.radius
            pardict['annulus_width'] = self.annulus_width
        else:  # box
            pardict['boxwidth'] = self.boxwidth
            pardict['boxheight'] = self.boxheight

        return pardict

    def ingest_params(self, pardict):
        """Ingest dictionary containing plugin parameters into plugin
        GUI and internal variables."""
        if ((pardict['plugin'] != str(self)) or
                (pardict['bgtype'] not in self._bgtype_options)):
            self.logger.error('Cannot ingest parameters')
            return True

        # Clear existing canvas
        if self.bgsubtag:
            try:
                self.canvas.delete_object_by_tag(self.bgsubtag, redraw=True)
            except Exception:
                pass

        # Ingest values from file. Retain current value if not found.

        self.algorithm = pardict.get('algorithm', self.algorithm)
        self.annulus_width = pardict.get('annulus_width', self.annulus_width)
        self.sigma = pardict.get('sigma', self.sigma)
        self.niter = pardict.get('niter', self.niter)
        self.ignore_badpix = pardict.get('ignore_badpix', self.ignore_badpix)

        self.set_bgtype(pardict['bgtype'])
        self.w.bg_type.set_index(self._bgtype_options.index(self.bgtype))

        if self.bgtype == 'constant':
            self.w.background_value.set_text(
                str(pardict.get('bgval', self._dummy_value)))
            self.set_constant_bg()
            return True

        # Only annulus or box beyond this point

        self.xcen = pardict.get('xcen', self.xcen)
        self.ycen = pardict.get('ycen', self.ycen)

        if self.bgtype == 'annulus':
            self.radius = pardict.get('radius', self.radius)

            bg_obj = self.dc.Annulus(
                x=self.xcen, y=self.ycen, radius=self.radius,
                width=self.annulus_width, color=self.bgsubcolor)
            y2 = self.ycen + self.radius + self.annulus_width

        else:  # box
            self.boxwidth = pardict.get('boxwidth', self.boxwidth)
            self.boxheight = pardict.get('boxheight', self.boxheight)

            x1 = self.xcen - (self.boxwidth * 0.5)
            x2 = x1 + self.boxwidth
            y1 = self.ycen - (self.boxheight * 0.5)
            y2 = y1 + self.boxheight
            bg_obj = self.dc.Rectangle(
                x1=x1, y1=y1, x2=x2, y2=y2, color=self.bgsubcolor)

        # Draw on canvas
        lbl_obj = self.dc.Text(self.xcen, y2 + self._text_label_offset,
                               self._text_label, color=self.bgsubcolor)
        self.bgsubtag = self.canvas.add(
            self.dc.CompoundObject(bg_obj, lbl_obj))

        return self.redo()

    def close(self):
        self.fv.stop_local_plugin(self.chname, str(self))
        return True

    def start(self):
        # insert canvas, if not already
        p_canvas = self.fitsimage.get_canvas()
        try:
            p_canvas.get_object_by_tag(self.layertag)
        except KeyError:
            # Add drawing layer
            p_canvas.add(self.canvas, tag=self.layertag)

        self.resume()

    def pause(self):
        self.canvas.ui_set_active(False)

    def resume(self):
        # turn off any mode user may be in
        self.modes_off()

        self.canvas.ui_set_active(True)
        self.fv.show_status('Draw a region with the left mouse button')

    def stop(self):
        # remove the canvas from the image
        p_canvas = self.fitsimage.get_canvas()
        try:
            p_canvas.delete_object_by_tag(self.layertag)
        except Exception:
            pass
        self.gui_up = False
        self.fv.show_status('')

    def __str__(self):
        """
        This method should be provided and should return the lower case
        name of the plugin.
        """
        return 'backgroundsub'


# Append module docstring with config doc for auto insert by Sphinx.
from ginga.util.toolbox import generate_cfg_example  # noqa
if __doc__ is not None:
    __doc__ += generate_cfg_example('plugin_BackgroundSub', package='stginga')
