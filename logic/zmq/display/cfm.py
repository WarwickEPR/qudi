import asyncio

from .. client.QudiControl import QudiControl
from .. data.tables_context import TablesContext
from .. data.image import ImageHDF
from logic.zmq.data.timestamp import Timestamp

import ipywidgets as widgets
import matplotlib.pyplot as plt
from ipywidgets import Layout
import numpy as np
from traitlets import HasTraits, Unicode
from .savefig import SaveFig
import math
from itertools import chain


class ImageWidget(HasTraits):
    image = Unicode

    _extent = (0., 0., 0., 0.)
    _count_range = (0, 100.0)
    _image_data = None

    fig = None
    _plot_pane = None
    _image = None
    _full_pane = None
    _controls = None
    x_label = "X"
    y_label = "Y"

    def __init__(self, tc=None, image=None, qc: QudiControl = None, save=False, **kwargs):
        super().__init__(**kwargs)
        self._tc = tc
        self.fig = None
        self.axes = None
        self._im_ax = None
        self._scatter_ax = None
        self._labels = []
        if image:
            self.image = image
        else:
            self.image = self.latest_image()

        self._count_range_control = widgets.FloatRangeSlider(min=0,
                                                             max=1.0,
                                                             value=(0, 1.0),
                                                             description="Count range (kc/s)",
                                                             orientation='vertical',
                                                             readout=True,
                                                             readout_format='.1f',
                                                             continuous_update=True,
                                                             layout=Layout(width='90px', height="50%")
                                                             )
        self._count_range_control.style.font_size = 20
        self._count_range_control.observe(self.update_contrast, names='value')
        self.observe(self.update_image, names=['image'])

        self._image_selector = widgets.Dropdown(options=self.images_dictionary(),
                                                description='Image',
                                                layout=Layout(flex='2 0 0%'))
        if self.image in self.images_dictionary():
            self._image_selector.value = self.image

        self._image_slice = widgets.Dropdown(options=[],
                                             description='Slice',
                                             layout=Layout(flex='2 0 0%'),
                                             disabled=True)
        self._image_title = widgets.Text(value='', description='Title:', continuous_update=False)

        def set_title(v):
            image_hdf = ImageHDF(self._tc, self.image)
            image_hdf.title = self._image_title.value
            self._image_selector.options = self.images_dictionary()
        self._image_title.observe(set_title, 'value')

        self._plot_pane = widgets.Output()
        with self._plot_pane:
            plt.ioff()
            self.fig, self.axes = plt.subplots(figsize=(5, 5), dpi=150, layout='constrained')
            self.fig.canvas.header_visible = False
            self.fig.canvas.toolbar_position = 'bottom'
            self.fig.canvas.toolbar_visible = 'fade-in-fade-out'
            self._im_ax = self.axes.imshow([[0]], origin='lower', interpolation='gaussian', cmap='inferno', extent=(0, 100, 0, 100))
            # Attach colour bar scale to RHS of image axes
            self.fig.colorbar(self._im_ax, ax=self.axes, shrink=0.6, label='Counts (kc/s)', pad=0.1)
            self.fig.get_layout_engine().set(w_pad=4 / 72, h_pad=4 / 72, hspace=0.2, wspace=0.2)
            self.axes.autoscale_on = True
            self.update_image(self.image)
            plt.ion()
            plt.show()

        if qc:
            self._bg_images_update = asyncio.create_task(self._update_options(qc))

        if self.image:
            widgets.link((self, 'image'), (self._image_selector, 'value'))

        image_with_slider = widgets.AppLayout(center=self._plot_pane, right_sidebar=self._count_range_control,
                                              grid_gap='20px', layout=Layout(align_items='center'))

        self._full_pane = widgets.GridspecLayout(10, 2)
        self._full_pane[:, 0] = image_with_slider
        self._full_pane[0, 1] = self._image_selector
        self._full_pane[1, 1] = self._image_slice
        self._full_pane[2, 1] = self._image_title
        if save:
            dirchoose, filechoose = SaveFig(self.fig).displayables()
            self._full_pane[3, 1] = dirchoose
            self._full_pane[4, 1] = filechoose
        else:
            self._save_fig = None

    def display(self):
        return self._full_pane

    async def _update_options(self, qc):
        s = qc.confocal.subscribe('confocal.stopped')
        while self._image_selector:
            await s.receive()
            self._image_selector.options = self.images_dictionary()

    def images_dictionary(self, filter_function=lambda _: True):
        with self._tc as th:
            filtered_nodes = filter(filter_function, th.list(root="/Confocal", data_type_prefix="Image"))
            filtered_nodes2 = filter(filter_function, th.list(root="/Confocal", data_type_prefix="AB"))
            n = sorted(chain(filtered_nodes, filtered_nodes2), key=Timestamp.extract_timestamp)

            def opt_label(x):
                if x._v_title:
                    return "{} ({})".format(x.name, x._v_title), x._v_pathname
                else:
                    return x.name, x._v_pathname

            return dict(map(opt_label, n))

    def latest_image(self, filter_function=lambda _: True):
        image_nodes = list(self.images_dictionary(filter_function).values())
        if image_nodes:
            return image_nodes[-1]
        else:
            return ''

    def update_contrast(self, change):
        (min_c, max_c) = change['new']
        self._im_ax.set_clim(min_c, max_c)
        self.fig.canvas.flush_events()

    def update_image(self, _):
        image_hdf = ImageHDF(self._tc, self.image)
        image_type = image_hdf.image_type
        img = None
        extents = None

        self._image_title.value = image_hdf.title

        if image_type == 'ABC':
            slices = image_hdf.data.shape[2]
            self._image_slice.options = range(slices)
            self._image_slice.disabled = False
        else:
            self._image_slice.options = []
            self._image_slice.disabled = True

        if image_type == 'XY':
            img = image_hdf.xy_image_data()
            self.axes.set_xlabel(r'X ($\mu$m)')
            self.axes.set_ylabel(r'Y ($\mu$m)')
            extents = [img[x] * 1e6 for x in ['x_range_start', 'x_range_end', 'y_range_start', 'y_range_end']]
        elif image_type == 'XZ':
            img = image_hdf.xz_image_data()
            self.axes.set_xlabel(r'X ($\mu$m)')
            self.axes.set_ylabel(r'Z ($\mu$m)')
            extents = [img[x] * 1e6 for x in ['x_range_start', 'x_range_end', 'z_range_start', 'z_range_end']]
        elif image_type == 'YZ':
            img = image_hdf.yz_image_data()
            self.axes.set_xlabel(r'Y($\mu$m)')
            self.axes.set_ylabel(r'Z ($\mu$m)')
            extents = [img[x] * 1e6 for x in ['y_range_start', 'y_range_end', 'z_range_start', 'z_range_end']]
        elif image_type == 'AB':
            img = image_hdf.xy_image_data()
            attrs = image_hdf.attrs
            self.axes.set_xlabel(r"X'($\mu$m)")
            self.axes.set_ylabel(r"Y'($\mu$m)")
            x = np.linalg.norm(attrs['a'] - attrs['o'])*1e6
            y = np.linalg.norm(attrs['b'] - attrs['o'])*1e6
            extents = [0, x, 0, y]
        elif image_type == 'ABC':
            img = image_hdf.xy_image_data(z_slice=1)
            attrs = image_hdf.attrs
            self.axes.set_xlabel(r"X'($\mu$m)")
            self.axes.set_ylabel(r"Y'($\mu$m)")
            x = np.linalg.norm(attrs['a'] - attrs['o'])*1e6
            y = np.linalg.norm(attrs['b'] - attrs['o'])*1e6
            extents = [0, x, 0, y]
        else:
            # unsupported
            return

        image_data = img['image'] * 1e-3
        self._count_range_control.min = 0.0
        self._count_range_control.max = np.max(np.ravel(image_data))
        self._count_range_control.value = (0.0, self._count_range_control.max)
        self._im_ax.set_extent(extents)
        self._im_ax.set_data(image_data)
        self.fig.canvas.flush_events()

    def label_pois(self, pois, offset=(0, 0, 0)):
        marker_x = [p[0]*1e6 for p in pois.values()]
        marker_y = [p[1]*1e6 for p in pois.values()]

        if self._scatter_ax:
            self._scatter_ax.remove()
            for label in self._labels:
                label.remove()
            self._labels = []

        ax = self._im_ax.axes
        extent = self._im_ax.get_extent()
        size_x = extent[1] - extent[0]
        size_y = extent[3] - extent[2]
        s = np.min([size_x, size_y]) * 5e-2
        self._scatter_ax = ax.scatter(marker_x, marker_y, color='white', zorder=2, marker='o', s=s, facecolors='None', edgecolors='white')
        label_distance = s
        label_angle = math.pi/4

        txt_offset_x = label_distance * math.cos(label_angle)
        txt_offset_y = label_distance * math.sin(label_angle)

        for poi, p in pois.items():
            l = ax.annotate(poi,
                            xy=(p[0]*1e6, p[1]*1e6),
                            textcoords='offset points',
                            color='white',
                            xytext=(txt_offset_x, txt_offset_y),
                            xycoords='data',
                            size=s*.5,
                            arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=-0.2', color='white'),
                            alpha=0.7)
            self._labels.append(l)

    #       self._labels = []
    #       labels = dict([(k, self.roi_data.pois[k]) for k in pois])
    #       for i, (poi, pos) in enumerate(labels.items()):
    #           txt_X = self.label_distance * math.sin(self.label_angle / 180 * math.pi)
    #           txt_Y = self.label_distance * math.cos(self.label_angle / 180 * math.pi)
    #           #            a = plt.annotate(poi, xy=(pos[0], pos[1]), textcoords='offset points', color='white', xytext=(txt_X, txt_Y), xycoords='data',
    #           #                             arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', color='white'), alpha=0.7)
    #           a = plt.annotate(poi, xy=(pos[0], pos[1]), textcoords='offset points', color='white',
    #                            xytext=(txt_X, txt_Y), xycoords='data',
    #                            alpha=0.7)
    #           self._labels.append(a)


    #        self._poi_markers = self._image_widget.axes.scatter([], [],
    #                                                            color='white',
    #                                                            zorder=2,
    #                                                            marker='o',
    #                                                            s=200,
    #                                                            facecolors='None',
    #                                                            edgecolors='white'

    #   def _update_poi_labels(self):
    #       pois = self.roi_data.poi_list
    #       x = list(map(lambda _: self.roi_data.pois[_][0], pois))
    #       y = list(map(lambda _: self.roi_data.pois[_][1], pois))
    #       ax = plt.gca()
    #       if self._scatter:
    #           self._scatter.remove()
    #       for a in self._labels:
    #           a.remove()
    #       self._labels = []
    #       labels = dict([(k, self.roi_data.pois[k]) for k in pois])
    #       for i, (poi, pos) in enumerate(labels.items()):
    #           txt_X = self.label_distance * math.sin(self.label_angle / 180 * math.pi)
    #           txt_Y = self.label_distance * math.cos(self.label_angle / 180 * math.pi)
    #           #            a = plt.annotate(poi, xy=(pos[0], pos[1]), textcoords='offset points', color='white', xytext=(txt_X, txt_Y), xycoords='data',
    #           #                             arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', color='white'), alpha=0.7)
    #           a = plt.annotate(poi, xy=(pos[0], pos[1]), textcoords='offset points', color='white',
    #                            xytext=(txt_X, txt_Y), xycoords='data',
    #                            alpha=0.7)
    #           self._labels.append(a)

    #    def _current_roi_change(self, c):
    #        self._update_selected_roi(c['new'])
    #        self._update_poi_labels()#
    #
    #   def _update_poi_labels(self):
    #       self._image_widget.axes.scatter()#

    #   def display_select_roi(self):
    #       layout = GridspecLayout(5, 3)
    #       layout[1, 0] = Dropdown()
    #       layout[1, 1] = Se
