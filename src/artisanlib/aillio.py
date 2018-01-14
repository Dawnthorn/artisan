#!/usr/bin/env python

import construct
import usb1

class AillioR1:
    AILLIO_USB_VID = 0x0483
    AILLIO_USB_PID = 0x5741
    AILLIO_USB_INTERFACE = 0x1
    AILLIO_USB_READ_ENDPOINT = 0x1
    AILLIO_USB_WRITE_ENDPOINT = 0x3


    def __init__(self, logger):
        self.logger = logger
        self.logger.debug('AillioR1.__init__')
        self.usbContext = None
        self.usbHandle = None
        self.transferList = []
        self.latestStats = construct.Container(
            beanTemperature = 0.0,
            ror = 0.0,
            drumTemperature = 0.0,
            fan = 0,
            power = 0,
            drumSpeed = 0,
            index = 0,
            canary = 0,
        )
        self.latestStatus = construct.Container(
            mode = 0,
        )
        self.statsStruct = construct.Struct(
            'beanTemperature' / construct.Float32l,
            'ror' / construct.Float32l,
            'drumTemperature' / construct.Float32l,
            'unknown1' / construct.Array(14, construct.Byte),
            'fan' / construct.Int8ul,
            'power' / construct.Int8ul,
            'drumSpeed' / construct.Int8ul,
            'unknown2' / construct.Int8ul,
            'index' / construct.Int16ul,
            'unknown3' / construct.Array(28, construct.Byte),
            'canary' / construct.Int32ul,
        )
        self.statusStruct = construct.Struct(
            'energy' / construct.Float32l,
            'unknown1' / construct.Array(36, construct.Byte),
            'preheatTemperature' / construct.Int8ul,
            'unknown2' / construct.Int8ul,
            'mode' / construct.Int8ul,
            'unknown3' / construct.Array(21, construct.Byte),
        )


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
        if self.usbHandle.kernelDriverActive(self.AILLIO_USB_INTERFACE):
            self.usbHandle.detachKernelDriver(self.AILLIO_USB_INTERFACE)
        self.usbHandle.claimInterface(self.AILLIO_USB_INTERFACE)


    def close(self):
        if self.usbHandle is not None:
            self.usbHandle.releaseInterface(self.AILLIO_USB_INTERFACE)
            self.usbHandle.close()
        if self.usbContext is not None:
            self.usbContext.close()


    def environmentAndBeanTemperature(self):
        self.logger.debug('AillioR1.environmentAndBeanTemperature')
        return self.toFahrenheit(self.latestStats.drumTemperature), self.toFahrenheit(self.latestStats.beanTemperature)


    def toFahrenheit(self, celsius):
        return celsius * 9 / 5 + 32


    def heaterAndFanSpeed(self):
        self.logger.debug('AillioR1.heaterAndFanSpeed')
        return self.latestStats.power, self.latestStats.fan


    def modeAndDrumSpeed(self):
        self.logger.debug('AillioR1.modeAndDrumSpeed')
        return self.latestStatus.mode, self.latestStats.drum


    def on(self):
        self.logger.debug('AillioR1.on')
        self.open()


    def prs(self):
        self.logger.debug('AillioR1.prs')
        self.writePacket(bytearray([0x30, 0x01, 0x0, 0x0]), self.writePrsCompleted)
        self.waitForTransfers()


    def writePrsCompleted(self, transfer):
        self.logger.debug('AillioR1.writePrsCompleted')
        self.transferList.remove(transfer)
        if transfer.getStatus() != usb1.TRANSFER_COMPLETED:
            raise Exception("Error sending stats write command: %d" % (transfer.getStatus()))


    def sample(self):
        self.logger.debug('AillioR1.sample')
        self.requestStats()
        self.waitForTransfers()


    def start(self):
        self.logger.debug('AillioR1.start')
        if self.latestStatus.mode == 0:
            self.prs()


    def stop(self):
        self.logger.debug('AillioR1.stop')


    def setstate(self, heater=None, fan=None, drum=None):
        self.logger.debug('AillioR1.setstate(%d, %d, %d)', heater, fan, drum)


    def readPacket(self, length, callback):
        transfer = self.usbHandle.getTransfer()
        transfer.setBulk(self.AILLIO_USB_READ_ENDPOINT | usb1.ENDPOINT_IN, length, callback)
        transfer.submit()
        self.transferList.append(transfer)


    def writePacket(self, packet, callback):
        transfer = self.usbHandle.getTransfer()
        transfer.setBulk(self.AILLIO_USB_WRITE_ENDPOINT | usb1.ENDPOINT_OUT, packet, callback)
        transfer.submit()
        self.transferList.append(transfer)


    def requestStats(self):
        self.logger.debug('AllioR1.requestStats')
        self.writePacket(bytearray([0x30, 0x01]), self.statsWriteCompleted)


    def statsWriteCompleted(self, transfer):
        self.logger.debug('AllioR1.statsWriteCompleted')
        self.transferList.remove(transfer)
        if transfer.getStatus() != usb1.TRANSFER_COMPLETED:
            raise Exception("Error sending stats write command: %d" % (transfer.getStatus()))
        self.readPacket(64, self.statsReadReady)


    def statsReadReady(self, transfer):
        self.logger.debug('AllioR1.statsReadReady')
        self.transferList.remove(transfer)
        if transfer.getStatus() != usb1.TRANSFER_COMPLETED:
            raise Exception("Error in stats read transfer: %d" % (transfer.getStatus()))
        stats = self.statsStruct.parse(transfer.getBuffer())
        if stats.canary == 2868903935:
            self.logger.debug('AllioR1: got stats %d' % (stats.index))
            self.latestStats = stats
            self.requestStatus()
        else:
            self.logger.debug('AllioR1: got stats finished')


    def requestStatus(self):
        self.logger.debug('AllioR1.requestStatus')
        self.writePacket(bytearray([0x30, 0x03]), self.statusWriteCompleted)


    def statusWriteCompleted(self, transfer):
        self.logger.debug('AllioR1.statusWriteCompleted')
        self.transferList.remove(transfer)
        if transfer.getStatus() != usb1.TRANSFER_COMPLETED:
            raise Exception("Error sending status write command: %d" % (transfer.getStatus()))
        self.readPacket(64, self.statusReadReady)


    def statusReadReady(self, transfer):
        self.logger.debug('AllioR1.statusReadReady')
        self.transferList.remove(transfer)
        if transfer.getStatus() != usb1.TRANSFER_COMPLETED:
            raise Exception("Error in status read transfer: %d" % (transfer.getStatus()))
        self.latestStatus = self.statusStruct.parse(transfer.getBuffer())
        self.requestStats()


    def waitForTransfers(self):
        while any(transfer.isSubmitted() for transfer in self.transferList):
            self.usbContext.handleEvents()


if __name__ == "__main__":
    import logging
    logger = logging.getLogger('artisian')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)
    R1 = AillioR1(logger)
    R1.on()
    R1.sample()
