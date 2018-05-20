#!/usr/bin/env python

if __name__ == '__main__' and __package__ is None:
    from os import sys, path
    sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

import construct
import functools
import time
import usb1
from usb_transfer_exception import UsbTransferException
from packet_repeat_writer import PacketRepeatWriter

class BulletR1(object):
    instance = None

    class ChangeTimeout(Exception):
        pass

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

    FAN_SPEED_MODES = [MODE_ROASTING, MODE_COOLING]
    DRUM_SPEED_MODES = [MODE_ROASTING, MODE_COOLING]

    FAN_DOWN_PACKET = bytearray([0x31, 0x02, 0xaa, 0xaa])
    FAN_UP_PACKET = bytearray([0x31, 0x01, 0xaa, 0xaa])
    HEATER_DOWN_PACKET = bytearray([0x34, 0x02, 0xaa, 0xaa])
    HEATER_UP_PACKET = bytearray([0x34, 0x01, 0xaa, 0xaa])


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
            fanSpeedLevel = -1,
            heaterPowerLevel = -1,
            drumSpeedLevel = -1,
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
            'fanSpeedLevel' / construct.Int8ul,
            'heaterPowerLevel' / construct.Int8ul,
            'drumSpeedLevel' / construct.Int8ul,
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

    
    def drumSpeedDown(self):
        self.logger.debug('BulletR1.drumSpeedDown')
        self.setDrumSpeedLevel(self.drumSpeedLevel() + 1)


    def drumSpeedLevel(self):
        return self.latestStats.drumSpeedLevel


    def drumSpeedUp(self):
        self.logger.debug('BulletR1.drumSpeedUp')
        self.setDrumSpeedLevel(self.drumSpeedLevel() - 1)


    def drumTemperature(self):
        return self.latestStats.drumTemperature


    def fanDown(self):
        self.logger.debug('BulletR1.fanDown')
        self.writePacket(self.FAN_DOWN_PACKET, "fanDown")


    def fanSpeedLevel(self):
        return self.latestStats.fanSpeedLevel


    def fanUp(self):
        self.logger.debug('BulletR1.fanUp')
        self.writePacket(self.FAN_UP_PACKET, "fanUp")


    def getOneStats(self):
        self.requestStats()
        self.waitForTransfers()


    def heaterDown(self):
        self.logger.debug('BulletR1.heaterDown')
        self.writePacket(self.HEATER_DOWN_PACKET, "heaterDown")


    def heaterPowerLevel(self):
        return self.latestStats.heaterPowerLevel


    def heaterUp(self):
        self.logger.debug('BulletR1.heaterUp')
        self.writePacket(self.HEATER_UP_PACKET, "heaterUp")


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
        self.sample()


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
        self.writePacket(bytearray([0x30, 0x01, 0x0, 0x0]), 'prs')


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


    def setDrumSpeedLevel(self, level):
        self.logger.debug('BulletR1.setDrumSpeedLevel(%d)' % (level))
        if level < 1 or level > 9:
            raise ValueError("setDrumSpeedLevel level value must be between 1 and 9 inclusive")
        if self.mode() not in self.DRUM_SPEED_MODES:
            return
        self.writePacket(bytearray([0x32, 0x01, level, 0x00]), "setDrumSpeedLevel")


    def setFanSpeedLevel(self, level):
        self.logger.debug('BulletR1.setFanSpeedLevel(%d)' % (level))
        if level < 0 or level > 12:
            raise ValueError("setFanSpeedLevel level value must be between 0 and 15 inclusive")
        if self.mode() not in self.FAN_SPEED_MODES:
            return
        self.setToTargetBySteps(level, self.fanSpeedLevel, self.FAN_DOWN_PACKET, self.FAN_UP_PACKET, "setFanSpeedLevel")


    def setHeaterPowerLevel(self, level):
        self.logger.debug('BulletR1.setHeaterPowerLevel(%d)' % (level))
        if level < 0 or level > 9:
            raise ValueError("setHeaterPowerLevel level value must be between 0 and 9 inclusive")
        if self.mode() != self.MODE_ROASTING:
            return
        self.setToTargetBySteps(level, self.heaterPowerLevel, self.HEATER_DOWN_PACKET, self.HEATER_UP_PACKET, "setHeaterPowerLevel")


    def setToTargetBySteps(self, target, getCurrent, decreasePacket, increasePacket, name):
        current = getCurrent()
        if target < current:
            self.logger.debug("decrease from %d to %d" % (current, target))
            timesToWrite = current - target
            packet = decreasePacket
        else:
            self.logger.debug("increase from %d to %d" % (current, target))
            timesToWrite = target - current
            packet = increasePacket
        self.logger.debug("timesToWrite: %d" % timesToWrite)
        repeatPacketWriter = PacketRepeatWriter(self, packet, timesToWrite, name)
        repeatPacketWriter.write()


    def statsReadReady(self, transfer):
        self.logger.debug('BulletR1.statsReadReady')
        stats = self.statsStruct.parse(transfer.getBuffer())
        if stats.canary == 2868903935:
            self.logger.debug('BulletR1: got stats %d' % (stats.index))
            self.latestStats = stats
            self.requestStatus()
        else:
            time.sleep(0.5)
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
            self.waitUntil(functools.partial(lambda self, currentMode: self.mode() != currentMode, self, self.mode()), "mode is not %s" % self.mode())


    def waitForTransfers(self):
        while any(transfer.isSubmitted() for transfer in self.transferList):
            self.usbContext.handleEvents()


    def waitUntil(self, condition, name):
        timesStatsRequested = 0
        lastStatsIndex = self.latestStats.index
        while not condition():
            self.waitForTransfers()
            self.getOneStats()
            timesStatsRequested += 1
            if timesStatsRequested > 8:
                raise self.ChangeTimeout("waiting until %s, but had 8 stats with no change after change request" % (name))
            if lastStatsIndex == self.latestStats.index:
                time.sleep(0.5)


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
    R1.untilMode(BulletR1.MODE_ROASTING)
    R1.setFanSpeedLevel(12)
    R1.waitUntil(functools.partial(lambda R1: R1.fanSpeedLevel() == 12, R1), "fanSpeedLevel is 12")
    R1.setHeaterPowerLevel(0)
    R1.waitUntil(functools.partial(lambda R1: R1.heaterPowerLevel() == 0, R1), "powerHeaterLevel is 0")
    R1.off()
