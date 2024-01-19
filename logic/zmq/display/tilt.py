import asyncio

from traitlets import HasTraits, Float, Tuple
from ipywidgets import Label, Layout, GridspecLayout, Button
import traitlets
import numpy as np
from .position import PositionWidget
from .. data.tilt import Tilt


class TiltWidget(HasTraits):
    pivot_t = Tuple(Float(), Float(), Float())
    p0_t = Tuple(Float(), Float(), Float())
    p1_t = Tuple(Float(), Float(), Float())
    p2_t = Tuple(Float(), Float(), Float())

    def __init__(self, qc=None, **kwargs):
        super(TiltWidget, self).__init__(qc=qc, **kwargs)

        self._pivot = PositionWidget(qc=qc, **kwargs)
        self._p0 = PositionWidget(qc=qc, **kwargs)
        self._p1 = PositionWidget(qc=qc, **kwargs)
        self._p2 = PositionWidget(qc=qc, **kwargs)

        self.layout = GridspecLayout(6, 5, layout=Layout(width='80%', display='flex-inline'))
        self.layout[0, 1] = Label(value='x (um)')
        self.layout[0, 2] = Label(value='y (um)')
        self.layout[0, 3] = Label(value='z (um)')
        if qc:
            self._qc = qc
            self.layout[0, 4] = b = Button(description='Send to Qudi')
            b.on_click(self._set_tilt)
            self.layout[1, 4] = self._pivot.button
            self.layout[2, 4] = self._p0.button
            self.layout[3, 4] = self._p1.button
            self.layout[4, 4] = self._p2.button

        self.layout[1, 0] = Label(value='Pivot point')
        self.layout[2, 0] = Label(value='p0')
        self.layout[3, 0] = Label(value='p1')
        self.layout[4, 0] = Label(value='p2')
        self.layout[5, 0] = Label(value='Tilt (mrad)')
        self.layout[1, 1] = self._pivot.entry_x
        self.layout[1, 2] = self._pivot.entry_y
        self.layout[1, 3] = self._pivot.entry_z
        self.layout[2, 1] = self._p0.entry_x
        self.layout[2, 2] = self._p0.entry_y
        self.layout[2, 3] = self._p0.entry_z
        self.layout[3, 1] = self._p1.entry_x
        self.layout[3, 2] = self._p1.entry_y
        self.layout[3, 3] = self._p1.entry_z
        self.layout[4, 1] = self._p2.entry_x
        self.layout[4, 2] = self._p2.entry_y
        self.layout[4, 3] = self._p2.entry_z

        self.layout[5, 1:2] = self.tilt_x = Label()
        self.layout[5, 3:4] = self.tilt_y = Label()
#        self.layout[5, 1] = self.tilt_x = HTMLMath(value='', layout=Layout(display='flex-inline', flex_flow='row'))
#        self.layout[5, 2] = self.tilt_y = HTMLMath(value='', layout=Layout(display='flex-inline', flex_flow='row'))
        self.observe(self._update_tilt)

        traitlets.link((self, 'pivot_t'), (self._pivot, 'p'))
        traitlets.link((self, 'p0_t'), (self._p0, 'p'))
        traitlets.link((self, 'p1_t'), (self._p1, 'p'))
        traitlets.link((self, 'p2_t'), (self._p2, 'p'))

        self.tilt = Tilt()
        self._update_tilt(None)

    @traitlets.default('p0_t')
    def _default_p0_t(self):
        return 0, 0, 0

    @traitlets.default('p1_t')
    def _default_p1_t(self):
        return 0, 0, 0

    @traitlets.default('p2_t')
    def _default_p2_t(self):
        return 0, 0, 0

    @traitlets.default('pivot_t')
    def _default_pivot_t(self):
        return 0, 0, 0

    @property
    def p0(self):
        return np.array([*self.p0_t])

    @p0.setter
    def p0(self, v):
        self.p0_t = tuple(v)

    @property
    def p1(self):
        return np.array([*self.p1_t])

    @p1.setter
    def p1(self, v):
        self.p1_t = tuple(v)

    @property
    def p2(self):
        return np.array([*self.p2_t])

    @p2.setter
    def p2(self, v):
        self.p2_t = tuple(v)

    @property
    def pivot(self):
        return np.array([*self.pivot_t])

    @pivot.setter
    def pivot(self, v):
        self.pivot_t = tuple(v)

    def _update_tilt(self, _):
        self.tilt = Tilt(pivot=self.pivot, p0=self.p0, p1=self.p1, p2=self.p2)
        self.tilt_x.value = '{:.3f}'.format(self.tilt.theta_x * 1e3)
        self.tilt_y.value = '{:.3f}'.format(self.tilt.theta_y * 1e3)

    def point_from_xy(self, x, y):
        return self.tilt.point_from_xy(x, y)

    def _set_tilt(self, _):

        async def send_tilt():
            await self._qc.confocal.set_tilt(tilt_x=self.tilt.xy_norm[0],
                                             tilt_y=self.tilt.xy_norm[1],
                                             reference_x=self.tilt.pivot[0],
                                             reference_y=self.tilt.pivot[1])

        if self._qc:
            asyncio.create_task(send_tilt())

    def display(self):
        return self.layout
