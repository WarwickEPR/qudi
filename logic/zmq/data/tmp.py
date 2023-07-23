

# General form for an arbitrary NI controlled, image scan.
# Point in any order, with or without transformed coordinates
# see attributes for which interpretation to use
# (this may be interpreted more simply if the scan pattern is known)
class ConfocalImage(tables.IsDescription):
    x = tables.Float32Col(pos=0)
    y = tables.Float32Col(pos=1)
    z = tables.Float32Col(pos=2)
    count_rate = tables.Float32Col(pos=3)

# 2D image slices in parametric coordinates are stored as gzip compressed arrays


# Used by both Qudi and client side of ZMQ based remoting system


class RoiImage(HasTraits):

    roi_data = Instance(klass=RoiData)
    label_angle = Float()
    label_distance = Float()
    visible_pois = Set()

    _image = None
    _image_pane = None
    _roi_chooser = None
    _full_pane = None
    _scatter = None
    _file_chooser_roi_image = None
    _file_chooser_pois = None
    _labels = []

    def __init__(self, roi_data=None, input_base=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if roi_data is None:
            self.roi_data = RoiData()
        else:
            self.roi_data = roi_data
            self._image = XYImage(image_data=roi_data.image)

        if input_base is not None:
            self._input_base = input_base

        self.roi_data.observe(self.update)

        self.label_distance = 10
        self.label_angle = -45

    def update(self):
        self._image_pane.update()

    def display_file_chooser(self):
        fc1 = FileChooser()
        if self._input_base:
            fc1.default_path = self._input_base
        fc1.title = "ROI image file (.npy)"
        fc1.filter_pattern = r'*scan_image.npy'
        fc1.layout.width = '80%'
        fc1.register_callback(lambda fc: self.roi_data.set_image_from_npy(fc.selected))
        self._file_chooser_roi_image = fc1

        fc2 = FileChooser()
        if self._input_base:
            fc2.default_path = self._input_base
        fc2.title = "POI list"
        fc2.filter_pattern = r'*_poi_list.dat'
        fc2.layout.width = '80%'
        fc2.register_callback(lambda fc: self.roi_data.set_pois_from_qudi(fc.selected))
        self._file_chooser_pois = fc2

        return widgets.VBox([fc1, fc2])

    def display_poi_select(self):
        pois = self.roi_data.poi_list
        selection = widgets.SelectMultiple(options=pois, value=pois, rows=10, description="Labelled")
        all_button = widgets.Button(description='All')
        none_button = widgets.Button(description='None')

        def select_all(_):
            selection.value = pois

        def select_none(_):
            selection.value = []

        def change_angle(change):
            angle = change['new']

        all_button.on_click(select_all)
        none_button.on_click(select_none)
        angle = widgets.FloatSlider(description='Label orientation', min=-180, max=180, value=-45,
                                    continuous_update=True, step=5, readout=True)
        angle.observe(change_angle, names='value')
        color = widgets.ColorPicker(description='Label colour', concise=True)

        return widgets.VBox([selection, all_button, none_button])

    def display(self):
        self._image_pane = self._image.display()
        self._poi_select = self.display_poi_select()
        self._layout = widgets.HBox([self._image_pane, self._poi_select])
        self._layout = self._image_pane
        self._update_poi_labels()

        def pois_changed(_):
            self._update_poi_labels()

        self.roi_data.observe(pois_changed, names='pois')

        return self._layout

    def _update_poi_labels(self):
        pois = self.roi_data.poi_list
        X = list(map(lambda _: self.roi_data.pois[_][0], pois))
        Y = list(map(lambda _: self.roi_data.pois[_][1], pois))
        ax = plt.gca()
        if self._scatter:
            self._scatter.remove()
        for a in self._labels:
            a.remove()
        self._labels = []
        self._scatter = ax.scatter(X, Y, color='white', zorder=2, marker='o', s=200, facecolors='None', edgecolors='white')
        labels = dict([(k, self.roi_data.pois[k]) for k in pois])
        for i, (poi, pos) in enumerate(labels.items()):
            txt_X = self.label_distance * math.sin(self.label_angle / 180 * math.pi)
            txt_Y = self.label_distance * math.cos(self.label_angle / 180 * math.pi)
#            a = plt.annotate(poi, xy=(pos[0], pos[1]), textcoords='offset points', color='white', xytext=(txt_X, txt_Y), xycoords='data',
#                             arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0', color='white'), alpha=0.7)
            a = plt.annotate(poi, xy=(pos[0], pos[1]), textcoords='offset points', color='white', xytext=(txt_X, txt_Y), xycoords='data',
                             alpha=0.7)
            self._labels.append(a)



class ConfocalImage(traitlets.HasTraits):

    image_data = traittypes.Array()
    extents = traitlets.Tuple()

    def __init__(self, image_data=None, extents=None):
        super().__init__()

        if image_data is not None:
            self.image_data = image_data

        if extents is not None:
            self.extents = extents

    @default('image_data')
    def _default_image_data(self):
        return np.zeros((1, 1))

    @validate('image_data')
    def _valid_image_data(self, proposal):
        return proposal['value']

    @default('extent')
    def _default_extents(self):
        return 0, 1, 0, 1

    @validate('extents')
    def _valid_extents(self, proposal):
        return proposal['value']

    def set_image_from_npy(self, path):
        with self.hold_trait_notifications():
            data = np.load(path)
            self.image_data = np.flipud(data)

    @staticmethod
    def image_from_npy(path):
        data = np.load(path)
        return np.flipud(data)
