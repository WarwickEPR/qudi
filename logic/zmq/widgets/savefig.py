from traitlets import HasTraits
import matplotlib.pyplot as plt
from ipyfilechooser import FileChooser
import ipywidgets as widgets
import os.path


class SaveFig(HasTraits):

    def __init__(self, fig :plt.Figure, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._fig = fig

    def display(self):
        formats = self._fig.canvas.get_supported_filetypes()
        save_format = widgets.SelectMultiple(options=list(sorted(formats)), descrption='Save format')
        dir_chooser = FileChooser(title="Save directory")
        dir_chooser.show_only_dirs = True
        save_stem = widgets.Text(description="Save filename stem")
        save_button = widgets.Button(description='Save')

        def save_figure(_):
            for form in save_format.value:
                path = os.path.join(dir_chooser.selected, save_stem.value + '.' + form)
                self._fig.savefig(path, format=form)

        save_button.on_click(save_figure)
        layout = widgets.HBox([dir_chooser, save_stem, save_format, save_button])
        return layout
