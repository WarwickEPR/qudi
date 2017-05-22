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
timeBin = 500
noBins = 2000
# zero point happens in the middle of the plot 
maxTime = ((noBins*timeBin)/2)/1e3
minTime = -maxTime
# make the row for the time bins
timeRow = np.linspace(minTime,maxTime,(noBins+1))

# start the correlation
coin = tt.Correlation(tagger, 0, 1, binwidth=timeBin, n_bins=noBins)

time.sleep(120)
# coin.stop()
# confocal.refocus_clicked()
# coin.start()
# time.sleep(60)
	
# Save the data at the end
with open(r"C:\Users\Confocal\Desktop\g2data.csv", 'w', newline='') as csvfile:
	g2writer = csv.writer(csvfile)
	g2writer.writerows([timeRow,coin.getData()])		
# refocus Plot, stop and clear g2
confocal.refocus_clicked()
plt.plot(coin.getData())
plt.show()
coin.stop()
# ready for next one
coin.clear()