#!/usr/bin/env python

import construct
import usb1
from .usb_transfer_exception import UsbTransferException

class BulletR1(object):
    instance = None

    USB_VID = 0x0483
    USB_PID = 0x5741
    USB_INTERFACE = 0x1
    USB_READ_ENDPOINT = 0x1
    USB_WRITE_ENDPOINT = 0x3

    MODE_OFF = 0x0
    MODE_PREHEATING = 0x2
    MODE_LOAD_BEANS = 0x4
    MODE_ROASTING = 0x6
    MODE_COOLING = 0x8
    MODE_SHUT_DOWN = 0x9

    def __init__(self, logger):
        self.logger = logger
        self.logger.debug('BulletR1.__init__')
        self.usbContext = None
        self.usbHandle = None
        self.transferList = []
        self.latestStats = construct.Container(
            beanTemperature = -1,
            ror = -1,
            drumTemperature = -1,
            fanSpeed = -1,
            heaterPower = -1,
            drumSpeed = -1,
            index = -1,
            canary = -1,
        )
        self.latestStatus = construct.Container(
            mode = -1,
        )
        self.statsStruct = construct.Struct(
            'beanTemperature' / construct.Float32l,
            'ror' / construct.Float32l,
            'drumTemperature' / construct.Float32l,
            'unknown1' / construct.Array(14, construct.Byte),
            'fanSpeed' / construct.Int8ul,
            'heaterPower' / construct.Int8ul,
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


    def __new__(cls, logger):
        if not BulletR1.instance:
            BulletR1.instance = super(BulletR1, cls).__new__(cls)
        return BulletR1.instance


    def beanTemperature(self):
        return self.latestStats.beanTemperature


    def close(self):
        if self.usbHandle is not None:
            self.usbHandle.releaseInterface(self.USB_INTERFACE)
            self.usbHandle.close()
        if self.usbContext is not None:
            self.usbContext.close()


    def cool(self):
        self.logger.debug('BulletR1.cool')
        self.untilMode(self.MODE_COOLING)


    def drumSpeed(self):
        return self.latestStats.drumSpeed


    def drumTemperature(self):
        return self.latestStats.drumTemperature


    def fanDown(self):
        self.logger.debug('BulletR1.fanUp')
        currentSpeed = self.fanSpeed()
        self.writePacket(bytearray([0x31, 0x02, 0xaa, 0xaa]), "fanUp")
        self.waitForTransfers()
        while currentSpeed == self.fanSpeed():
            self.requestStats()
            self.waitForTransfers()


    def fanSpeed(self):
        return self.latestStats.fanSpeed


    def fanUp(self):
        self.logger.debug('BulletR1.fanUp')
        currentSpeed = self.fanSpeed()
        self.writePacket(bytearray([0x31, 0x01, 0xaa, 0xaa]), "fanUp")
        while currentSpeed == self.fanSpeed():
            self.requestStats()
            self.waitForTransfers()


    def heaterPower(self):
        return self.latestStats.heaterPower


    def loadBeans(self):
        self.logger.debug('BulletR1.loadBeans')
        self.untilMode(self.MODE_LOAD_BEANS)


    def mode(self):
        return self.latestStatus.mode


    def off(self):
        self.logger.debug('BulletR1.off')
        self.untilMode(self.MODE_OFF)


    def on(self):
        self.logger.debug('BulletR1.on')
        self.open()


    def open(self):
        if self.usbHandle is not None:
            return
        self.usbContext = usb1.USBContext()
        self.usbHandle = self.usbContext.openByVendorIDAndProductID(self.USB_VID, self.USB_PID, skip_on_error=True)
        if self.usbHandle is None:
            raise Exception("BulletR1 device not found at %x:%x." % (self.USB_VID, self.USB_PID))
            return
        self.logger.info("BulletR1 found.")
        if self.usbHandle.kernelDriverActive(self.USB_INTERFACE):
            self.usbHandle.detachKernelDriver(self.USB_INTERFACE)
        self.usbHandle.claimInterface(self.USB_INTERFACE)


    def preheat(self):
        self.logger.debug('BulletR1.preheat')
        self.untilMode(self.MODE_PREHEATING)


    def prs(self):
        self.logger.debug('BulletR1.prs')
        currentMode = self.mode()
        self.writePacket(bytearray([0x30, 0x01, 0x0, 0x0]), "writePrs")
        while currentMode == self.mode():
            self.requestStats()
            self.waitForTransfers()


    def readPacket(self, length, errorMsg, callback):
        transfer = self.usbHandle.getTransfer()
        transfer.callback = callback
        transfer.errorMsg = errorMsg
        transfer.setBulk(self.USB_READ_ENDPOINT | usb1.ENDPOINT_IN, length, self.transferCompleted)
        transfer.submit()
        self.transferList.append(transfer)


    def requestStats(self):
        self.logger.debug('BulletR1.requestStats')
        self.writePacket(bytearray([0x30, 0x01]), "requestStats", self.statsWriteCompleted)


    def requestStatus(self):
        self.logger.debug('BulletR1.requestStatus')
        self.writePacket(bytearray([0x30, 0x03]), "requestStatus", self.statusWriteCompleted)


    def roast(self):
        self.logger.debug('BulletR1.roast')
        self.untilMode(self.MODE_ROASTING)


    def sample(self):
        self.logger.debug('BulletR1.sample')
        self.requestStats()
        self.waitForTransfers()


    def setDrumSpeed(self, speed):
        self.logger.debug('BulletR1.setDrumSpeed(%d)' % (speed))


    def setFanSpeed(self, speed):
        self.logger.debug('BulletR1.setFanSpeed(%d)' % (speed))
        if self.fanSpeed() < 0:
            return
        if self.mode() != self.MODE_ROASTING:
            return
        while self.fanSpeed() != speed:
            if self.fanSpeed() < speed:
                self.fanUp()
            else:
                self.fanDown()


    def setPower(self, power):
        self.logger.debug('BulletR1.setPower(%d)' % (power))


    def statsReadReady(self, transfer):
        self.logger.debug('BulletR1.statsReadReady')
        stats = self.statsStruct.parse(transfer.getBuffer())
        if stats.canary == 2868903935:
            self.logger.debug('BulletR1: got stats %d' % (stats.index))
            self.latestStats = stats
            self.requestStatus()
        else:
            self.logger.debug('BulletR1: got stats finished')


    def statsWriteCompleted(self, transfer):
        self.logger.debug('BulletR1.statsWriteCompleted')
        self.readPacket(64, "statsRead", self.statsReadReady)


    def statusReadReady(self, transfer):
        self.logger.debug('BulletR1.statusReadReady')
        self.latestStatus = self.statusStruct.parse(transfer.getBuffer())
        self.requestStats()


    def statusWriteCompleted(self, transfer):
        self.logger.debug('BulletR1.statusWriteCompleted')
        self.readPacket(64, "statusRead", self.statusReadReady)


    def toFahrenheit(self, celsius):
        return celsius * 9 / 5 + 32


    def transferCompleted(self, transfer):
        self.transferList.remove(transfer)
        statusCode = transfer.getStatus()
        if statusCode != usb1.TRANSFER_COMPLETED:
            raise UsbTransferException("USB Transfer failed during %s: %s (%d)" % (transfer.errorMsg, UsbTransferException.statusCodeToString(statusCode), statusCode))
        if transfer.callback is not None:
            transfer.callback(transfer)


    def untilMode(self, requestedMode):
        while self.mode() != requestedMode:
            self.prs()


    def waitForTransfers(self):
        while any(transfer.isSubmitted() for transfer in self.transferList):
            self.usbContext.handleEvents()


    def writePacket(self, packet, errorMsg, callback = None):
        transfer = self.usbHandle.getTransfer()
        transfer.callback = callback
        transfer.errorMsg = errorMsg
        transfer.setBulk(self.USB_WRITE_ENDPOINT | usb1.ENDPOINT_OUT, packet, self.transferCompleted)
        transfer.submit()
        self.transferList.append(transfer)



if __name__ == "__main__":
    import logging
    logger = logging.getLogger('artisian')
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.DEBUG)
    R1 = BulletR1(logger)
    R1.on()
    R1.sample()
