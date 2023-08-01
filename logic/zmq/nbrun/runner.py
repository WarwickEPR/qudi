import asyncio
import logging

from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError
import nbformat
from ipywidgets import GridspecLayout, Button, Layout, Label
from IPython.display import JSON
import IPython
import json
from .. data.timestamp import get_timestamp
from traitlets import HasTraits, Unicode, default

from IPython.core.magic import line_magic, magics_class, Magics
from ipykernel.comm import Comm

# at the start of sections of measurement add:
# %start_measurement rabi
# this will tag all saved cells from there until the %end_measurement with  "measurement_rabi"
# Any variables starting "rabi" will be saved
# Special variables are:
# rabi_status: which expected to be 'DONE', 'FAILED' or 'INCOMPLETE'
# rabi_summary: a short summary string which is displayed in the output grid
#
# Cells which have not been run are scanned as strings for lines starting "%start_measurement" to find what outputs are
# expected and what entry points are available after executed cells for potentially resuming
#
# After each cell executes, the notebook is saved
# The parameters and any saved state are prepended to the notebook in cells tagged 'params' and 'state' respectively
# Inline output of executed cells is saved for display


@magics_class
class MeasurementTrack(Magics):
    def __init__(self, ip:IPython):
        super(MeasurementTrack, self).__init__(ip)
        self.current_measurement = None
        self.measurement_state = {}
        self.measurement_status = {}
        self.measurement_summary = {}
        self.shell = ip

        self.comm = Comm(target_name='status_log', data={})

    def send_status(self, msg):
        self.comm.send(msg)

    def _get(self, name, default_value=None):
        return self.shell.user_ns.get(name, default_value)

    def _save_measurement(self):
        for k, v in self.shell.user_ns.items():
            if k.startswith(self.current_measurement):
                self.measurement_state[k] = v
        status_key = '{}_status'.format(self.current_measurement)
        summary_key = '{}_summary'.format(self.current_measurement)
        self.measurement_status[status_key] = self._get(status_key, 'INCOMPLETE')
        self.measurement_summary[summary_key] = self._get(summary_key, ' ')

    @classmethod
    def setup(cls):
        ip = IPython.get_ipython()
        mt = MeasurementTrack(ip)
        ip.events.register('post_run_cell', mt.post_run_cell)
        ip.register_magics(mt)
        return mt

    def post_run_cell(self, result):
        if self.current_measurement is not None:
            self._save_measurement()

    @line_magic
    def start_measurement(self, line):
        self.shell.user_ns['measurement'] = line
        self.current_measurement = line

    @line_magic
    def checkpoint(self, line):
        if line:
            checkpoint = line
        else:
            checkpoint = self.current_measurement
        return JSON({'checkpoint': checkpoint,
                     'state': self.measurement_state,
                     'status': self.measurement_status,
                     'summary': self.measurement_summary}, expanded=False)


class CommLog(HasTraits):
    latest_message = Unicode()

    @default(latest_message)
    def _latest_message(self):
        return ''

    def __init__(self, *args, **kwargs):
        super(CommLog, self).__init__(*args, **kwargs)

    def handle_msg(self, msg):
        data = msg['content']['data']
        self.latest_message.value = data


class RunHelper:

    @classmethod
    def checkpoint(cls, name, params):
        params['name'] = name
        return JSON(params)


class Runner:

    def __init__(self, f):
        self._nb_template_filename = None
        self._nb_template = None
        self._reloaded = False
        self._checkpoints = []
        self._results = {}

    # The notebook to load can either be a template for per-poi execution or an auto-saved notebook from a past run
    def load_template_notebook(self, f):
        self._nb_template_filename = f
        self._nb_template = nbformat.read(f, as_version=4)

    def load_run_notebook(self, f):
        nb = nbformat.read(f, as_version=4)
        for cell in nb.cells:

            # find all cells with line "%start_measurement <foo>"

            # if start at checkpoint - inject the state from the specified checkpoint at the start
            # on save, tag checkpoints so we can find them as entry points
            # also tag all the cells after a "start_measurement" to the checkpoint so we can run preamble and
            # skip to checkpoint

            # cells with metadata.result set are expected to output a JSON object for in-progress reporting
            if 'result' in cell.metadata:
                # expect this cell to output a JSON result of a measurement on execution
                result_name = cell.metadata.result
                self._results[result_name] = {}
                try:
                    for output in cell.outputs:
                        if 'application/json' in output['data']:
                            self._results[result_name] = json.loads(output['data']['application/json'])
                            break
                except KeyError:
                    pass
                except json.JSONDecodeError:
                    pass

            # Cells with metadata.checkpoint_load=name set are entry points from a previous run which can be restarted from
            # On save, a cell with metadata.checkpoint_load=name is injected after the checkpoint output and executes as
            # normal to reload those variables
            # Here we're just inspecting to get the available checkpoints
            if 'checkpoint_load' in cell.metadata:
                self._checkpoints.append(cell.metadata.checkpoint_load)

            if 'parameters' in cell.metadata.tags:
                self._reloaded = True

    def make_grid(self, pois):

        def button(description, button_style):
            return Button(description=description, button_style=button_style,
                          layout=Layout(height='auto', width='auto'))

        if self._results.keys():
            results = self._results.keys()
            grid = GridspecLayout(len(results)+1, len(pois)+1)

            for i, result in enumerate(results):
                grid[i+1, 0] = Label(result)

            for j, poi in enumerate(pois):
                grid[0, j+1] = Label(poi)

            for i, result in enumerate(results):
                for j, poi in enumerate(pois):
                    grid[i+1, j+1] = button(" ", 'primary')

    @classmethod
    def first_tag_index(cls, nb, tag):
        for i, c in enumerate(nb.cells):
            try:
                tags = c.metadata.tags
                if tag in tags:
                    return i
            except KeyError:
                pass
        return None

    @classmethod
    def inject_params(cls, nb, poi: str, params: dict):
        params['poi'] = poi # override
        params_str = ''
        for k, v in params.items():
            params_str += ['{}={}'.format(k,v)]
        params_cell = nbformat.v4.new_code_cell(source='\n'.join(params_str))
        params_cell.metadata = {'tags': 'parameters'}

        params_index = cls.first_tag_index(nb, 'parameters')
        if params_index is not None:
            # replace the cell
            nb.cells[params_index] = params_cell
        else:
            # insert at start
            nb.cells.insert(0, params_cell)

        return nb

    @classmethod
    def inject_saved_state(cls, nb, saved_state=None):
        saved_state_str = []
        if saved_state:
            for k, v in saved_state.items():
                saved_state_str += ['{}={}'.format(k, v)]
        saved_state_cell = nbformat.v4.new_code_cell(source='\n'.join(saved_state_str))
        saved_state_cell.metadata = {'tags': 'saved_state'}

        saved_state_index = cls.first_tag_index(nb, 'saved_state')
        if saved_state_index is not None:
            nb.cells[saved_state_index] = saved_state_cell
        else:
            params_index = cls.first_tag_index(nb, 'parameters')
            if params_index is not None:
                # after parameters cell
                nb.cells.insert(params_index, saved_state_cell)
            else:
                # first
                nb.cells.insert(0, saved_state_cell)

        return nb

    def run_notebook_from_template(self, poi:str, params, saved_state=None):
        nb = self._nb_template
        nb = self.inject_params(nb, poi, params)
        if saved_state is not None:
            nb = self.inject_saved_state(nb, saved_state)
        nbformat.validate(nb)  # Raises nbformat.ValidationError on fault
        poi_file = self._nb_template_filename.replace('.ipynb', '-{}-{}.ipynb'.format(poi, get_timestamp()))
        nbformat.write(nb, poi_file)
        nc = NotebookClient(nb, kernel_name="python3")
        with nc.setup_kernel():
            nb_task = asyncio.create_task(self.execute_cells(nc, nb))

    async def execute_cells(self, nc, nb):
        for i, c in enumerate(nb.cells):
            try:
                result = await nc.async_execute_cell(c, i)
                # if the cell is a checkpoint, insert a saved_state cell
                # if measurement_status changes - send an update to the Grid
                # save notebook
            except CellExecutionError:
                # log failure and stop
                return

