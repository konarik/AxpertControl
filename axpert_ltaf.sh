#!/bin/sh

# echo '1-1.3' | tee /sys/bus/usb/drivers/usb/unbind >/dev/null
#sleep 1
# echo '1-1.3' | tee /sys/bus/usb/drivers/usb/bind >/dev/null
#sleep 1

/usr/bin/python2 /home/david/bin/axpert_hdo.py LTaf >/dev/null