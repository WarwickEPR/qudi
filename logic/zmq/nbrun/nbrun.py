import asyncio

import nbformat
from nbclient import NotebookClient
from . track import TrackProgress
import logging
import re
import traceback


class NBRun:

    def __init__(self, notebook=None):
        stages = []
        if notebook:
            self.nb = nbformat.read(notebook, as_version=4)
            self.output_filename = notebook.replace('.ipynb', '-out.ipynb')
            stages = self.find_tracked_stages(self.nb)
        self.tracker = TrackProgress()
        self.log = logging.getLogger('NBRun')
        self.cell_task = None
        self.checkpoint = {}
        self.nc = None
        self.status = dict([(k, "NOT_STARTED") for k in stages])
        self.summary = dict([(k, " ") for k in stages])

    def _comm_open_handler(self, msg):
        return self.tracker

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
    def find_tracked_stages(cls, nb):
        stages = []
        # find any "%start <foo>" magic at the start of any line of any cell
        start_patt = re.compile(r"^%start\s+(\w+)", re.MULTILINE)
        for c in nb.cells:
            if c['cell_type'] == 'code':
                m = re.search(start_patt, c['source'])
                if m:
                    stages.append(m.group(1))
        return stages

    @classmethod
    def inject_params(cls, nb, poi: str, params: dict):
        params['poi'] = poi   # override
        params_str = ''
        for k, v in params.items():
            params_str += ['{}={}'.format(k,v)]
        params_cell = nbformat.v4.new_code_cell(source='\n'.join(params_str))
        params_cell.metadata = {'tags': 'parameters'}

        params_index = cls.first_tag_index(nb, 'parameters')
        if params_index is not None:
            # replace the params cell if present
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

    async def _execute_cell(self, nc: NotebookClient, cell:nbformat.NotebookNode, cell_index):
        cell_output = await nc.async_execute_cell(cell, cell_index)
        try:
            if cell_output['metadata']['type'] == 'checkpoint':
                # expect JSON checkpoint
                cp_data = cell_output['data']['application/json']
                self.checkpoint[cp_data['checkpoint']] = cp_data['state']
                self.status.update(cp_data['status'])
                self.summary.update(cp_data['summary'])
        except KeyError:
            pass
        return cell_output

    async def run(self, poi=None, parameters: dict = None):
        nc = NotebookClient(self.nb)
        nc.comm_open_handlers['progress'] = self._comm_open_handler
        self.nc = nc

        if poi is not None:
            nb = self.inject_params(self.nb, poi=poi, params=parameters)
        else:
            nb = self.nb

        async with nc.async_setup_kernel():
            for i, c in enumerate(nb.cells):
                cell = nbformat.from_dict(c)

                ok = False
                try:
                    self.cell_task = asyncio.create_task(self._execute_cell(nc, cell, i))
                    cell_output = await self.cell_task
                    ok = True
                except asyncio.CancelledError:
                    self.log.info("Run cancelled on cell {}".format(i))
                except Exception as e:
                    self.log.warning("Exception raised in cell {}: {} {}".format(i, type(e), e))
                finally:
                    nbformat.write(self.nb, self.output_filename)
                if not ok:
                    break

