#!/bin/sh

 echo '1-1.3' | tee /sys/bus/usb/drivers/usb/unbind >/dev/null
 echo '1-1.4' | tee /sys/bus/usb/drivers/usb/unbind >/dev/null
sleep 1
 echo '1-1.3' | tee /sys/bus/usb/drivers/usb/bind >/dev/null
 echo '1-1.4' | tee /sys/bus/usb/drivers/usb/bind >/dev/null
sleep 1

/usr/bin/python2 /home/david/bin/axpert_hdo.py $1
#>/dev/null
