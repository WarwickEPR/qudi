
try:
    pulsedmasterlogic
except:
    print("Pulsed modules not loaded")

try:
    optimizerlogic
except:
    print("Optimizerlogic not loaded")

# Create handlers for refocusing that pause a running pulsed measurement

def pulsed_running():
    try:
        return pulsedmasterlogic.status_dict['measurement_running']
    except:
        return False

def pulsed_paused():
    try:
        return pulsed_running() and not pulsedmasterlogic.status_dict['pulser_running']
    except:
        return False

def on_refocusing(tag):
    if pulsed_running() and not pulsed_paused():
        pulsedmasterlogic.log.info("Refocusing, pausing")
        pulsedmasterlogic.pause_measurement()
        # nicard.set_voltage(5.0)

def on_refocused(tag,pos):
    if pulsed_running() and pulsed_paused():
        pulsedmasterlogic.log.info("Refocused, unpausing")
        #nicard.set_voltage(7.0)
        pulsedmasterlogic.continue_measurement()


optimizerlogic.sigRefocusStarted.connect(on_refocusing)
optimizerlogic.sigRefocusFinished.connect(on_refocused)