# AxpertControl
Controling and logging Software for Axpert Inverter 
- One loop only. 
- To be runned via another script or cron. 
- Switching between low (charging from solar+utility) and high tarrif (solar only charging) from command line. 
- Swithing to low tarrif only in case that battery is discharged below defined level.

Tested with one Axpert MKS III 5k-48 connected to Raspberry PI via USB. Logging tested on local emonCMS (docker) and emoncms.org

Implemented Dynamic Load Control from 73.00E

Repository contains:

axpert_hdo.py
Python script communicate with Axpert inverter, send and receive data to emonCMS (2 servers). 

axpert_ht.sh and axpert_lt.sh
Used to be called in cron, uncoment the lines if you need to rebind the hidraw device