import asyncio
import logging
import re
import nbformat
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError
from nbformat import NotebookNode
from ipywidgets import Output
from IPython.display import display

from .track import TrackProgress, NbClientCommManager
from .wait import InterruptableWaitHandle


class Notebook(nbformat.NotebookNode):

    def __init__(self, *args, **kwargs):
        super(Notebook, self).__init__(*args, **kwargs)

    def first_tag_index(self, tag):
        for i, c in enumerate(self.cells):
            try:
                tags = c.metadata.tags
                if tag in tags:
                    return i
            except AttributeError:
                pass
        return None

    def find_tracked_stages(self):
        stages = []
        # find any "%start <foo>" magic at the start of any line of any cell
        start_patt = re.compile(r"^%start\s+(\w+)", re.MULTILINE)
        for c in self.cells:
            if c['cell_type'] == 'code':
                m = re.search(start_patt, c['source'])
                if m:
                    stages.append(m.group(1))
        return stages

    def inject_params(self, poi: str, params: dict):
        params['poi'] = poi   # override
        params_str = []

        for k, v in params.items():
            if isinstance(v, str):
                v_enc = "r'{}'".format(v)
            else:
                v_enc = v
            params_str += ['{}={}'.format(k, v_enc)]
        params_cell = nbformat.v4.new_code_cell(source='\n'.join(params_str))
        params_cell.metadata = {'tags': 'parameters'}

        params_index = self.first_tag_index('parameters')
        if params_index is not None:
            # replace the params cell if present
            self.cells[params_index] = params_cell
        else:
            # insert at start
            self.cells.insert(0, params_cell)

    def inject_saved_state(self, saved_state=None):
        saved_state_str = []
        if saved_state:
            for k, v in saved_state.items():
                saved_state_str += ['{}={}'.format(k, v)]
        saved_state_cell = nbformat.v4.new_code_cell(source='\n'.join(saved_state_str))
        saved_state_cell.metadata = {'tags': 'saved_state'}

        saved_state_index = self.first_tag_index('saved_state')
        if saved_state_index is not None:
            self.cells[saved_state_index] = saved_state_cell
        else:
            params_index = self.first_tag_index('parameters')
            if params_index is not None:
                # after parameters cell
                self.cells.insert(params_index, saved_state_cell)
            else:
                # first
                self.cells.insert(0, saved_state_cell)

    def update_attachments(self, attachments):
        attachment_patt = re.compile(r'\(attachment:(.*)\)')
        updated = False
        #logger = logging.getLogger('Notebook')
        for cell in self.cells:
            if cell['cell_type'] == 'markdown':
                #logger.debug("Checking markdown cell for attachment reference")
                match = re.search(attachment_patt, cell['source'])
                if match:
                    attachment = match.group(1)
                    #logger.debug("Found attachment reference: {}".format(attachment))
                    if attachment in attachments:
                        if attachment.endwith('.png'):
                            #logger.debug("inserting attachment {}".format(attachment))
                            cell['attachments'] = {'data': attachments[attachment]}
                            updated = True
        return updated

    def save(self, filename, attachments=None, force=False):
        if (attachments and self.update_attachments(attachments)) or force:
            #logging.getLogger('Notebook').info("Saving to {}".format(filename))
            nbformat.write(self, filename)


class NBRun:

    def __init__(self, notebook=None, notebook_template=None):
        self.stages = []
        self.log = logging.getLogger('NBRun')

        if notebook:
            self.nb = Notebook(nbformat.read(notebook, as_version=4))
            self.nb_filename = notebook
            self.output_filename = notebook.replace('.ipynb', '-out.ipynb')
            self.stages = self.nb.find_tracked_stages()
        elif notebook_template:
            self.nb_template = Notebook(nbformat.read(notebook_template, as_version=4))
            self.nb_template_filename = notebook_template
            self.stages = self.nb_template.find_tracked_stages()
        else:
            self.log.error("No notebook or template supplied")

        self.comm_manager = NbClientCommManager()
        self.tracker = TrackProgress()
        self.wait_stop_handle = InterruptableWaitHandle()

        self.comm_manager.handlers['progress'] = self.tracker.handle_msg
        self.comm_manager.handlers['stop_file'] = self.wait_stop_handle.set_stop_file
        self.cell_task = None
        self.poi = None
        self.nc = None
        self.run_output = {}
        self.attachments = {}

    @staticmethod
    def _initialize_output(stages):
        return {'status': dict([(k, "NOT_STARTED") for k in stages]),
                'summary': dict([(k, " ") for k in stages]),
                'checkpoint': {}}

    def apply_parameters_to_template(self, poi, params):
        self.nb = self.nb_template
        self.nb.inject_params(poi, params)
        self.output_filename = self.nb_template_filename.replace('.ipynb', '-{}.ipynb'.format(poi))

    def update_attachments(self, name, data):
        self.attachments[name] = data
        nb = Notebook(self.nb)
        nb.save(self.output_filename, attachments=self.attachments)

    def save(self, force=False):
        nb = Notebook(self.nb)
        nb.save(self.output_filename, attachments=self.attachments, force=force)

    def stop(self):
        # interrupt the running notebook if in an interruptable wait
        self.wait_stop_handle.stop()

    def on_cell_complete(self, cell=None, cell_index=None):
        self.log.debug("Cell [{}] complete: {}".format(cell_index, cell))
        self.save(force=True)

        try:
            if cell['metadata']['type'] == 'checkpoint':
                # expect JSON checkpoint output
                cp_data = cell['data']['application/json']
                self.run_output[self.poi]['checkpoint'][cp_data['checkpoint']] = cp_data['state']
                self.run_output[self.poi]['status'].update(cp_data['status'])
                self.run_output[self.poi]['summary'].update(cp_data['summary'])
        except KeyError:
            # not present so nothing to do
            pass

    def on_cell_error(self, cell=None, cell_index=None, execute_reply=None):
        content = execute_reply['content']
        exception = content['ename']
        traceback = content.get('traceback', '')
        if exception == 'CancelledError':
            self.log.info("Cell [{}] cancelled".format(cell_index))
            self.run_out.append_stdout("Cancelled in cell [{}]".format(cell_index))
        else:
            self.log.error("Cell [{}] exception: {}".format(cell_index, exception))
            self.run_out.append_stderr("Exception from cell [{}]: {}".format(cell_index, exception))
            if traceback:
                self.log.error(traceback)
                self.run_out.append_stderr(traceback)

    def on_notebook_start(self, notebook=None):
        self.log.debug("Notebook started. Output to '{}'".format(self.output_filename))

    def on_notebook_complete(self, notebook=None):
        self.log.debug("Notebook completed. Output to '{}'".format(self.output_filename))

    def on_notebook_error(self, notebook=None):
        self.log.debug("Notebook finished with an error. Output to '{}'".format(self.output_filename))

    async def run_all(self, pois_and_parameters: dict):
        stages = self.nb_template.find_tracked_stages()

        # set up output
        for poi, params in pois_and_parameters.items():
            self.run_output[poi] = self._initialize_output(stages)

        # run on each notebook
        for poi, params in pois_and_parameters.items():
            if not self.wait_stop_handle.stopped:
                await self.run(poi, params)
                await asyncio.sleep(5)

    def track_latest(self):
        from ipywidgets import Label, link
        from IPython.display import display
        lbl = Label("")
        link((self.tracker, 'latest_message'), (lbl, 'value'))
        display(lbl)

    async def run(self, poi=None, parameters: dict = None):

        self.run_out = Output()
        display(self.run_out)

        if poi is None:
            stages = self.nb_template.find_tracked_stages()
            self.run_output[None] = self._initialize_output(stages)
        else:
            self.apply_parameters_to_template(poi=poi, params=parameters)
            self.poi = poi

        if not self.nb:
            if self.nb_template:
                self.log.error("No notebook prepared. Apply parameters to template.")
            else:
                self.log.error("No notebook provided")
            return

        self.log.debug("Saving to {} before running".format(self.output_filename))
        self.save(force=True)
        self.log.debug("Saved")

        nc = NotebookClient(self.nb,
                            timeout=None,
                            store_widget_state=True,
                            on_cell_complete=self.on_cell_complete,
                            on_notebook_complete=self.on_notebook_complete,
                            on_notebook_start=self.on_notebook_start,
                            on_notebook_error=self.on_notebook_error,
                            on_cell_error=self.on_cell_error)
        self.comm_manager.add_comm_open_handlers(nc)
        self.nc = nc

        try:
            self.log.debug("Executing notebook")
            await nc.async_execute(reset_kc=False)
        except CellExecutionError as e:
            if e.ename == 'CancelledError':
                self.log.info("Execution cancelled running notebook on poi {}".format(self.poi))
                self.run_out.append_stdout("Execution cancelled running notebook on poi {}".format(self.poi))
            else:
                self.log.error("Exception in cell execution {}({})".format(e.ename, e.evalue))
                self.log.error(e.traceback)
                self.run_out.append_stderr("Exception {}({})\n".format(e.ename, e.evalue) + e.traceback)

                raise
        except Exception as e:
            self.log.debug("Exception {}".format(e))
            self.log.exception("Something unexpected went wrong")
            self.run_out.append_stderr("Unexpected exception {}".format(e))
            raise
        finally:
            self.log.info("Notebook execution on poi {} finished".format(self.poi))
            # save notebook
            self.save(force=True)
            self.poi = None
