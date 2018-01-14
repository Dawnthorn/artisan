#!/usr/bin/env python

import construct
import usb1
from usb_transfer_exception import UsbTransferException

class BulletR1:
    AILLIO_USB_VID = 0x0483
    AILLIO_USB_PID = 0x5741
    AILLIO_USB_INTERFACE = 0x1
    AILLIO_USB_READ_ENDPOINT = 0x1
    AILLIO_USB_WRITE_ENDPOINT = 0x3

    TRANSFER_STATUS_TO_STRING = {
        usb1.TRANSFER_COMPLETED: 'completed',
        usb1.TRANSFER_ERROR: 'error',
        usb1.TRANSFER_TIMED_OUT: 'timed out',
        usb1.TRANSFER_CANCELLED: 'cancelled',
        usb1.TRANSFER_STALL: 'stalled',
        usb1.TRANSFER_NO_DEVICE: 'no device',
        usb1.TRANSFER_OVERFLOW: 'overflow',
    }

    def __init__(self, logger):
        self.logger = logger
        self.logger.debug('BulletR1.__init__')
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


    def close(self):
        if self.usbHandle is not None:
            self.usbHandle.releaseInterface(self.AILLIO_USB_INTERFACE)
            self.usbHandle.close()
        if self.usbContext is not None:
            self.usbContext.close()


    def environmentAndBeanTemperature(self):
        self.logger.debug('BulletR1.environmentAndBeanTemperature')
        return self.latestStats.drumTemperature, self.latestStats.beanTemperature

    def heaterAndFanSpeed(self):
        self.logger.debug('BulletR1.heaterAndFanSpeed')
        return self.latestStats.power, self.latestStats.fan


    def modeAndDrumSpeed(self):
        self.logger.debug('BulletR1.modeAndDrumSpeed')
        return self.latestStatus.mode, self.latestStats.drum


    def on(self):
        self.logger.debug('BulletR1.on')
        self.open()


    def open(self):
        if self.usbHandle is not None:
            return
        self.usbContext = usb1.USBContext()
        self.usbHandle = self.usbContext.openByVendorIDAndProductID(self.AILLIO_USB_VID, self.AILLIO_USB_PID, skip_on_error=True)
        if self.usbHandle is None:
            raise Exception("BulletR1 device not found at %x:%x." % (self.AILLIO_USB_VID, self.AILLIO_USB_PID))
            return
        self.logger.info("BulletR1 found.")
        if self.usbHandle.kernelDriverActive(self.AILLIO_USB_INTERFACE):
            self.usbHandle.detachKernelDriver(self.AILLIO_USB_INTERFACE)
        self.usbHandle.claimInterface(self.AILLIO_USB_INTERFACE)


    def prs(self):
        self.logger.debug('BulletR1.prs')
        self.writePacket(bytearray([0x30, 0x01, 0x0, 0x0]), "writePrs", self.writePrsCompleted)
        self.waitForTransfers()


    def readPacket(self, length, errorMsg, callback):
        transfer = self.usbHandle.getTransfer()
        transfer.callback = callback
        transfer.errorMsg = errorMsg
        transfer.setBulk(self.AILLIO_USB_READ_ENDPOINT | usb1.ENDPOINT_IN, length, self.transferCompleted)
        transfer.submit()
        self.transferList.append(transfer)


    def requestStats(self):
        self.logger.debug('BulletR1.requestStats')
        self.writePacket(bytearray([0x30, 0x01]), "requestStats", self.statsWriteCompleted)


    def requestStatus(self):
        self.logger.debug('BulletR1.requestStatus')
        self.writePacket(bytearray([0x30, 0x03]), "requestStatus", self.statusWriteCompleted)


    def sample(self):
        self.logger.debug('BulletR1.sample')
        self.requestStats()
        self.waitForTransfers()


    def start(self):
        self.logger.debug('BulletR1.start')
        if self.latestStatus.mode == 0:
            self.prs()


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


    def stop(self):
        self.logger.debug('BulletR1.stop')


    def toFahrenheit(self, celsius):
        return celsius * 9 / 5 + 32


    def transferCompleted(self, transfer):
        self.transferList.remove(transfer)
        statusCode = transfer.getStatus()
        if statusCode != usb1.TRANSFER_COMPLETED:
            raise UsbTransferException("USB Transfer failed during %s: %s (%d)" % (transfer.errorMsg, UsbTransferException.statusCodeToString(statusCode), statusCode))
        if transfer.callback is not None:
            transfer.callback(transfer)


    def waitForTransfers(self):
        while any(transfer.isSubmitted() for transfer in self.transferList):
            self.usbContext.handleEvents()


    def writePacket(self, packet, errorMsg, callback = None):
        transfer = self.usbHandle.getTransfer()
        transfer.callback = callback
        transfer.errorMsg = errorMsg
        transfer.setBulk(self.AILLIO_USB_WRITE_ENDPOINT | usb1.ENDPOINT_OUT, packet, self.transferCompleted)
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
