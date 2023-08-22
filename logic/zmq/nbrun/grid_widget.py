
from ipywidgets import GridspecLayout, Button, Layout, Label, Widget, AppLayout


class ProgressGridWidget(Widget):
    _label_layout = Layout(justify_content='center', height='auto', width='auto')

    _status_colour = {"NOT_STARTED": "lightgrey",
                      "STARTED": "blue",
                      "ERROR": "red",
                      "ABORTED": "orange",
                      "CANCELLED": "yellow",
                      "DONE": "green"}

    def __init__(self, points, stages, **kwargs):
        super(ProgressGridWidget, self).__init__(**kwargs)
        self.points = points
        self.stages = stages

        def swap_inc(x):
            u, v = x
            return v, u + 1

        self._point_index = dict(map(swap_inc, enumerate(points)))
        self._stage_index = dict(map(swap_inc, enumerate(stages)))

        self.grid = GridspecLayout(len(points) + 1, len(stages) + 1, width="80%")
        self.progress = Label(value="", style={'font_size': '14pt', 'background': 'lightgrey'},
                              layout=Layout(align_items="center", height="40px", width="80%", padding='30px',
                                            border="2px solid"))

        for i, result in enumerate(stages):
            self.grid[0, i + 1] = Label(result, style={'font_size': '14pt'}, layout=Layout(justify_content='center'))

        for i, poi in enumerate(points):
            self.grid[i + 1, 0] = Label(poi, style={'font_size': '14pt'}, layout=Layout(justify_content='center'))

        for j, result in enumerate(points):
            for i, poi in enumerate(stages):
                self.grid[j + 1, i + 1] = self._cell_label(" ")

    def display(self):
        return AppLayout(center=self.grid, footer=self.progress)

    def cell(self, poi, stage):
        return self.grid[self._point_index[poi], self._stage_index[stage]]

    def update_cell(self, poi, stage, status=None, summary=None):
        cell = self.cell(poi, stage)
        if status is not None:
            colour = self._status_colour.get(status, "grey")
            cell.style.background = colour
        if summary is not None:
            cell.value = summary

    def update_all(self, status={}, summary={}):
        # expect form status[poi][stage], summary[poi][stage]
        for poi in self.points:
            for stage in self.stages:
                try:
                    self.update_cell(poi, stage, status[poi][stage], summary[poi][stage])
                except KeyError:
                    pass

    def update_progress(self, msg: str):
        self.progress.value = msg

    @classmethod
    def _cell_label(cls, description):
        return Label(value=description, style={'background': 'lightgrey', 'font_size': '14pt', 'text_color': 'white'},
                     layout=Layout(align_items="center", height="40px", justify_content="center"))

