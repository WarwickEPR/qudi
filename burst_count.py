## short bin countrate in bursts iPython

# should really run when Qudi is restarted
import time
import csv
import math
import numpy as np
import matplotlib.pyplot as plt
import TimeTagger as tt

tagger = timetaggerSlow._tagger
channels = [0, 1]


class BurstCount:

    def __init__(self, bin_width, number):
        self.frequency = 1e6 / bin_width;
        self.measurement = tt.Counter( tagger,
                                       channels=channels,
                                       n_values=number,
                                       binwidth=int(bin_width*1e6) )

    def take(self):
        data = self.measurement.getData()
        total = data[0] + data[1]
        return total * self.frequency

    def histogram(self, bins):
        data = self.take()
        data = list(filter(lambda x: x > 0, data))
        plt.hist(data, bins=bins)
        plt.ylabel('freq')
        plt.xlabel('counts')

    def plot(self,limit=None):
        data = self.take()
        t = self.measurement.getIndex() * 1e-6
        if limit is not None:
            decimation = int(len(data) / limit);
            data = data[0:-1:decimation]
            t = t[0:-1:decimation]

        plt.plot(t, data)
        plt.ylabel('counts')
        plt.xlabel('time (us)')

    def ft(self):
        data = self.take()
        t = self.measurement.getIndex() * 1e-12
        y = np.fft.fft(data)
        f = np.fft.fftfreq(len(data), t[1]-t[0])
        start = int(math.floor(len(y)*.5-1))
        y = np.abs(y)
        plt.plot(f[0:start], y[0:start])
        plt.ylabel('Intensity (counts/Hz)')
        plt.xlabel('Frequency (Hz)')

    def figure(self,bins=200):
        plt.figure()
        plt.subplot(311)
        self.plot(500)
        plt.subplot(312)
        self.histogram(bins)
        plt.subplot(313)
        self.ft()
