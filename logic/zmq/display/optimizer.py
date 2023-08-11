import asyncio
import matplotlib.pyplot as plt
from ..data.optimizer import OptimizerImage
from ipywidgets import Output


class NoTablesContext(Exception):
    pass


class RefocusDisplay:

    def __init__(self, tc=None, qc=None):
        self.output = Output()
        self.tc = tc
        self.qc = qc.optimizer
        self.update_task = None
        self.on_update = None

    def display_inline(self, datasource):
        if isinstance(datasource, str):
            if self.tc is not None:
                data = OptimizerImage.load(self.tc, datasource)
            else:
                raise NoTablesContext
        else:
            data = datasource
        self._display_inline(data)

    def get_image(self):
        try:
            return self.output.outputs[0]['data']
        except (KeyError, IndexError):
            return None

    def _display_inline(self, data: OptimizerImage):

        fig, (ax1, ax2) = plt.subplots(1, 2, layout='constrained', figsize=(10, 3))
        fig.get_layout_engine().set(w_pad=1)
        fig.suptitle('Focus optimization on <{}> at {}'.format(data.poi, data.timestamp))

        # xy plot
        extents = [data.setup[k]*1e6 for k in ['x0', 'x1', 'y0', 'y1']]
        _image = ax1.imshow(data.xy_data * 1e-3, interpolation='gaussian', cmap='inferno', extent=extents)
        plt.colorbar(_image, label='Counts (kc/s)', fraction=0.04, pad=0.04)
        ax1.grid(True)
        ax1.set_xlabel(r'X (um)')
        ax1.set_ylabel(r'Y (um)')

        # z plot
        ax2.scatter(data.z_data['z']*1e6, data.z_data['counts']*1e-3)
        ax2.grid(True)
        ax2.set_xlabel(r'Z (um)')
        ax2.set_ylabel(r'Counts (kc/s)')

        # clear_output with context_manager should get fixed sometime, has problems with threads?
        # clear the old output in a nasty way so that inline updates don't make the sheet unreadable
        #clear_output(wait=True)
        self.output.outputs = []
        self.output.append_display_data(fig)

        if self.on_update:
            self.on_update()

    def update_on_save(self):

        # forever (or until this kernel is shutdown) in the background, update on save
        async def listen_for_save():
            s = self.qc.subscribe('optimizer.saved_hdf5')
            while True:
                save_location = await s.receive()
                try:
                    self.display_inline(save_location.body['path'])
                except KeyError:
                    pass
                except asyncio.CancelledError:
                    break

        self.update_task = asyncio.create_task(listen_for_save(), name="update_refocus_display")

    def __del__(self):
        self.update_task.cancel()
