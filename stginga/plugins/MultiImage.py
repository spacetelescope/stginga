from math import sqrt

from ginga import GingaPlugin
from ginga.gw import Widgets, Viewers
from ginga.qtw.QtHelp import QtCore

instructions = (
    'To add images to the group, simply ensure that the plugin is active'
    ' and display the image in the main viewer.'
)


class MultiImage(GingaPlugin.LocalPlugin):
    """Coordinate display between multiple images"""

    def __init__(self, fv, fitsimage):
        super(MultiImage, self).__init__(fv, fitsimage)

        self.logger.debug('Called.')
        self.logger.debug('fv.w="{}"'.format(self.fv.w))

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

        self.id_count = 0  # Create unique ids

        self.layertag = 'muimg-canvas'
        self.dx = 30
        self.dy = 30
        self.max_side = 1024
        self.images = {}
        self.center_ra = None
        self.center_dec = None
        self.dsky = None
        self.pstamps = None

    def build_gui(self, container):
        """Build the Dialog"""
        self.logger.debug('Called.')
        if self.pstamps is not None:
            return

        # Postage stamps
        pstamps_frame = self.fv.w['pstamps']
        self.pstamps_show = False
        pstamps = Widgets.HBox()
        w = pstamps.get_widget()
        pstamps_frame.layout().addWidget(w)
        w.setMinimumHeight(100)
        self.pstamps = pstamps
        self.pstamps_frame = pstamps_frame
        return

        # Get container specs.
        vbox, sw, orientation = Widgets.get_oriented_box(container)
        vbox.set_border_width(4)
        vbox.set_spacing(2)

        # Instructions
        self.msgFont = self.fv.getFont("sansFont", 12)
        tw = Widgets.TextArea(wrap=True, editable=False)
        tw.set_font(self.msgFont)
        self.tw = tw

        fr = Widgets.Expander("Instructions")
        fr.set_widget(tw)
        vbox.add_widget(fr, stretch=0)

        vjunk = Widgets.VBox()
        vjunk.set_border_width(4)
        container.add_widget(vjunk, stretch=1)

    def instructions(self):
        self.tw.set_text(instructions)
        self.tw.set_font(self.msgFont)

    def start(self):
        self.logger.debug('Called.')

        #self.instructions()

        # insert layer if it is not already
        p_canvas = self.fitsimage.get_canvas()
        try:
            p_canvas.getObjectByTag(self.layertag)

        except KeyError:
            # Add canvas layer
            p_canvas.add(self.canvas, tag=self.layertag)

        self.show_pstamps(True)
        #self.redo()

    def resume(self):
        self.logger.debug('Called.')

        self.canvas.ui_setActive(True)
        self.fv.showStatus("Do something")

    def redo(self):
        self.logger.debug('Called.')
        self.logger.debug('pstamps.sizeHint="{}"'.format(self.pstamps_frame.sizeHint()))

        fi_image = self.fitsimage.get_image()
        if fi_image is None:
            return

        try:
            fi_image_id = fi_image.get('path')
        except Exception as e:
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
        self.set_region(finalize=True)

        # Loop through all images.
        for image_id, (image, pstamp) in self.images.items():

            # Determine the region.
            x1, y1, \
                x2, y2, \
                center_ra, center_dec, \
                dsky = self.sky_region(image)

            # Cut and show postage stamp
            self.logger.debug("box %f,%f %f,%f" % (x1, y1, x2, y2))
            x1, y1, x2, y2, data = self.cutdetail(image,
                                                  int(x1), int(y1),
                                                  int(x2), int(y2))
            self.logger.debug("cut box %f,%f %f,%f" % (x1, y1, x2, y2))
            pstamp.set_data(data)

    def stop(self):
        self.logger.debug('Called.')

        # deactivate the canvas
        self.canvas.ui_setActive(False)
        self.fv.showStatus("")

        self.show_pstamps(False)

    def close(self):
        self.logger.debug('Called.')

        chname = self.fv.get_channelName(self.fitsimage)
        self.fv.stop_local_plugin(chname, str(self))
        return True

    def pause(self):
        self.logger.debug('Called.')

        self.canvas.ui_setActive(False)

    def __str__(self):
        return 'multi image'

    def btndown(self, canvas, event, data_x, data_y, viewer):
        self.set_region(data_x, data_y)
        return True

    def update(self, canvas, event, data_x, data_y, viewer):
        self.set_region(data_x, data_y, finalize=True)
        return self.redo()

    def drag(self, canvas, event, data_x, data_y, viewer):
        self.set_region(data_x, data_y)
        self.redo()
        return True

    def draw_cb(self, canvas, tag):
        self.logger.debug('Called.')
        obj = canvas.getObjectByTag(tag)
        self.logger.debug('obj="{}"'.format(obj))
        pt_obj = canvas.getObjectByTag(self.pstag)
        self.logger.debug('self.pstag="{}"'.format(pt_obj))
        if obj.kind != 'rectangle':
            return True
        canvas.deleteObjects([obj, pt_obj])
        x1, y1, x2, y2 = obj.get_llur()
        self.dx = (x2 - x1) // 2
        self.dy = (y2 - y1) // 2
        self.dsky = None
        self.set_region(x1 + self.dx, y1 + self.dy, finalize=True)
        self.redo()
        return True

    def edit_cb(self, canvas, obj):
        self.logger.debug('Called.')
        self.logger.debug('obj="{}"'.format(obj))
        pt_obj = canvas.getObjectByTag(self.pstag)
        self.logger.debug('self.pstag="{}"'.format(pt_obj))
        self.redo()
        return True

    def cutdetail(self, srcimage, x1, y1, x2, y2):
        data, x1, y1, x2, y2 = srcimage.cutout_adjust(x1, y1, x2, y2)
        return (x1, y1, x2, y2, data)

    def add_pstamp(self):

        # Setup for thumbnail display
        di = Viewers.ImageViewCanvas(logger=self.logger)
        di.configure_window(100, 100)
        di.enable_autozoom('on')
        di.add_callback('configure', self.window_resized_cb)
        di.enable_autocuts('off')
        di.set_bg(0.4, 0.4, 0.4)
        # for debugging
        di.set_name('pstamp')

        iw = Widgets.wrap(di.get_widget())
        self.pstamps.add_widget(iw)

        return di

    def set_region(self, x=None, y=None, finalize=False, coord='data'):
        """Set the box"""
        linestyle = 'solid' if finalize else 'dash'

        image = self.fitsimage.get_image()
        x1, y1, \
            x2, y2, \
            self.center_ra, self.center_dec, \
            self.dsky = self.sky_region(image, x, y)

        try:
            obj = self.canvas.getObjectByTag(self.pstag)
        except: # Need be general due to ginga
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

    def sky_region(self, image, x=None, y=None):
        if x is not None and y is not None:
            center_ra, center_dec = image.pixtoradec(x, y)
        else:
            if self.center_ra is None or self.center_dec is None:
                x = image.width // 2
                y = image.height // 2
                center_ra, center_dec = image.pixtoradec(x, y)
            else:
                center_ra = self.center_ra
                center_dec = self.center_dec
                x, y = image.radectopix(center_ra, center_dec)
        dsky = self.dsky
        if dsky is None:
            x1, y1 = x - self.dx, y - self.dy
            ra1, dec1 = image.pixtoradec(x1, y1)
            dsky = sqrt(
                (center_ra - ra1)**2 + (center_dec - dec1)**2
            )

        x1, y1 = image.radectopix(
            center_ra - dsky,
            center_dec - dsky
        )
        x2, y2 = image.radectopix(
            center_ra + dsky,
            center_dec + dsky
        )
        x1, x2 = (x1, x2) if x1 <= x2 else (x2, x1)
        y1, y2 = (y1, y2) if y1 <= y2 else (y2, y1)
        return (x1, y1, x2, y2, center_ra, center_dec, dsky)

    def make_id(self):
        self.id_count += 1
        return 'Image_{:02}'.format(self.id_count)

    def window_resized_cb(self, fitsimage, width, height):
        self.logger.debug('Called.')
        fitsimage.zoom_fit()

    def show_pstamps(self, show):
        """Show/hide the stamps"""
        self.pstamps_frame.setVisible(show)

    def pstamps_size_hint(self):
        size = self.pstamps_frame.size()
        self.logger.debug('size="{}"'.format(size.width()))
        self.logger.debug('frame_size="{}"'.format(self.pstamps_frame_size))
        if self.pstamps_show:
            return QtCore.QSize(size.width(), self.pstamps_frame_size)
        else:
            self.pstamps_frame_size = size.height
            return QtCore.QSize(size.width(), 0)
