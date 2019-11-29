
def ensure_logic_started(module_list):
    # requires these modules to be preloaded
    for m in module_list:
        if not manager.isModuleLoaded('logic',m):
            print('{} is not loaded, starting'.format(m))
            manager.startModule('logic',m)

def bind_common_notifications():
    ensure_logic_started(['scannerlogic','aomlogic','hbtlogic','odmrlogic','optimizerlogic','pulsedmeasurementlogic']);

    def refocus_done(*x):
        kernellogic.notify_kernels('refocus done')
        if pulsedmeasurementlogic.module_state() == 'locked':
            pulsedmeasurementlogic.continue_pulsed_measurement()

    def refocus_started(*x):
        if pulsedmeasurementlogic.module_state() == 'locked':
            pulsedmeasurementlogic.pause_pulsed_measurement()

    #kernellogic.bind_notification(optimizerlogic.sigRefocusFinished,'refocus done')
    optimizerlogic.sigRefocusStarted.connect(refocus_started)
    optimizerlogic.sigRefocusFinished.connect(refocus_done)


    kernellogic.bind_notification(scannerlogic.signal_xy_image_updated,'xy image done')
    kernellogic.bind_notification(scannerlogic.signal_depth_image_updated,'depth image done')
    kernellogic.bind_notification(scannerlogic.signal_xy_data_saved,'xy image saved')
    kernellogic.bind_notification(scannerlogic.signal_depth_data_saved,'depth image saved')

    kernellogic.bind_notification(aomlogic.psat_updated,'psat done')
    kernellogic.bind_notification(aomlogic.psat_fit_updated,'psat fit done')
    kernellogic.bind_notification(aomlogic.psat_saved,'psat saved')

    kernellogic.bind_notification(hbtlogic.hbt_updated,'hbt done')
    #kernellogic.bind_notification(hbtlogic.hbt_fit_updated,'psat fit done')
    kernellogic.bind_notification(hbtlogic.hbt_saved,'hbt saved')

    kernellogic.bind_notification(odmrlogic.sigOutputStateUpdated,'odmr output change')
    kernellogic.bind_notification(odmrlogic.sigOdmrFitUpdated,'odmr fit done')

def bind_pulsed_notifications():
    ensure_logic_started(['pulsedmasterlogic'])
    kernellogic.bind_notification(pulsedmasterlogic.sigPredefinedSequenceGenerated,'predefined generated')
    kernellogic.bind_notification(pulsedmasterlogic.sigLoadedAssetUpdated,'asset loaded')
    kernellogic.bind_notification(pulsedmasterlogic.sigMeasurementStatusUpdated,'measurement status updated')
    kernellogic.bind_notification(pulsedmasterlogic.sigFitUpdated,'pulsed fit updated')

def bind_pause_pulsed():
    ensure_logic_started(['pulsedmeasurementlogic'])
    optimizerlogic.sigRefocusStarted.connect(pulsedmeasurementlogic.pause_pulsed_measurement)
    optimizerlogic.sigRefocusFinished.connect(pulsedmeasurementlogic.continue_pulsed_measurement)

def unbind_pause_pulsed():
    ensure_logic_started(['pulsedmeasurementlogic'])
    optimizerlogic.sigRefocusStarted.disconnect(pulsedmeasurementlogic.pause_pulsed_measurement)
    optimizerlogic.sigRefocusFinished.disconnect(pulsedmeasurementlogic.continue_pulsed_measurement)

