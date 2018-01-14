import usb1

class UsbTransferException(Exception):
    TRANSFER_STATUS_TO_STRING = {
        usb1.TRANSFER_COMPLETED: 'completed',
        usb1.TRANSFER_ERROR: 'error',
        usb1.TRANSFER_TIMED_OUT: 'timed out',
        usb1.TRANSFER_CANCELLED: 'cancelled',
        usb1.TRANSFER_STALL: 'stalled',
        usb1.TRANSFER_NO_DEVICE: 'no device',
        usb1.TRANSFER_OVERFLOW: 'overflow',
    }

    @staticmethod
    def statusCodeToString(statusCode):
        return UsbTransferException.TRANSFER_STATUS_TO_STRING[statusCode]
