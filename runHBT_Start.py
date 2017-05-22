## G2 data iPython

# should really run when Qudi is restarted
import time
import csv
import numpy as np
import matplotlib.pyplot as plt
import TimeTagger as tt
tagger = timetaggerSlow._tagger

## create the measurement and stop it ready for later
# time is in picoseconds
timeBin = 1000
noBins = 2000
# zero point happens in the middle of the plot 
maxTime = ((noBins*timeBin)/2)/1e3
minTime = -maxTime
# make the row for the time bins
timeRow = np.linspace(minTime,maxTime,(noBins+1))

# start the correlation (iterate start stop just to clear last if not a fresh reload)
coin = tt.Correlation(tagger, 0, 1, binwidth=timeBin, n_bins=noBins)
coin.start()