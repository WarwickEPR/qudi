## G2 data iPython

# should really run when Qudi is restarted
import csv
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import animation
import TimeTagger as tt
tagger = timetaggerSlow._tagger

## create the measurement and stop it ready for later
# time is in picoseconds
timeBin = 500
noBins = 2000
# zero point happens in the middle of the plot
maxTime = ((noBins*timeBin)/2)/1e3
minTime = -maxTime
# make the row for the time bins
timeRow = np.linspace(minTime,maxTime,(noBins+1))

# start the correlation (iterate start stop just to clear last if not a fresh reload)
coin = tt.Correlation(tagger, 0, 1, binwidth=timeBin, n_bins=noBins)
coin.stop()
coin.clear()
coin.start()

fig, ax = plt.subplots()
line, = ax.plot([], [], 'k-')
ax.margins(0.05)

def init():
    yinitData = np.zeros(noBins)
    line.set_data(timeRow[:noBins],yinitData)
    return line,

def animate(i):
    xdata = timeRow[:noBins]
    ydata = coin.getData()
    yAverage = ydata / (np.average(ydata[:100]))
    line.set_data(xdata, yAverage)
    ax.relim()
    ax.autoscale()
    return line,

anim = animation.FuncAnimation(fig, animate, init_func=init, interval=25)

plt.show()

def saveHBT():
    with open(r"C:\Users\Confocal\Desktop\g2data.csv", 'w', newline='') as csvfile:
        g2writer = csv.writer(csvfile)
        g2writer.writerows([timeRow, coin.getData()])
    # Plot, stop and clear
    #plt.plot(coin.getData())
    #plt.show()

    coin.stop()
    coin.clear()

def clearHBT():
    coin.stop()
    coin.clear()