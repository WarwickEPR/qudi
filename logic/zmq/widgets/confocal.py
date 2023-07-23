# An iPython widget for use with Jupyter Lab to display and interact with confocal imaging
# recorded to HDF5 by the Qudi extension

from .. client.QudiControl import QudiControl, BgTask
from .. data.tables_context import TablesContext
import logging

import ipywidgets as widgets
import matplotlib.pyplot as plt
from ipywidgets import AppLayout, HBox, Dropdown
import IPython.display
import numpy as np
from traitlets import HasTraits
from IPython.display import Math, display
from scipy.optimize import curve_fit
#from .savefig import SaveFig
from ..data import image as imgdata



class ConfocalWidget:

    log = logging.getLogger('widget.confocal')

    def __init__(self, tc: TablesContext, qc: QudiControl = None):

        self.tc = tc
        self.qc = qc

        self.selected_xy_image = None
        self.selected_depth_image = None

        self.plot_area = widgets.Output()
        self.layout = AppLayout(center=self.plot_area, pane_widths=[1, 4, 4])

    def list_xy_images(self):
        with self.tc as th:
            xy_images = th.tables.get_node('/Confocal_XY')
            return list(xy_images._v_children)

    def list_depth_images(self):
        with self.tc as th:
            xz_images = th.tables.get_node('/Confocal_XZ')
            yz_images = th.tables.get_node('/Confocal_YZ')
            return [xz_images._v_children] + [xz_images._v_children]

    def image_display(self):
        layout = AppLayout()


    def update_image(self, image):
        with self.tc as th:
            image_node = th.tables.get_node(image)
            image_data = np.array(image_node)
            image_attrs = image_node._v_attrs
            image_name = image.split('/')[-1]

            fig = plt.figure(figsize=(6, 6))
            ax = plt.subplot()
            im = plt.imshow(cfd[:, :, 3], vmax=20e3, interpolation='gaussian', cmap='inferno')
            plt.xlabel("X (um)")
            plt.ylabel("Y (um)")
            fig.suptitle(image)

    def image_list_dropdown(self):
        xy_images = self.list_xy_images()
        if len(xy_images) > 0:
            default_image = xy_images[-1]
        else:
            default_image = None
        dropdown = Dropdown(options=xy_images, value=default_image)
        image_type_selector = widgets.RadioButtons(options=['XY', 'Depth'], value='XY', layout=HBox())
        dropdown.options = self.list_xy_images()
        image_selector = HBox(dropdown, image_type_selector)


class ConfocalImageHdf(HasTraits):
    file = None
    image = None

    image_data = None
    _fig = None
    _plot_pane = None
    _image = None
    _full_pane = None
    _controls = None
    x_label = "X"
    y_label = "Y"

    def __init__(self, file, image=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file = file
        self._tc = TablesContext(file)
        if image:
            self.image = image
        else:
            self.image = self.latest_image


    def images_dictionary(self, filter_function=lambda _: True):
        with self._tc as th:
            filtered_nodes = filter(filter_function, th.nodes_of_type(root="/Confocal", data_type_prefix="Image"))
            n = sorted(filtered_nodes, key=TablesContext.extract_timestamp)
            return dict(map(lambda x: (x.name, x._v_pathname), n))

    def latest_image(self, filter_function=lambda _: True):
        image_nodes = self.images_dictionary(filter_function).values()
        if image_nodes:
            return image_nodes[-1]
        else:
            return None

    def display(self):
        self._plot_pane = widgets.Output()
        with self._plot_pane:
            plt.ioff()
            self._fig = plt.figure(figsize=(4, 4), dpi=150)
            plt.ion()
            self._fig.canvas.header_visible = False
            image_data = self.image_data.image_data
            extents = self.image_data.extents
            self._image = plt.imshow(image_data, interpolation='gaussian', cmap='inferno', extent=extents,
                                     zorder=1)
            plt.colorbar(self._image, label='Counts (kc/s)')
            plt.xlabel = 'X (um)'
            plt.ylabel = 'Y (um)'
            plt.clabel = 'kc/s'
            plt.show()

        max_counts = np.max(self.image_data.image_data)
        contrast = widgets.IntRangeSlider(min=0, max=max_counts, value=(0, int(max_counts)),
                                          description="Count range",
                                          orientation='vertical', readout=False, continuous_update=False,
                                          width='90px')
        min_kcps = widgets.BoundedIntText(min=0, max=max_counts, value=0, layout=widgets.Layout(width='90px'))
        max_kcps = widgets.BoundedIntText(min=0, max=max_counts, value=max_counts,
                                          layout=widgets.Layout(width='90px'))
        widgets.link((min_kcps, 'value'),
                     (contrast, 'value'),
                     transform=[(lambda x: (x, max_kcps.value)), (lambda x: x[0])])
        widgets.link((max_kcps, 'value'),
                     (contrast, 'value'),
                     transform=[(lambda x: (min_kcps.value, x)), (lambda x: x[1])])

        def contrast_change(change):
            cmin, cmax = change.new
            self.update_count_range(cmin, cmax)

        def image_change(change):
            data = change.new
            self._image.set_data(data)

        def extents_change(change):
            data = change.new
            self._image.set_extents(data)
            with self._plot_pane:
                plt.xlabel = self.x_label
                plt.ylabel = self.y_label
                plt.xlim((data[0:2]))
                plt.ylim((data[2:4]))

        contrast.observe(contrast_change, names='value')
        self.image_data.observe(image_change, names='image_data')
        self.image_data.observe(extents_change, names='extents')

        self._controls = widgets.VBox([max_kcps, contrast, min_kcps])
        self._controls.layout.align_items = 'center'
        self._full_pane = widgets.AppLayout(center=self._plot_pane,
                                            right_sidebar=self._controls,
                                            footer=SaveFig(self._fig).display(),
                                            align_items='center',
                                            pane_widths=[1, 4, 1])
        return self._full_pane

    def update_count_range(self, cmin, cmax):
        if self._image:
            self._image.set_clim(cmin, cmax)

    def update(self):
        self._image.set_data(self.image_data.image_data)
        self._image.set_extent(self.image_data.extents)

def update_dropdown(value):
    if value == 'Depth':
        dropdown.options = self.list_depth_images()
    else: # XY
        dropdown.options = self.list_xy_images()

def update_selection(image):
    if image_type_selector.value == 'Depth':
        self.selected_depth_image = image
    else: # XY
        self.selected_xy_image = image
    self.update_image(image)

image_type_selector.observe(update_dropdown)

return image_selector

