"""Background subtraction local plugin for Ginga (Qt)."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

# STDLIB
import warnings

# THIRD-PARTY
import numpy as np

# GINGA
from ginga import GingaPlugin
from ginga.canvas.types.astro import Annulus
from ginga.misc import Widgets

# LOCAL
QUIP_LOG = None
try:
    from stginga.utils import calc_stat
except ImportError:
    warnings.warn('stginga not found, using np.mean() for statistics')

    def calc_stat(*args, **kwargs):
        return np.mean(args[0])

__all__ = []


class BackgroundSub(GingaPlugin.LocalPlugin):
    """Background subtraction on an image."""
    def __init__(self, fv, fitsimage):
        # superclass defines some variables for us, like logger
        super(BackgroundSub, self).__init__(fv, fitsimage)

        self.layertag = 'backgroundsub-canvas'
        self.bgsubtag = None

        self._bgtype_options = ['annulus', 'box', 'constant']
        self._algorithm_options = ['mean', 'median', 'mode']
        self._dummy_value = 0.0
        self._no_keyword = 'N/A'
        self._text_label = 'BGSub'
        self._text_label_offset = 4

        # User preferences. Some are just default values and can also be
        # changed by GUI.
        prefs = self.fv.get_preferences()
        settings = prefs.createCategory('plugin_BackgroundSub')
        settings.load(onError='silent')
        self.bgsubcolor = settings.get('bgsubcolor', 'magenta')
        self.bgtype = settings.get('bgtype', 'annulus')
        self.annulus_width = settings.get('annulus_width', 10)
        self.algorithm = settings.get('algorithm', 'median')
        self.sigma = settings.get('sigma', 1.8)
        self.niter = settings.get('niter', 10)

        # FITS keywords and values from general config
        gen_settings = prefs.createCategory('general')
        gen_settings.load(onError='silent')
        self._sci_extname = gen_settings.get('sciextname', 'SCI')
        self._ext_key = gen_settings.get('extnamekey', 'EXTNAME')

        # Used for calculation
        self.xcen, self.ycen = self._dummy_value, self._dummy_value
        self.radius = self._dummy_value
        self.boxwidth, self.boxheight = self._dummy_value, self._dummy_value

        # Stores latest result
        self.bgval = self._dummy_value
        self._debug_str = ''

        self.dc = self.fv.getDrawClasses()

        # The rest are set by set_bgtype()
        canvas = self.dc.DrawingCanvas()
        canvas.enable_edit(False)
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

        vbox, sw, self.orientation = Widgets.get_oriented_box(container)
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

        fr = Widgets.Frame('Background Selection')
        captions = (('Type:', 'label', 'BG type', 'combobox'), )
        w, b = Widgets.build_info(captions)
        self.w.update(b)

        combobox = b.bg_type
        for name in self._bgtype_options:
            combobox.append_text(name)
        b.bg_type.set_index(self._bgtype_options.index(self.bgtype))
        b.bg_type.widget.activated[str].connect(self.set_bgtype)

        fr.set_widget(w)
        vbox.add_widget(fr, stretch=0)

        fr = Widgets.Frame('Attributes')
        vbox2 = Widgets.VBox()
        self.w.bgtype_attr_vbox = Widgets.VBox()
        vbox2.add_widget(self.w.bgtype_attr_vbox, stretch=1)
        fr.set_widget(vbox2)
        vbox.add_widget(fr, stretch=0)

        captions = (
            ('Background Value:', 'label', 'Background Value', 'entry'),
            ('Subtract', 'button'))
        w, b = Widgets.build_info(captions, orientation=self.orientation)
        self.w.update(b)

        b.background_value.set_tooltip('Background value')
        b.background_value.set_text(str(self.bgval))
        b.background_value.widget.editingFinished.connect(self.set_constant_bg)
        b.background_value.widget.setReadOnly(True)
        b.background_value.widget.setEnabled(True)
        b.background_value.widget.setStyleSheet(
            'QLineEdit{background: white;}')

        b.subtract.set_tooltip('Subtract background')
        b.subtract.widget.clicked.connect(self.sub_bg)
        b.subtract.widget.setEnabled(False)

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
        self.set_bgtype(self.bgtype)

        self.gui_up = True

    def instructions(self):
        self.tw.set_text("""Select how background would be calculated: Annulus, box, or constant value.

To calculate from annulus or box: Draw (or redraw) a region with the right mouse button. Click or drag left mouse button to reposition region. You can also manually fine-tune region parameters by entering values in the respective text boxes. All X and Y values must be 0-indexed. Select algorithm from drop-down box, and enter desired parameter values.

To use a constant value: Enter the background value.

Click "Subtract" to remove background.""")

    def redo(self):
        self.w.background_value.set_text(str(self._dummy_value))
        self.w.subtract.widget.setEnabled(False)

        if self.bgtype not in ('annulus', 'box'):
            return True

        self.w.x.set_text(str(self.xcen))
        self.w.y.set_text(str(self.ycen))
        self._debug_str = 'x={0}, y={1}'.format(self.xcen, self.ycen)

        image = self.fitsimage.get_image()
        depth = image.get_depth()
        if depth == 3:
            self.logger.error(
                'Background calculation for RGB image is not supported')
            return True

        header = image.get_header()
        extname = header.get(self._ext_key, self._no_keyword).upper()
        if extname != self._sci_extname:
            self.logger.debug(
                'Background calculation not possible for {0} extension in '
                '{1}'.format(extname, image.get('name')))
            return True

        try:
            obj = self.canvas.getObjectByTag(self.bgsubtag)
        except KeyError:
            return True
        if obj.kind != 'compound':
            return True
        bg_obj = obj.objects[0]

        if self.bgtype == 'annulus':
            self.w.r.set_text(str(self.radius))
            self._debug_str += ', r={0}, dannulus={1}'.format(
                self.radius, self.annulus_width)
        else:  # box
            self.w.box_w.set_text(str(self.boxwidth))
            self.w.box_h.set_text(str(self.boxheight))
            self._debug_str += ', w={0}, h={1}'.format(
                self.boxwidth, self.boxheight)

        # Extract background data
        bg_masked = image.cutout_shape(bg_obj)
        bg_data = bg_masked[~bg_masked.mask]
        self.bgval = calc_stat(bg_data, sigma=self.sigma, niter=self.niter,
                               algorithm=self.algorithm)
        self._debug_str += (', bgval={0}, salgo={1}, sigma={2}, '
                            'niter={3}'.format(
                self.bgval, self.algorithm, self.sigma, self.niter))

        self.logger.debug(self._debug_str)
        self.w.background_value.set_text(str(self.bgval))

        if self.bgval != 0:
            self.w.subtract.widget.setEnabled(True)

        return True

    def update(self, canvas, button, data_x, data_y):
        try:
            obj = self.canvas.getObjectByTag(self.bgsubtag)
        except:
            return True

        if obj.kind == 'compound':
            bg_obj = obj.objects[0]
        else:
            bg_obj = obj

        if bg_obj.kind not in ('compound', 'annulus', 'rectangle'):
            return True

        try:
            canvas.deleteObjectByTag(self.bgsubtag, redraw=False)
        except:
            pass

        # Update displayed values
        self.xcen = data_x
        self.ycen = data_y

        bg_obj.move_to(data_x, data_y)
        tag = canvas.add(bg_obj)
        self.draw_cb(canvas, tag)
        return True

    def drag(self, canvas, button, data_x, data_y):
        try:
            obj = self.canvas.getObjectByTag(self.bgsubtag)
        except:
            return True

        if obj.kind == 'compound':
            bg_obj = obj.objects[0]
        else:
            bg_obj = obj

        if bg_obj.kind not in ('compound', 'annulus', 'rectangle'):
            return True

        bg_obj.move_to(data_x, data_y)

        if obj.kind == 'compound':
            try:
                canvas.deleteObjectByTag(self.bgsubtag, redraw=False)
            except:
                pass
            self.bgsubtag = canvas.add(bg_obj)
        else:
            canvas.redraw(whence=3)

        # Update displayed values
        self.xcen = data_x
        self.ycen = data_y

        return True

    def draw_cb(self, canvas, tag):
        obj = canvas.getObjectByTag(tag)
        if obj.kind not in ('annulus', 'rectangle'):
            return True
        canvas.deleteObjectByTag(tag, redraw=False)

        if self.bgsubtag:
            try:
                canvas.deleteObjectByTag(self.bgsubtag, redraw=False)
            except:
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
            self.radius = bg_obj.radius
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
        return self.redo()

    def set_bgtype(self, bgtype):
        if bgtype not in self._bgtype_options:
            self.logger.error(
                'Undefined background selection type - {0}'.format(bgtype))
            return True

        self.bgtype = bgtype

        # Remove old params
        self.w.bgtype_attr_vbox.remove_all()
        self.w.background_value.set_text(str(self._dummy_value))
        self.w.subtract.widget.setEnabled(False)
        self.canvas.deleteAllObjects()

        # Reset parameters
        self.xcen, self.ycen = self._dummy_value, self._dummy_value
        self.radius = self._dummy_value
        self.boxwidth, self.boxheight = self._dummy_value, self._dummy_value

        captions = [('X:', 'label', 'X', 'entry'),
                    ('Y:', 'label', 'Y', 'entry')]

        if bgtype == 'constant':
            self.canvas.enable_draw(False)
            self.w.background_value.widget.setReadOnly(False)

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
                ('Number of Iterations:', 'label', 'NIter', 'entry')]
            w, b = Widgets.build_info(captions, orientation=self.orientation)
            self.w.update(b)

            b.x.set_tooltip('X of centroid')
            b.x.set_text(str(self.xcen))
            b.x.widget.editingFinished.connect(self.set_xcen)

            b.y.set_tooltip('Y of centroid')
            b.y.set_text(str(self.ycen))
            b.y.widget.editingFinished.connect(self.set_ycen)

            if bgtype == 'annulus':
                b.r.set_tooltip('Inner radius of annulus')
                b.r.set_text(str(self.radius))
                b.r.widget.editingFinished.connect(self.set_radius)

                b.annulus_width.set_tooltip('Set annulus width manually')
                b.annulus_width.set_text(str(self.annulus_width))
                b.annulus_width.widget.editingFinished.connect(
                    self.set_annulus_width)

            else:  # box
                b.box_w.set_tooltip('Width of box')
                b.box_w.set_text(str(self.boxwidth))
                b.box_w.widget.editingFinished.connect(self.set_boxwidth)

                b.box_h.set_tooltip('Height of box')
                b.box_h.set_text(str(self.boxheight))
                b.box_h.widget.editingFinished.connect(self.set_boxheight)

            for name in self._algorithm_options:
                b.algorithm.append_text(name)
            b.algorithm.set_index(
                self._algorithm_options.index(self.algorithm))
            b.algorithm.widget.activated[str].connect(self.set_algorithm)

            b.sigma.set_tooltip('Sigma for clipping')
            b.sigma.set_text(str(self.sigma))
            b.sigma.widget.editingFinished.connect(self.set_sigma)

            b.niter.set_tooltip('Number of clipping iterations')
            b.niter.set_text(str(self.niter))
            b.niter.widget.editingFinished.connect(self.set_niter)

            self.w.bgtype_attr_vbox.add_widget(w, stretch=1)
            self.w.background_value.widget.setReadOnly(True)

        return True

    def set_xcen(self):
        """Reposition X."""
        try:
            self.xcen = float(self.w.x.get_text())
        except ValueError:
            return True

        # Get the compound object that sits on the canvas.
        try:
            obj = self.canvas.getObjectByTag(self.bgsubtag)
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
            c_obj.move_to(self.xcen, y)

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
            obj = self.canvas.getObjectByTag(self.bgsubtag)
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
        bg_obj.move_to(x, self.ycen)

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
            obj = self.canvas.getObjectByTag(self.bgsubtag)
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
            obj = self.canvas.getObjectByTag(self.bgsubtag)
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
            obj = self.canvas.getObjectByTag(self.bgsubtag)
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
            obj = self.canvas.getObjectByTag(self.bgsubtag)
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

    def set_algorithm(self, salgo):
        self.logger.debug('BGSub algorithm: {0}'.format(salgo))
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

    def set_constant_bg(self):
        self.w.subtract.widget.setEnabled(False)
        try:
            self.bgval = float(self.w.background_value.get_text())
        except ValueError:
            return True
        if self.bgval != 0:
            self.w.subtract.widget.setEnabled(True)
        self._debug_str = ''
        return True

    def sub_bg(self):
        """Subtract background, and update contents manager and display."""
        if self.bgval == 0:  # Nothing to do
            return True

        image = self.fitsimage.get_image()
        new_data = image.get_data() - self.bgval
        s = '{0} subtracted from {1}'.format(
            self.bgval, image.metadata['name'])
        if self._debug_str:
            s += ' ({0})'.format(self._debug_str)
        self.logger.info(s)

        # Also record action in QUIP log, if available
        if QUIP_LOG is not None:
            imname = image.metadata['name'].split('[')[0]
            s = QUIP_LOG.add_entry(imname, 'Background subtracted', s, 'status')

        # Update history listing
        try:
            history_plugin_obj = self.fv.gpmon.getPlugin('History')
        except Exception as e:
            self.logger.error(
                'Failed to update History plugin: {0}'.format(str(e)))
        else:
            history_plugin_obj.add_entry(s)

        # Change data in Ginga object and recalculate BG in annulus
        image.set_data(new_data, metadata=image.metadata)
        self.fitsimage.auto_levels()
        self.redo()

        # Update file listing
        try:
            list_plugin_obj = self.fv.gpmon.getPlugin('ContentsManager')
        except Exception as e:
            self.logger.error(
                'Failed to update ContentsManager plugin: {0}'.format(str(e)))
        else:
            chname = self.fv.get_channelName(self.fitsimage)
            list_plugin_obj.set_modified_status(chname, image, 'yes')

        return True

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
        self.fv.showStatus('')

    def __str__(self):
        """
        This method should be provided and should return the lower case
        name of the plugin.
        """
        return 'backgroundsub'
