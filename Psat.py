import numpy as np
import time

# define the powers, note that there needs to be a conversion to mW for the command to laser
powers = np.array([1,2,3,4,5,6,7,8,9,10])
powers = np.linspace(1,50,20)
#powers = np.array([1,2])
convertmW = 1000
mWpowers = powers/convertmW

# this is currently a very dumb way to do it. How does the program know when autofocus is finished.

for mW in mWpowers:
    print(mW)
    # laser power is in Watts, so value should represent that (ie 0.001 = 1 mW)
    laser.sigPower.emit(mW)
    # Wait for laser to stabilise (about 20 seconds should be fine)
    time.sleep(30)
    # do a refocus
    #confocal.refocus_clicked()
    # start saving
    counter_nicard.save_clicked()
    # record for time
    time.sleep(120)
    # stop saving
    counter_nicard.save_clicked()
    # Make sure data is saved before the next iteration of the loop
    time.sleep(10)

laser.sigPower.emit(0.001)