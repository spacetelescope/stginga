"""Smoothing on an image."""

# STDLIB
import ast
import time
from datetime import datetime

# THIRD-PARTY
from scipy import ndimage
from scipy.signal import boxcar

# GINGA
from ginga.AstroImage import AstroImage
from ginga.GingaPlugin import LocalPlugin
from ginga.gw import Widgets

# STGINGA
from stginga.plugins.local_plugin_mixin import HelpMixin, ParamMixin

__all__ = []


# TODO: If this plugin becomes active again, need modernize doc rendering.
# See https://github.com/spacetelescope/stginga/issues/134
class Smoothing(HelpMixin, LocalPlugin, ParamMixin):

    def __init__(self, fv, fitsimage):
        # superclass defines some variables for us, like logger
        super(Smoothing, self).__init__(fv, fitsimage)

        self.help_url = ('https://stginga.readthedocs.io/en/latest/stginga/'
                         'plugins_manual/smoothing.html')

        self._smooth_options = ['boxcar', 'gauss', 'medfilt']
        self._mode_options = ['reflect', 'constant', 'nearest', 'mirror',
                              'wrap']
        self._text_label = 'Smooth'
        self._text_label_offset = 4
        self._out_pfx = 'smoothed'
        self._default_pars = (100, 100)
        self._dummy_value = 0.0

        # User preferences. Some are just default values and can also be
        # changed by GUI.
        prefs = self.fv.get_preferences()
        settings = prefs.create_category('plugin_Smoothing')
        settings.load(onError='silent')
        self.algorithm = settings.get('algorithm', 'boxcar')
        self.smoothpars = settings.get('smoothpars', self._default_pars)
        self.mode = settings.get('mode', 'nearest')
        self.fillval = settings.get('fillval', self._dummy_value)

        self.gui_up = False

    def build_gui(self, container):
        top = Widgets.VBox()
        top.set_border_width(4)

        vbox, sw, self.orientation = Widgets.get_oriented_box(container)
        vbox.set_border_width(4)
        vbox.set_spacing(2)

        fr = Widgets.Frame('Smoothing Algorithm')
        captions = (('Algorithm:', 'label', 'smooth type', 'combobox'),
                    ('Mode:', 'label', 'mode type', 'combobox'))
        w, b = Widgets.build_info(captions)
        self.w.update(b)

        combobox = b.smooth_type
        for name in self._smooth_options:
            combobox.append_text(name)
        b.smooth_type.set_index(self._smooth_options.index(self.algorithm))
        b.smooth_type.add_callback('activated', self.set_algo_cb)

        combobox = b.mode_type
        for name in self._mode_options:
            combobox.append_text(name)
        b.mode_type.set_index(self._mode_options.index(self.mode))
        b.mode_type.add_callback('activated', self.set_mode_cb)

        fr.set_widget(w)
        vbox.add_widget(fr, stretch=0)

        fr = Widgets.Frame('Attributes')
        vbox2 = Widgets.VBox()
        self.w.smooth_attr_vbox = Widgets.VBox()
        vbox2.add_widget(self.w.smooth_attr_vbox, stretch=1)
        fr.set_widget(vbox2)
        vbox.add_widget(fr, stretch=0)

        self.build_param_gui(vbox)

        captions = (('Status', 'llabel'),
                    ('Smooth', 'button', 'Spacer1', 'spacer'), )
        w, b = Widgets.build_info(captions, orientation=self.orientation)
        self.w.update(b)

        b.status.set_text('')

        b.smooth.set_tooltip('Smooth image')
        b.smooth.add_callback('activated', lambda w: self.do_smooth())

        vbox.add_widget(w, stretch=0)
        top.add_widget(sw, stretch=1)

        btns = Widgets.HBox()
        btns.set_border_width(4)
        btns.set_spacing(3)

        btn = Widgets.Button('Close')
        btn.add_callback('activated', lambda w: self.close())
        self.w.close = btn
        btns.add_widget(btn, stretch=0)
        btn = Widgets.Button('Help')
        btn.add_callback('activated', lambda w: self.help())
        btns.add_widget(btn, stretch=0)
        btns.add_widget(Widgets.Label(''), stretch=1)

        top.add_widget(btns, stretch=0)
        container.add_widget(top, stretch=1)

        # Populate default attributes frame
        self.set_algo()

        self.gui_up = True

    def toggle_gui(self, enable=False):
        """Disable/enable all GUI elements, except Save Param."""
        all_w = [self.w.smooth_type, self.w.mode_type, self.w.smoothpars,
                 self.w.load_param, self.w.smooth, self.w.close]

        if self.mode == 'constant':
            all_w.append(self.w.fillval)

        for w in all_w:
            w.set_enabled(enable)

    def set_algo_cb(self, w, index):
        self.algorithm = self._smooth_options[index]
        self.set_algo()

    def set_mode_cb(self, w, index):
        self.mode = self._mode_options[index]
        self.set_algo()

    def set_algo(self):
        """Change smoothing algorithm."""
        salgo = self.algorithm
        mode = self.mode

        # Remove old params
        self.w.smooth_attr_vbox.remove_all()
        self.w.smooth.set_enabled(False)

        # Reset parameters
        # self.smoothpars = self._default_pars
        # self.fillval = self._dummy_value

        if salgo == 'gauss':
            captions = [('Sigma:', 'label', 'smoothpars', 'entry')]
            tooltip_pars = 'Std dev for Gaussian kernel'
        else:
            captions = [('Size:', 'label', 'smoothpars', 'entry')]
            tooltip_pars = 'Kernel size (pix)'

        if mode == 'constant':
            captions += [('Fill value:', 'label', 'fillval', 'entry')]

        w, b = Widgets.build_info(captions, orientation=self.orientation)
        self.w.update(b)

        b.smoothpars.set_tooltip(tooltip_pars)
        b.smoothpars.set_text(str(self.smoothpars))
        b.smoothpars.add_callback('activated', lambda w: self.set_smoothpars())

        if mode == 'constant':
            b.fillval.set_tooltip('Fill value')
            b.fillval.set_text(str(self.fillval))
            b.fillval.add_callback('activated', lambda w: self.set_fillval())

        self.w.smooth_attr_vbox.add_widget(w, stretch=1)
        self.w.smooth.set_enabled(True)

    def set_smoothpars(self):
        try:
            pars = ast.literal_eval(self.w.smoothpars.get_text())
        except ValueError:
            self.logger.error('Cannot set kernel parameter(s)')
            self.w.smoothpars.set_text(str(self.smoothpars))
        else:
            self.smoothpars = pars

    def set_fillval(self):
        try:
            fillval = float(self.w.fillval.get_text())
        except ValueError:
            self.logger.error('Cannot set fill value')
            self.w.fillval.set_text(str(self.fillval))
        else:
            self.fillval = fillval

    def do_smooth(self):
        """Create a **new** smoothed image."""
        self.toggle_gui(enable=False)
        image = self.fitsimage.get_image()

        if image is None:
            self.logger.error('No image to smooth')
            return True

        self.w.status.set_text('Smoothing...')
        self.fv.nongui_do(self._smooth, image)

    def _smooth(self, image):
        """Smoothing work horse."""
        t1 = time.time()
        data = image.get_data()

        if self.algorithm == 'gauss':
            s = 'sigma'
        else:
            s = 'size'

        debug_str = f'{s}={self.smoothpars}, mode={self.mode}'

        if self.mode == 'constant':
            debug_str += f', fillval={self.fillval}'

        if self.algorithm == 'boxcar':
            kern = boxcar(self.smoothpars)
            kern /= kern.size
            new_dat = ndimage.convolve(
                data, kern, mode=self.mode, cval=self.fillval)
        elif self.algorithm == 'gauss':
            new_dat = ndimage.gaussian_filter(
                data, sigma=self.smoothpars, mode=self.mode, cval=self.fillval)
        else:  # medfilt
            new_dat = ndimage.median_filter(
                data, size=self.smoothpars, mode=self.mode, cval=self.fillval)

        # Insert new image
        old_name = image.get('name', 'none')
        new_name = self._get_new_name(old_name)
        new_im = self._make_image(new_dat, image, new_name)
        self.fv.gui_call(
            self.fv.add_image, new_name, new_im, chname=self.chname)

        # Add change log
        s = f'Smoothed {old_name} using {self.algorithm}, {debug_str}'
        info = {'time_modified': datetime.utcnow(), 'reason_modified': s}
        self.fv.update_image_info(new_im, info)
        self.logger.info(s)

        t2 = time.time()
        self.w.status.set_text(f'Done ({t2 - t1:.3f} s)')
        self.toggle_gui(enable=True)

    def _get_new_name(self, oldname):
        """Generate new unique image name."""
        ts = int(time.time())  # Ensure unique name
        return f'{self._out_pfx}{ts}_{oldname}'

    def _make_image(self, data_np, oldimage, name):
        """Generate new image object."""
        image = AstroImage()
        image.set_data(data_np)
        image.update_keywords(oldimage.get_header())
        image.set(name=name, path=None)
        return image

    def params_dict(self):
        """Return current parameters as a dictionary."""
        pardict = {'plugin': str(self),
                   'algorithm': self.algorithm, 'mode': self.mode}

        image = self.fitsimage.get_image()
        if image is None:
            return pardict

        pardict['image'] = image.get('path')
        pardict['ext'] = image.get('idx')
        pardict['smoothpars'] = self.smoothpars

        if self.mode == 'constant':
            pardict['fillval'] = self.fillval

        return pardict

    def ingest_params(self, pardict):
        """Ingest dictionary containing plugin parameters into plugin
        GUI and internal variables."""
        if ((pardict['plugin'] != str(self)) or
                (pardict['algorithm'] not in self._smooth_options) or
                (pardict['mode'] not in self._mode_options)):
            self.logger.error('Cannot ingest parameters')
            return

        self.algorithm = pardict['algorithm']
        self.mode = pardict['mode']
        self.w.smooth_type.set_index(
            self._smooth_options.index(self.algorithm))
        self.w.mode_type.set_index(self._mode_options.index(self.mode))
        self.set_algo()

        self.smoothpars = pardict['smoothpars']
        self.w.smoothpars.set_text(str(self.smoothpars))

        if self.mode == 'constant':
            self.fillval = pardict['fillval']
            self.w.fillval.set_text(str(self.fillval))

    def close(self):
        self.fv.stop_local_plugin(self.chname, str(self))
        return True

    def start(self):
        self.resume()

    def pause(self):
        self.canvas.ui_set_active(False)

    def resume(self):
        # turn off any mode user may be in
        self.modes_off()

        self.fv.show_status('See Help')

    def stop(self):
        self.gui_up = False
        self.fv.show_status('')

    def __str__(self):
        """
        This method should be provided and should return the lower case
        name of the plugin.
        """
        return 'smoothing'
