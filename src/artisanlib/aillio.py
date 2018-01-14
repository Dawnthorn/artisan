#!/usr/bin/env python

import usb1

# TODO:
#    1) Figure out the VID/PID/endpoints/ports/interface
#    2) Figure out how to communicate with the device
#    3) Figure out if we can communicate async or if we need a special process
#    4) 

class AillioR1:
    AILLIO_USB_VID = 0x0483
    AILLIO_USB_PID = 0x5781
    AILLIO_USB_ENDPOINT = 0x12
    AILLIO_USB_INTERFACE = 0x1


    def __init__(self, logger):
        self.logger = logger
        self.logger.debug('AillioR1.__init__')
        self.usbContext = None
        self.usbHandle = None


    def __del__(self):
        self.close()


    def open(self):
        if self.usbHandle is not None:
            return
        self.usbContext = usb1.USBContext()
        self.usbHandle = self.usbContext.openByVendorIDAndProductID(self.AILLIO_USB_VID, self.AILLIO_USB_PID, skip_on_error=True)
        if self.usbHandle is None:
            raise Exception("AillioR1 device not found at %x:%x." % (self.AILLIO_USB_VID, self.AILLIO_USB_PID))
            return
        self.logger.info("AillioR1 found.")
        self.usbHandle.claimInterface(self.AILLIO_USB_INTERACE)


    def close(self):
        if self.usbHandle is not None:
            self.usbHandle.releaseInterface(self.AILLIO_USB_INTERACE)
            self.usbHandle.close()
        if self.usbContext is not None:
            self.usbContext.close()


    def beanAndEnvironmentalTemp(self):
        self.logger.debug('AillioR1.beanAndEnvironmentalTemp')
        return 0,0,0


    def heaterAndFanSpeed(self):
        self.logger.debug('AillioR1.heaterAndFanSpeed')
        return 0,0,0


    def modeAndDrumSpeed(self):
        self.logger.debug('AillioR1.modeAndDrumSpeed')
        return 0,0,0


    def on(self):
        self.logger.debug('AillioR1.on')
        self.open()


    def prs(self):
        self.logger.debug('AillioR1.prs')


    def start(self):
        self.logger.debug('AillioR1.start')


    def stop(self):
        self.logger.debug('AillioR1.stop')


    def setstate(self, heater=None, fan=None, drum=None):
        self.logger.debug('AillioR1.setstate(%d, %d, %d)', heater, fan, drum)




if __name__ == "__main__":
    import logger
    logger = logging.getLogger('artisian')
    R1 = AillioR1(logger)
    R1.on()
    R1.start()
    R1.setstate()
    R1.beanAndEnvironmentalTemp()
    R1.stop()
