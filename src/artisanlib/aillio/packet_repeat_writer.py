import time

class PacketRepeatWriter:
    def __init__(self, r1, packet, times, name):
        self.r1 = r1
        self.packet = packet
        self.timesToWrite = times
        self.timesWritten = 0
        self.name = name


    def write(self):
        if self.timesWritten >= self.timesToWrite:
            return
        self.r1.writePacket(self.packet, self.name, self.packetWritten)


    def packetWritten(self, transfer):
        self.r1.logger.debug("Wrote one packet for %s!" % self.name)
        self.timesWritten += 1
        self.write()
