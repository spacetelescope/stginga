"""Multi-Image viewer global plugin for Ginga."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

# GINGA
from ginga.GingaPlugin import GlobalPlugin
from ginga.gw import Widgets, Viewers

__all__ = ['MultiImage']


class MultiImage(GlobalPlugin):
    """Display the same region from multiple images."""
    def __init__(self, fv):
        # superclass defines some variables for us, like logger
        super(MultiImage, self).__init__(fv)

        self._def_coords = 'wcs'
        self._coords_options = (('wcs', 'Fix region to sky'),
                                ('data', 'Fix region to pixels'))
        self.id_count = 0  # Create unique ids
        self.layertag = 'muimg-canvas'
        self.region = None
        self.images = {}
        self.pstamps = None

        # TODO: Enable user preferences
        #prefs = self.fv.get_preferences()
        #self.settings = prefs.createCategory('plugin_MultiImage')
        #self.settings.addDefaults(something=True)
        #self.settings.load(onError='silent')

        self.dc = self.fv.getDrawClasses()

        canvas = self.dc.DrawingCanvas()
        canvas.enable_draw(True)
        canvas.enable_edit(True)
        canvas.set_drawtype('rectangle', color='cyan', linestyle='dash',
                            coord='wcs', drawdims=True)
        canvas.set_callback('draw-event', self.draw_cb)
        canvas.set_callback('edit-event', self.edit_cb)
        canvas.add_draw_mode('move', down=self.btndown,
                             move=self.drag, up=self.update)
        canvas.register_for_cursor_drawing(self.fitsimage)
        canvas.setSurface(self.fitsimage)
        canvas.set_draw_mode('move')
        self.canvas = canvas

        self.gui_up = False

    def build_gui(self, container):
        """This method is called when the plugin is invoked.  It builds the
        GUI used by the plugin into the widget layout passed as
        ``container``.

        This method could be called several times if the plugin is opened
        and closed.

        """
        # Setup for options
        vbox, sw, orientation = Widgets.get_oriented_box(container)
        vbox.set_border_width(4)
        vbox.set_spacing(2)

        # Instructions
        msgFont = self.fv.getFont('sansFont', 12)
        tw = Widgets.TextArea(wrap=True, editable=False)
        tw.set_font(msgFont)
        self.tw = tw

        fr = Widgets.Expander('Instructions')
        fr.set_widget(tw)

        # Mode administration
        modes = Widgets.Frame('Region Editing')
        mode = self.canvas.get_draw_mode()
        hbox = Widgets.HBox()
        hbox.set_border_width(4)
        btn1 = Widgets.RadioButton('Move')
        btn1.set_state(mode == 'move')
        btn1.add_callback(
            'activated', lambda w, val: self.set_mode_cb('move', val))
        btn1.set_tooltip('Choose this to position region')
        self.w.btn_move = btn1
        hbox.add_widget(btn1)

        btn2 = Widgets.RadioButton('Draw', group=btn1)
        btn2.set_state(mode == 'draw')
        btn2.add_callback(
            'activated', lambda w, val: self.set_mode_cb('draw', val))
        btn2.set_tooltip('Choose this to draw a replacement region')
        self.w.btn_draw = btn2
        hbox.add_widget(btn2)

        btn3 = Widgets.RadioButton('Edit', group=btn1)
        btn3.set_state(mode == 'edit')
        btn3.add_callback(
            'activated', lambda w, val: self.set_mode_cb('edit', val))
        btn3.set_tooltip("Choose this to edit a region")
        self.w.btn_edit = btn3
        hbox.add_widget(btn3)

        hbox.add_widget(Widgets.Label(''), stretch=1)
        modes.set_widget(hbox)

        # Coordinates
        coords = Widgets.Frame('WCS Reference')
        hbox = Widgets.HBox()
        hbox.set_border_width(4)
        hbox.set_spacing(4)
        for option, tooltip in self._coords_options:
            btn = Widgets.RadioButton(option)
            btn.set_state(option == self._def_coords)
            btn.add_callback(
                'activated',
                lambda widget, state, option=option: self.set_coords(
                    option, state))
            btn.set_tooltip(tooltip)
            hbox.add_widget(btn)
        hbox.add_widget(Widgets.Label(''), stretch=1)
        coords.set_widget(hbox)

        # Basic plugin admin buttons
        btns = Widgets.HBox()
        btns.set_spacing(3)

        btn = Widgets.Button('Close')
        btn.add_callback('activated', lambda w: self.close())
        btns.add_widget(btn, stretch=0)
        btns.add_widget(Widgets.Label(''), stretch=1)

        # Layout the options
        vbox.add_widget(fr, stretch=0)
        vbox.add_widget(coords, stretch=0)
        vbox.add_widget(modes, stretch=0)

        # Layout top level framing
        vtop = Widgets.VBox()
        vtop.set_border_width(4)
        vtop.add_widget(sw, stretch=1)  # Magic: sw contains vbox
        vtop.add_widget(btns, stretch=0)

        # Options completed.
        container.add_widget(vtop, stretch=1)

        # Postage stamps
        if self.pstamps is not None:
            return

        pstamps_frame = self.fv.w['pstamps']
        self.pstamps_show = False
        pstamps = Widgets.HBox()
        pswidth = pstamps.get_size()[0]
        pstamps.resize(pswidth, 100)  # Toolkit agnostic way to set min height
        pstamps_frame.add_widget(pstamps)
        self.pstamps = pstamps
        self.pstamps_frame = pstamps_frame

        self.gui_up = True

    def instructions(self):
        self.tw.set_text("""To add images to the group, simply ensure that the plugin is active and display the image in the main viewer.

Then move, drag, or edit the region as needed.

The WCS options select the common frame of reference to use between images.""")

    def start(self):
        self.instructions()

# UNTIL HERE

        # insert layer if it is not already
        p_canvas = self.fitsimage.get_canvas()
        try:
            p_canvas.getObjectByTag(self.layertag)

        except KeyError:
            # Add canvas layer
            p_canvas.add(self.canvas, tag=self.layertag)

        self.show_pstamps(True)

    def resume(self):
        self.logger.debug('Called.')

        self.canvas.ui_setActive(True)
        self.fv.showStatus("Draw a region to examine.")

        self.redo()

    def redo(self):
        self.logger.debug('Called.')

        fi_image = self.fitsimage.get_image()
        if fi_image is None:
            return

        try:
            fi_image_id = fi_image.get('path')
        except Exception:
            raise
            fi_image_id = self.make_id()
        try:
            _, pstamp = self.images[fi_image_id]
        except KeyError:
            pstamp = self.add_pstamp()
            self.images[fi_image_id] = (fi_image, pstamp)
        self.fitsimage.copy_attributes(pstamp,
                                       ['transforms', 'cutlevels',
                                        'rgbmap'])

        # Ensure region is accurately reflected on displayed image.
        if self.region is None:
            self.init_region()
        self.region.image = fi_image
        self.draw_region(finalize=True)

        # Loop through all images.
        for image_id, (image, pstamp) in self.images.items():
            x1, y1, x2, y2 = self.region.bbox(coord='data', image=image)
            x1, y1, x2, y2, data = self.cutdetail(image,
                                                  int(x1), int(y1),
                                                  int(x2), int(y2))
            pstamp.set_data(data)

    def stop(self):
        self.logger.debug('Called.')

        try:
            obj = self.canvas.getObjectByTag(self.pstag)
        except:
            """Ignore"""
        else:
            self.canvas.delete_objects([obj])
        self.canvas.ui_setActive(False)
        self.fv.showStatus("")

        self.pstamps_frame.layout().removeWidget(self.pstamps.get_widget())
        self.pstamps.get_widget().setParent(None)
        self.pstamps = None
        self.images = {}

    def close(self):
        self.logger.debug('Called.')
        self.fv.stop_local_plugin(self.chname, str(self))
        return True

    def pause(self):
        self.logger.debug('Called.')

        self.canvas.ui_setActive(False)

    def __str__(self):
        return 'MultiImage'

    def btndown(self, canvas, event, data_x, data_y, viewer):
        self.logger.debug('Called.')
        self.region.set_center(data_x, data_y, coord='data')
        self.redo()
        return True

    def update(self, canvas, event, data_x, data_y, viewer):
        self.region.set_center(data_x, data_y, coord='data')
        self.redo()
        return

    def drag(self, canvas, event, data_x, data_y, viewer):
        self.region.set_center(data_x, data_y, coord='data')
        self.redo()
        return True

    def draw_cb(self, canvas, tag):
        self.logger.debug('Called.')
        obj = canvas.getObjectByTag(tag)
        pt_obj = canvas.getObjectByTag(self.pstag)
        if obj.kind != 'rectangle':
            return True
        canvas.deleteObjects([obj, pt_obj])
        x1, y1, x2, y2 = obj.get_llur()
        self.region.set_bbox(x1, y1, x2, y2, coord='data')
        self.redo()
        return True

    def edit_cb(self, canvas, obj):
        self.logger.debug('Called.')
        pt_obj = canvas.getObjectByTag(self.pstag)
        if obj != pt_obj:
            return True
        x1, y1, x2, y2 = pt_obj.get_llur()
        self.region.set_bbox(x1, y1, x2, y2, coord='data')
        self.redo()
        return True

    def cutdetail(self, srcimage, x1, y1, x2, y2):
        data, x1, y1, x2, y2 = srcimage.cutout_adjust(x1, y1, x2, y2)
        return (x1, y1, x2, y2, data)

    def add_pstamp(self):
        self.logger.debug('Called.')
        # Setup for thumbnail display
        di = Viewers.ImageViewCanvas(logger=self.logger)
        #di.configure_window(100, 100)
        di.set_desired_size(100, 100)
        di.enable_autozoom('on')
        di.add_callback('configure', self.window_resized_cb)
        di.enable_autocuts('off')
        di.set_bg(0.4, 0.4, 0.4)
        # for debugging
        di.set_name('pstamp')

        iw = Widgets.wrap(di.get_widget())
        self.pstamps.add_widget(iw)

        return di

    def draw_region(self, finalize=False, coord='data'):
        """Set the box"""
        self.logger.debug('Called.')
        linestyle = 'solid' if finalize else 'dash'
        x1, y1, x2, y2 = self.region.bbox(coord=coord)
        try:
            obj = self.canvas.getObjectByTag(self.pstag)
        except:  # Need be general due to ginga
            self.pstag = self.canvas.add(
                self.dc.Rectangle(x1, y1, x2, y2,
                                  color='cyan',
                                  linestyle=linestyle)
            )
            obj = self.canvas.getObjectByTag(self.pstag)
        else:
            obj.linestyle = linestyle
            obj.x1, obj.y1 = x1, y1
            obj.x2, obj.y2 = x2, y2
            self.canvas.redraw(whence=3)

    def make_id(self):
        self.id_count += 1
        return 'Image_{:02}'.format(self.id_count)

    def window_resized_cb(self, fitsimage, width, height):
        self.logger.debug('Called.')
        fitsimage.zoom_fit()

    def show_pstamps(self, show):
        """Show/hide the stamps"""
        self.pstamps_frame.get_widget().setVisible(show)

    def edit_region(self):
        if self.pstag is not None:
            obj = self.canvas.getObjectByTag(self.pstag)
            if obj.kind != 'rectangle':
                return True
            self.canvas.edit_select(obj)
        else:
            self.canvas.clear_selected()
        self.canvas.update_canvas()

    def set_mode_cb(self, mode, tf):
        if tf:
            self.canvas.set_draw_mode(mode)
            if mode == 'edit':
                self.edit_region()
        return True

    def set_coords(self, coords, state):
        self.logger.debug('Called.')
        if state:
            self.region.set_coords(coords)

    def init_region(self):
        image = self.fitsimage.get_image()
        height, width = image.shape
        x = width // 2
        y = height // 2
        self.region = Region(logger=self.logger)
        self.region.set_region(x, y, 30, 'data', as_coord=self._def_coords,
                               image=image)

    def set_region(self, region):
        self.region = region
