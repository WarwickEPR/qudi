import asyncio

from traitlets import HasTraits, Unicode, List

from .background import BgTask
from ..data.image import Rectangle, Cuboid
from .. data.tables_context import TablesContext
import time as tm
import numpy as np
import matplotlib.pyplot as plt
from ipywidgets import TwoByTwoLayout, Button, Text, Label, Dropdown, Accordion, FloatText, VBox, Layout, \
    SelectMultiple, HBox, FloatSlider, BoundedIntText, BoundedFloatText, AppLayout
from matplotlib.widgets import RectangleSelector
from . tilt import TiltWidget
from . cfm import ImageWidget
import logging


class RoiWidget(HasTraits):

    log = logging.getLogger('widget.roi')

    current_roi = Unicode()
    available_roi = List(Unicode())

    def __init__(self, tc: TablesContext, qc=None, **kwargs):
        super(RoiWidget, self).__init__(**kwargs)
        self._tc = tc
        self._qc = qc

        if qc:
            # ask for notifications about ROI changes
            pass

        self._rois_cache_time = 0
        self._rois_cache = self._rois_cached()
        if self._rois_cache:
            self.current_roi = next(iter(self._rois_cache.keys()))
        else:
            self.current_roi = ''

        self._image_widget = ImageWidget(tc, qc=qc, save=True)
        self._tilt_widget = TiltWidget(tc=tc, qc=qc)
        self._select_roi = self._roi_selection_dropdown()
        self._skew_control = self._skew()
        self._new_roi_control = self._fetch_from_qudi_button()
        self._select_pois = self._select_pois()
        self._tilt_pull_hdf()
        self._container = Accordion((HBox((self._select_roi, self._new_roi_control)),
                                    self._select_pois,
                                    self._image_widget.display(),
                                    self._tilt_widget.display(),
                                    self._skew_control),
                                    titles=['Select ROI', 'Select POIs', 'Image', 'Tilt', 'Skew & 3D'])
        self._container.selected_index = 0


        self._tilt_widget.observe(self._tilt_change)
        self.observe(lambda _: self._tilt_pull_hdf(), names=['current_roi'])

#        with self._tc as th:
#            roi = th.tables.get_node('/ROI', self.current_roi, classname=Table)

        pois = {'x': (1, 2, 3)}

    def display(self):
        return self._container

    @property
    def current_roi_name(self):
        if self.current_roi:
            return self.extract_roi_name(self.current_roi)
        else:
            return ''

    @property
    def current_roi_path(self):
        if self.current_roi.startswith('/'):
            return self.current_roi
        else:
            return self.current_roi_latest

    @property
    def current_roi_latest(self):
        rois = self._rois_cache
        if not self.current_roi:
            return ''
        return rois[self.current_roi_name][0]['path']

    @staticmethod
    def extract_roi_name(x):
        p = x.split('/')
        if len(p) > 1:
            return p[-2]
        else:
            return p[0]

    def _update_roi(self, _):
        if not self.current_roi:
            return
        images = self._fetch_roi_image_list(self.current_roi_name)
        self._tilt_pull_hdf()
        image_names = map(self.extract_roi_name, images)
        image_options = dict(zip(image_names, images))
        self._image_widget._image_selector.options = image_options

    # Callbacks

    def _tilt_change(self, _):
        if not self.current_roi:
            return
        with self._tc as th:
            n = th.tables.get_node(self.current_roi_path)
            n.attrs['tilt_p0'] = self._tilt_widget.p0
            n.attrs['tilt_p1'] = self._tilt_widget.p1
            n.attrs['tilt_p2'] = self._tilt_widget.p2
            n.attrs['tilt_reference'] = self._tilt_widget.pivot
            n.attrs['tilt_xynorm'] = self._tilt_widget.xy_norm

    def _tilt_pull_hdf(self):
        if not self.current_roi:
            return
        with self._tc as th, self._tilt_widget.hold_trait_notifications() as hold:
            try:
                n = th.tables.get_node(self.current_roi_path)
                self._tilt_widget.p0 = n.attrs['tilt_p0']
                self._tilt_widget.p1 = n.attrs['tilt_p1']
                self._tilt_widget.p2 = n.attrs['tilt_p2']
                self._tilt_widget.pivot = n.attrs['tilt_reference']
            except KeyError:
                z = [0.0, 0.0, 0.0]
                self._tilt_widget.pivot = z
                self._tilt_widget.p0 = z
                self._tilt_widget.p1 = z
                self._tilt_widget.p2 = z

    # Fetch data from HDF5

    def _rois_cached(self):
        cache_age = tm.time() - self._rois_cache_time
        if cache_age > 10 or not self._rois_cache:
            self._rois_cache = self._rois()
            self._rois_cache_time = tm.time()
        return self._rois_cache

    def _rois(self):
        with self._tc as th:
            rois = {}
            for group in th.tables.iter_nodes('/ROI', classname='Group'):
                roi_name = group._v_name
                poi_tables = []
                for node in group._f_iter_nodes(classname='Table'):
                    if node.name.startswith('pois'):
                        _, date, time = str(node.name).rsplit('_', 2)

                        roi_summary = {'path': node._v_pathname,
                                       'full_name': node.name,
                                       'name': roi_name,
                                       'date': date,
                                       'time': time,
                                       'points': node.nrows}
                        poi_tables.append(roi_summary)
                poi_tables = self._sort_by_timestamp(poi_tables)
                if poi_tables:
                    rois[roi_name] = poi_tables    # all versions in reverse time order

            # sort so latest ROI is at the top
            rois = dict([(k, rois[k]) for k in sorted(rois.keys(), key=lambda k: rois[k][0]['date']+rois[k][0]['time'], reverse=True)])
            return rois

    @staticmethod
    def _sort_by_timestamp(a):
        a.sort(key=lambda x: x['date'] + x['time'], reverse=True)
        return a

    def _fetch_roi_image_list(self, roi_name):
        images = {}
        with self._tc as th:
            for i in th.tables.walk_nodes(where='/ROI/'+roi_name, classname='Array'):
                if i.attrs['data_type'].startswith('Image'):
                    images[i._v_name] = i._v_pathname
        return images

    def _fetch_roi_metadata(self, roi_node):
        md = {}
        with self._tc as th:
            n = th.tables.get_node(roi_node)
            for x in ['image', 'tilt_p0', 'tilt_p1', 'tilt_p2', 'tilt_xy_norm', 'tilt_reference']:
                md[x] = n.attrs[x]
        return md

    @property
    def poi_list(self):
        if not self.current_roi:
            return []
        with self._tc as th:
            n = th.tables.get_node(self.current_roi_path)
            return [x['name'].decode('utf-8') for x in n.iterrows()]

    def pois_in_bounds(self, x0, y0, x1, y1):
        if not self.current_roi:
            return []
        with self._tc as th:
            n = th.tables.get_node(self.current_roi_path)
            where = "(x >= {}) & (x <= {}) & (y >= {}) & (y <= {})".format(x0, x1, y0, y1)
            return dict([(x['name'].decode('utf-8'), np.array([x['x'], x['y'], x['z']])) for x in n.where(where)])

    # UI elements

    def _roi_selection_dropdown(self):
        rois = self._rois_cached()

        latest = dict([(k, v[0]) for k, v in rois.items()])
        opts = list(map(lambda x: ("{} ({})".format(x['name'], x['points']), x['path']), latest.values()))
        dd = Dropdown(options=opts)
        if self.current_roi:
            dd.value = self.current_roi_path

        def update(_):
            self.current_roi = dd.value

        dd.observe(update)
        return dd

    def _fetch_from_qudi_button(self):
        l = Layout(width='30%', display='flex-inline')
        s = {'description_width': 'initial'}
        self._new_roi_text = Label("Create a new ROI in HDF5 from the current in Qudi as /ROI/<my_roi>_<date>_<time>.\nDo this whenever you remount or move manually, points can be imported from other ROIs and orientated/translated.")
        self._new_roi_name = Text(description='New ROI name: ', placeholder='patch-A', layout=l, style=s)
        self._new_roi_button = Button(description='Fetch current Qudi ROI', disabled=not self._qc)

        container = VBox((self._new_roi_text,
                          self._new_roi_name,
                          self._new_roi_button))

        async def ask_qudi_to_save_roi(name):
            await self._qc.roi.save_roi(name)

        def callback(_):
            if self._qc:
                name = None
                if self._new_roi_name.value:
                    name = self._new_roi_name.value
                asyncio.create_task(ask_qudi_to_save_roi(name))

        self._new_roi_button.on_click(callback)

        return container

    def _select_pois(self):

        self.select_pois = SelectMultiple(rows=10,
                                          options=list(self.poi_list))
        select_all_button = Button(description="All")
        select_none_button = Button(description="None")

        def select_all(_):
            self.select_pois.value = self.select_pois.options

        def select_none(_):
            self.select_pois.value = []

        select_all_button.on_click(select_all)
        select_none_button.on_click(select_none)

        return TwoByTwoLayout(top_left=self.select_pois, top_right=select_all_button, bottom_right=select_none_button)

    def _new_roi_panel(self):
        l = Layout(width='30%', display='flex-inline')
        s = {'description_width': 'initial'}
        self._new_roi_text = Label("Create a new empty ROI in HDF5 as /ROI/<my_roi>_<date>_<time> whenever you remount or move manually. Points can be imported from other ROIs and offsets applied.")
        self._new_roi_name = Text(description='New ROI name: ', placeholder='patch-A', layout=l, style=s)
        self._manual_stage_x = FloatText(description='Manual stage X (mm): ', value=0.0, layout=l, style=s)
        self._manual_stage_y = FloatText(description='Manual stage Y (mm): ', value=0.0, layout=l, style=s)
        self._new_roi_button = Button(description="Save new ROI & select", layout=l, style=s)
        self._new_roi_button.on_click(self._new_roi_action)
        return VBox((self._new_roi_text,
                     self._new_roi_name,
                     self._manual_stage_x,
                     self._manual_stage_y,
                     self._new_roi_button),
                    layout=Layout(width='80%', display='flex-inline'))

    def _skew(self):
        if not self._qc:
            return HBox()

        self._skew_iw = ImageWidget(tc=self._tc, qc=self._qc)

        def rscb(eclick, erelease):
            pass

        self._skew_rs = RectangleSelector(self._skew_iw._im_ax.axes, rscb, useblit=True, interactive=True)

        def angle(c):
            a = c['new']
            self._skew_rs.rotation = a

        s = {'description_width': 'initial'}
        self._skew_angle = FloatSlider(descriptio='Angle: ', min=-45, max=45)
        self._skew_angle.observe(angle, names='value')
        self._xy_resolution = BoundedIntText(description="XY points max", style=s, min=1, value=100, max=2000)
        self._z_resolution = BoundedIntText(description="Z points", style=s, min=1)
        self._z_centre = BoundedFloatText(description="Z centre (um)", style=s, min=0, max=300)
        self._z_up = BoundedFloatText(description="Z up (um)", style=s, min=0, max=300)
        self._z_down = BoundedFloatText(description="Z down (um)", style=s, min=0, max=300)
        self._skew_rectangle_height = Button(description="Z from rectangle centre", style=s)
        self._skew_take_rectangle = Button(description="Image skew rectangle", style=s)
        self._skew_take_cuboid = Button(description="Image skew cuboid", style=s)

        def hello(_):
            self.log.debug("Hello")

        def take_rectangle(_):
            tilt = self._tilt_widget.tilt
            rectangle = check_offset(Rectangle(skew_rectangle=self._skew_rs.geometry * 1e-6, tilt=tilt))
            sx, sy = rectangle.fixed_aspect_resolution(self._xy_resolution.value)
            self.log.info("Starting scan of rectangle {} size {}".format(rectangle, (sx, sy)))
            scan = self._qc.scan.start_rectangle_scan(rectangle=rectangle, size=(sx, sy))
            asyncio.create_task(scan)
            #bg_scan = BgScan(self._qc, scan, sx*sy)
            #app.footer = bg_scan.display_progress()
            #bg_scan.start()

        self._skew_take_rectangle.on_click(take_rectangle)

        right = VBox((self._xy_resolution, self._z_resolution,
                      self._z_centre, self._z_up, self._z_down,
                      self._skew_angle,
                      self._skew_rectangle_height,
                      self._skew_take_rectangle, self._skew_take_cuboid))
        app = AppLayout(center=self._skew_iw.display(), right_sidebar=right, pane_widths=[1, 4, 2])

        def rectangle_centre_z(_):
            tilt = self._tilt_widget.tilt
            rectangle = Rectangle(skew_rectangle=self._skew_rs.geometry * 1e-6, tilt=tilt)
            z = rectangle.centre[2] * 1e6
            self._z_centre.value = z
            #self.log.debug("Getting centre z: {} {} {}".format(z, rectangle.o, rectangle.centre))

        self._skew_rectangle_height.on_click(rectangle_centre_z)

        def check_offset(rectangle):
            if self._z_centre.value > 0:
                z_centre = self._z_centre.value * 1e-6
                z_offset = z_centre - rectangle.centre[2]
                return rectangle.displaced(z_offset)
            else:
                return rectangle

        def take_cuboid(_):
            tilt = self._tilt_widget.tilt
            z_up = self._z_up.value * 1e-6
            z_down = self._z_down.value * 1e-6
            height = z_up + z_down
            cuboid = check_offset(Cuboid(skew_rectangle=self._skew_rs.geometry * 1e-6, height=height, tilt=tilt)).displaced(-z_down)
            sx, sy = cuboid.fixed_aspect_resolution(self._xy_resolution)
            sz = self._z_resolution.value
            self.log.info("Starting scan of cuboid {} size {}".format(cuboid, (sx, sy, sz)))
            scan = self._qc.scan.start_cuboid_scan(cuboid=cuboid, size=(sx, sy, sz))
            asyncio.create_task(scan)

#            bg_scan = BgScan(self._qc, scan, sx*sy)
#            app.footer = bg_scan.display_progress()
#            bg_scan.start()

        self._skew_take_rectangle.on_click(take_rectangle)
        self._skew_take_cuboid.on_click(take_cuboid)

        return app

    def _new_roi_action(self, _):
        pass


class BgScan(BgTask):
    # Specialisation of BgTask to run a scan and allow cancellation
    def __init__(self, qc, scan, points, after=None):
        super(BgScan).__init__(scan, on_done=after, on_cancel=self.stop)
        self.qc = qc
        self.points = points
        self.points_done = 0

        async def updates():
            s = self.qc.scan.subscribe('scan.update')
            while not self.task.done():
                data = await s.receive()
                self.points_done = int(data['done'])

        #self._update_handling = asyncio.create_task(updates())

    def progress_str(self):
        return '{}/{}'.format(self.points_done, self.points)

    def update_progress(self):
        self.progress.description = self.progress_str()
        self.progress.value = self.points_done

    def setup_progress_bar(self):
        self.progress.min = 0
        self.progress.max = self.points
        self.update_progress()

    async def stop(self):
        await self.qc.scan.stop()

