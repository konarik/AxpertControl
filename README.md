# AxpertControl
Uses python2

Controling and logging Software for Axpert Inverter 
- Log at least once, loop lenght is controlled by log_time. 
- To be runned via another script, command line or cron. 
- Switching between low (charging from solar+utility) and high tarrif (solar only charging) from command line. 
- Swithing to low tarrif only in case that battery is discharged below defined level.

Line arguments are:
- "LT" low tarrif(switches to solar+utility if battery level is < min_batt)
- "LTaf" low tarrif afternoon(switches to solar+utility if battery level is < min_batt_afternoon)
- "HT" high tarrif
- "SET" shows actual setting

Tested with one Axpert MKS III 5k-48 connected to Raspberry PI via USB. Logging tested on local emonCMS (docker) and emoncms.org

Implemented Dynamic Load Control from 73.00E

Repository contains:

axpert_hdo.py - Python script communicate with Axpert inverter, send and receive data to emonCMS (2 servers). 

axpert_ht.sh, axpert_lt.sh and axpert_ltaf.sh - Used to be called in cron, uncoment the lines if you need to rebind the hidraw device

cron - Example setting for low tarrif between 0-5 and 15-18 o'clock

Open points:
- move from python2 to python3
- add conditions for undefined servers