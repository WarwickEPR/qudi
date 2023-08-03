import asyncio

from traitlets import Tuple, Float, HasTraits
import traitlets
from .. client import QudiControl
from ipywidgets import Button, Layout, BoundedFloatText


class PositionWidget(HasTraits):
    p = Tuple(Float(), Float(), Float())

    @traitlets.default('p')
    def _default_p(self):
        return 0, 0, 0

    def __init__(self, min_value=0.0, max_value=300.0, qc=None, **kwargs):
        super(PositionWidget, self).__init__(**kwargs)
        self.min_value = min_value
        self.max_value = max_value
        self._qc = qc
        #self._confocal.monitor_position_changes()
        self.description = 'Get position'
        self._x = BoundedFloatText(min=self.min_value, max=self.max_value, layout=Layout(width='70%'))
        self._y = BoundedFloatText(min=self.min_value, max=self.max_value, layout=Layout(width='70%'))
        self._z = BoundedFloatText(min=self.min_value, max=self.max_value, layout=Layout(width='70%'))
        traitlets.link((self, 'p'), (self._x, 'value'), transform=[(lambda p: p[0]*1e6), (lambda x: (x*1e-6, self.p[1], self.p[2]))])
        traitlets.link((self, 'p'), (self._y, 'value'), transform=[(lambda p: p[1]*1e6), (lambda y: (self.p[0], y*1e-6, self.p[2]))])
        traitlets.link((self, 'p'), (self._z, 'value'), transform=[(lambda p: p[2]*1e6), (lambda z: (self.p[0], self.p[1], z*1e-6))])
        self._button = Button(description='Get position')
        self._button.on_click(self._click)

    @property
    def button(self):
        return self._button

    @property
    def entry_x(self):
        return self._x

    @property
    def entry_y(self):
        return self._y

    @property
    def entry_z(self):
        return self._z

    def _click(self, _):
        async def update_position():
            x, y, z = await self._qc.confocal.get_position()
            self.p = (x, y, z)

        if self._qc:
            asyncio.create_task(update_position())
