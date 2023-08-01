import asyncio

from traitlets import HasTraits, Unicode, List
from .. data.tables_context import TablesContext
import time as tm
import numpy as np
import matplotlib.pyplot as plt
from ipywidgets import TwoByTwoLayout, Button, Text, Label, Dropdown, Accordion, FloatText, VBox, Layout, \
    SelectMultiple, HBox, FloatSlider, BoundedIntText, BoundedFloatText, AppLayout
from matplotlib.widgets import RectangleSelector
from . tilt import TiltWidget
from . cfm import ImageWidget


class PulsedMeasurementWidget(HasTraits):

    selected_measurement = Unicode()

    def __init__(self, tc: TablesContext, qc=None, **kwargs):
        super(PulsedMeasurementWidget, self).__init__(**kwargs)
        self._tc = tc
        self._qc = qc

    def plot_measurement(self, path):
        with self.tc as th:
            node = th.get_node(path)
            if node