# AxpertControl
Controling and logging Software for Axpert Inverter

Tested with Axpert MKS-4000 over Serial port

Repository contains:

Axpert.sh
Script to run python script

Axpert.py
Python script communicate with Axpert inverter, send and receive data to emonCMS. Control mode depends to local tarif.

HDO-NT.py
Switch to low tarif

HDO-VT.py
Switch to High tarif

HDO-A1B8DP5
cron job for switching tarif in West Bohemia Czech Republic

axpert_tmp.py
testing script wiht CRC, commands, ... 
