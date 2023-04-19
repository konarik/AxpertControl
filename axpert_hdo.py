#! /usr/bin/python

# Axpert Inverter control script

# Read values from inverter, sends values to emonCMS,
# read electric low or high tarif from emonCMS and setting charger and mode to hold batteries fully charged
# controls grid charging current to meet circuit braker maximum alloweble grid current(power)
# calculation of CRC is done by XMODEM mode, but in firmware is wierd mistake in POP02 command, so exception of calculation is done in serial_command(command) function
# real PL2303 = big trouble in my setup, cheap chinese converter some times disconnecting, workaround is at the end of serial_command(command) function
# differenc between SBU(POP02) and Solar First (POP01): in state POP01 inverter works only if PV_voltage <> 0 !!! SBU mode works during night

# Josef Krieglstein 20190312 last update


# Modifications done by me to the original script:
#   - runs only once
#   - added command line arguments for tarrif swithing (and commented emoncms part)
#   - added second server for upload
#   - printing of current set up of the inverter
#   - commented the second inverter options
# Line arguments are:
#   - "LT" low tarrif (switches to solar+utility if battery level is < min_batt)
#   - "HT" high tarrif
#   - "SET" shows 
#   - if no argument is given only data is processed
#   - some modifications in device initization code
# Serial connection not tested

import urllib2
import serial, time, sys, string
import sqlite3
import json
import urllib
import httplib
import datetime
import calendar
import os
import re
import crcmod
import usb.core
import usb.util
import sys
import signal
import time
from binascii import unhexlify
#import binascii

# Domain you want to post to: localhost would be an emoncms installation on your own laptop
# this could be changed to emoncms.org to post to emoncms.org or your own server
server = "emoncms.org"
server2 = ""

# Location of emoncms in your server, the standard setup is to place it in a folder called emoncms
# To post to emoncms.org change this to blank: ""
emoncmspath = ""

# Write apikey of emoncms account
apikey = ""
apikey2 = ""

# Connection type to the inverter - serial connection not tested
#connection = "serial"
connection = "USB"

# Minimum battery level for low tarrif to switch to grid charging
min_batt = 90

# Node id youd like the emontx to appear as
nodeid0 = 1
#nodeid1 = 22

mode0 = -1
mode1 = -1
load = 0
wake_up_start = 0
parrallel_num = 0

#Axpert Commands and examples
#Q1             # Undocumented command: LocalInverterStatus (seconds from absorb), ParaExistInfo (seconds from end of Float), SccOkFlag, AllowSccOnFlag, ChargeAverageCurrent, SCC PWM Temperature, Inverter Temperature, Battery Temperature, Transformer Temperature, GPDAT, FanLockStatus, FanPWMDuty, FanPWM, SCCChargePowerWatts, ParaWarning, SYNFreq, InverterChargeStatus
#QPI            # Device protocol ID inquiry
#QID            # The device serial number inquiry
#QVFW           # Main CPU Firmware version inquiry
#QVFW2          # Another CPU Firmware version inquiry
#QFLAG          # Device flag status inquiry
#QPIGS          # Device general status parameters inquiry
                # GridVoltage, GridFrequency, OutputVoltage, OutputFrequency, OutputApparentPower, OutputActivePower, OutputLoadPercent, BusVoltage, BatteryVoltage, BatteryChargingCurrent, BatteryCapacity, InverterHeatSinkTemperature, PV-InputCurrentForBattery, PV-InputVoltage, BatteryVoltageFromSCC, BatteryDischargeCurrent, DeviceStatus,
#QMOD           # Device mode inquiry P: PowerOnMode, S: StandbyMode, L: LineMode, B: BatteryMode, F: FaultMode, H: PowerSavingMode
#QPIWS          # Device warning status inquiry: Reserved, InverterFault, BusOver, BusUnder, BusSoftFail, LineFail, OPVShort, InverterVoltageTooLow, InverterVoltageTooHIGH, OverTemperature, FanLocked, BatteryVoltageHigh, BatteryLowAlarm, Reserved, ButteryUnderShutdown, Reserved, OverLoad, EEPROMFault, InverterSoftFail, SelfTestFail, OPDCVoltageOver, BatOpen, CurrentSensorFail, BatteryShort, PowerLimit, PVVoltageHigh, MPPTOverloadFault, MPPTOverloadWarning, BatteryTooLowToCharge, Reserved, Reserved
#QDI            # The default setting value information
#QMCHGCR        # Enquiry selectable value about max charging current
#QMUCHGCR       # Enquiry selectable value about max utility charging current
#QBOOT          # Enquiry DSP has bootstrap or not
#QOPM           # Enquiry output mode
#QPIRI          # Device rating information inquiry
                # GridRatingVoltage, GridRatingCurrent, ACOutputRatingVoltage, ACOutputRatingFrequency, ACOutputRatingCurrent, ACOutputRatingApparentPower, ACOutputRatingActivePower, BatteryRatingVoltage,
                # BatteryReChargeVoltage, BatteryUnderVoltage, BatteryBulkVoltage, BatteryFloatVoltage, BatteryType (0: AGM; 1: Flooded; 2: User; 3: PYL; 4: WECO), CurrentMaxACChargingCurrent,
                # CurrentMaxChargingCurrent, InputVoltageRange (0: Appliance; 1: UPS), OutputSourcePriority (0: UtilitySolarBat; 1: SolarUtilityBat; 2: SolarBatUtility), ChargerSourcePriority (1: Solar first, 2: Solar + Utility, 3: Only solar charging permitted),
                # ParallelMaxNum, MachineType (00: Grid tie; 01: Off Grid; 10: Hybrid), Topology (0: transformerless; 1: transformer),
                # OutputMode (00: single machine output; 01: parallel output; 02: Phase 1 of 3 Phase output; 03: Phase 2 of 3 Phase output; 04: Phase 3 of 3 Phase output; 05: Phase 1 of 2 Phase output; 06: Phase 2 of 2 Phase output (120deg); 07: Phase 2 of 2 Phase output (180deg)),
                # BatteryReDischargeVoltage, PVOKConditionForParallel, PVPowerBalance (0: PV input max current will be the max charged current; 1: PV input max power will be the sum of the max charged power and loads power),
                # MaxChargingTimeAtCVStage, OperationLogic (not working?), MaxDischargingCurrent (not working?)
#QPGS0          # Parallel information inquiry
                # TheParallelNumber, SerialNumber, WorkMode, FaultCode, GridVoltage, GridFrequency, OutputVoltage, OutputFrequency, OutputAparentPower, OutputActivePower, LoadPercentage, BatteryVoltage, BatteryChargingCurrent, BatteryCapacity, PV-InputVoltage, TotalChargingCurrent, Total-AC-OutputApparentPower, Total-AC-OutputActivePower, Total-AC-OutputPercentage, InverterStatus, OutputMode, ChargerSourcePriority, MaxChargeCurrent, MaxChargerRange, Max-AC-ChargerCurrent, PV-InputCurrentForBattery, BatteryDischargeCurrent
#QBV            # Compensated Voltage, SoC
#PEXXX          # Setting some status enable
#PDXXX          # Setting some status disable
#PF             # Setting control parameter to default value
#FXX            # Setting device output rating frequency
#POP02          # set to SBU
#POP01          # set to Solar First
#POP00          # Set to UTILITY
#PBCVXX_X       # Set battery re-charge voltage
#PBDVXX_X       # Set battery re-discharge voltage
#PCP00          # Setting device charger priority: Utility First
#PCP01          # Setting device charger priority: Solar First
#PCP02          # Setting device charger priority: Solar and Utility
#PGRXX          # Setting device grid working range
#PBTXX          # Setting battery type
#PSDVXX_X       # Setting battery cut-off voltage
#PCVVXX_X       # Setting battery C.V. charging voltage
#PBFTXX_X       # Setting battery float charging voltage
#PPVOCKCX       # Setting PV OK condition
#PSPBX          # Setting solar power balance
#MCHGC0XX       # Setting max charging Current          M XX
#MUCHGC002      # Setting utility max charging current  0 02
#MUCHGC010      # Setting utility max charging current  0 10
#MUCHGC020      # Setting utility max charging current  0 20
#MUCHGC030      # Setting utility max charging current  0 30
#POPMMX         # Set output mode       M 0:single, 1: parrallel, 2: PH1, 3: PH2, 4: PH3

#notworking
#PPCP000        # Setting parallel device charger priority: UtilityFirst - notworking
#PPCP001        # Setting parallel device charger priority: SolarFirst - notworking
#PPCP002        # Setting parallel device charger priority: OnlySolarCharging - notworking

def handler(signum, frame):
    print 'Signal handler called with signal', signum
    raise Exception("Handler")

ser = serial.Serial()
ser.port = "/dev/ttyUSB0"
ser.baudrate = 2400
ser.bytesize = serial.EIGHTBITS     #number of bits per bytes
ser.parity = serial.PARITY_NONE     #set parity check: no parity
ser.stopbits = serial.STOPBITS_ONE  #number of stop bits
ser.timeout = 1                     #non-block read
ser.xonxoff = False                 #disable software flow control
ser.rtscts = False                  #disable hardware (RTS/CTS) flow control
ser.dsrdtr = False                  #disable hardware (DSR/DTR) flow control
ser.writeTimeout = 2                #timeout for write

if ( connection == "USB" ):
    try:
        usb0 = os.open('/dev/hidraw0', os.O_RDWR | os.O_NONBLOCK)

    except Exception, e:
        print "Error open USB port: " + str(e)
        exit()

    try:
        usb1 = os.open('/dev/hidraw1', os.O_RDWR | os.O_NONBLOCK)

    except Exception, e:
        print "Error open second inverter USB port: " + str(e)
        
if ( connection == "serial" ):
    try:
        ser.open()

    except Exception, e:
        print "error open serial port: " + str(e)
        exit()

def get_data(command,inverter):
    #collect data from axpert inverter
    global mode0
    global mode1
    global load
    status = -1
    global parrallel_num
    if inverter == 0: device = usb0
    if inverter == 1: device = usb1
    try:
        data = "{"
        if ( connection == "serial" and ser.isOpen() or connection == "USB" ):
            response = serial_command(command,device)
            if "NAKss" in response or response == '':
                if connection == "serial": time.sleep(0.2)
                return ''
            else:
                response_num = re.sub ('[^0-9. ]','',response)
                if command == "QPGS0":
                    response.rstrip()
                    response_num.rstrip()
                    nums = response_num.split(' ', 99)
                    nums_mode = response.split(' ', 99)
                    if nums_mode[2] == "L":
                        data += "Gridmode0:1"
                        data += ",Solarmode0:0"
                        mode0 = 0
                    elif nums_mode[2] == "B":
                        data += "Gridmode0:0"
                        data += ",Solarmode0:1"
                        mode0 = 1
                    elif nums_mode[2] == "S":
                        data += "Gridmode0:0"
                        data += ",Solarmode0:0"
                        mode0 = 2
                    elif nums_mode[2] == "F":
                        data += "Gridmode0:0"
                        data += ",Solarmode0:0"
                        mode0 = 3
        
                    data += ",The_parallel_num0:" + nums[0]
                    data += ",Serial_number0:" + nums[1]
                    data += ",Fault_code0:" + nums[3]
                    data += ",Load_percentage0:" + nums[10]
                    data += ",Total_charging_current:" + nums[15]
                    data += ",Total_AC_output_active_power:" + nums[17]
                    data += ",Total_AC_output_apparent_power:" + nums[16]
                    data += ",Total_AC_output_percentage:" + nums[18]
                    data += ",Inverter_Status0:" + nums[19]
                    data += ",Output_mode0:" + nums[20]
                    data += ",Charger_source_priority0:" + nums[21]
                    data += ",Max_Charger_current0:" + nums[22]
                    data += ",Max_Charger_range0:" + nums[23]
                    data += ",Max_AC_charger_current0:" + nums[24]
                    data += ",Inverter_mode0:" + str (mode0)
                    parrallel_num = int (nums[0])
                    load = int (nums[17])

                elif command == "QPGS1":
                    response.rstrip()
                    response_num.rstrip()
                    nums = response_num.split(' ', 99)
                    nums_mode = response.split(' ', 99)
                    if nums_mode[2] == "L":
                        data += "Gridmode1:1"
                        data += ",Solarmode1:0"
                        mode1 = 0
                    elif nums_mode[2] == "B":
                        data += "Gridmode1:0"
                        data += ",Solarmode1:1"
                        mode1 = 1
                    elif nums_mode[2] == "S":
                        data += "Gridmode1:0"
                        data += ",Solarmode1:0"
                        mode1 = 2
                    elif nums_mode[2] == "F":
                        data += "Gridmode1:0"
                        data += ",Solarmode1:0"
                        mode1 = 3
            
                    data += ",The_parallel_num1:" + nums[0]
                    data += ",Serial_number1:" + nums[1]
                    data += ",Fault_code1:" + nums[3]
                    data += ",Load_percentage1:" + nums[10]
                    data += ",Total_charging_current:" + nums[15]
                    data += ",Total_AC_output_active_power:" + nums[17]
                    data += ",Total_AC_output_apparent_power:" + nums[16]
                    data += ",Total_AC_output_percentage:" + nums[18]
                    data += ",Inverter_Status1:" + nums[19]
                    data += ",Output_mode1:" + nums[20]
                    data += ",Charger_source_priority1:" + nums[21]
                    data += ",Max_Charger_current1:" + nums[22]
                    data += ",Max_Charger_range1:" + nums[23]
                    data += ",Max_AC_charger_current1:" + nums[24]
                    data += ",Inverter_mode1:" + str (mode1)
                    parrallel_num = int (nums[0])
                    load = int (nums[17])

                elif command == "QPIGS":
                    response_num.rstrip()
                    nums = response_num.split(' ', 99)
                    data += "Grid_voltage" + str(inverter) + ":" + nums[0]
                    data += ",Grid_frequency" + str(inverter) + ":" + nums[1]
                    data += ",AC_output_voltage" + str(inverter) + ":" + nums[2]
                    data += ",AC_output_frequency" + str(inverter) + ":" + nums[3]
                    data += ",AC_output_apparent_power" + str(inverter) + ":" + nums[4]
                    data += ",AC_output_active_power" + str(inverter) + ":" + nums[5]
                    data += ",Output_Load_Percent" + str(inverter) + ":" + nums[6]
                    data += ",Bus_voltage" + str(inverter) + ":" + nums[7]
                    data += ",Battery_voltage" + str(inverter) + ":" + nums[8]
                    data += ",Battery_charging_current" + str(inverter) + ":" + nums[9]
                    data += ",Battery_capacity" + str(inverter) + ":" + nums[10]
                    data += ",Inverter_heatsink_temperature" + str(inverter) + ":" + nums[11]
                    data += ",PV_input_current_for_battery" + str(inverter) + ":" + nums[12]
                    data += ",PV_Input_Voltage" + str(inverter) + ":" + nums[13]
                    data += ",Battery_voltage_from_SCC" + str(inverter) + ":" + nums[14]
                    data += ",Battery_discharge_current" + str(inverter) + ":" + nums[15]
                    data += ",Device_status" + str(inverter) + ":" + nums[16]

                elif command == "Q1":
                    response_num.rstrip()
                    nums = response_num.split(' ', 99)
                    data += "SCCOkFlag" + str(inverter) + ":" + nums[2]
                    data += ",AllowSCCOkFlag" + str(inverter) + ":" + nums[3]
                    data += ",ChargeAverageCurrent" + str(inverter) + ":" + nums[4]
                    data += ",SCCPWMTemperature" + str(inverter) + ":" + nums[5]
                    data += ",InverterTemperature" + str(inverter) + ":" + nums[6]
                    data += ",BatteryTemperature" + str(inverter) + ":" + nums[7]
                    data += ",TransformerTemperature" + str(inverter) + ":" + nums[8]
                    data += ",GPDAT" + str(inverter) + ":" + nums[9]
                    data += ",FanLockStatus" + str(inverter) + ":" + nums[10]
                    data += ",FanPWM" + str(inverter) + ":" + nums[12]
                    data += ",SCCChargePower" + str(inverter) + ":" + nums[13]
                    data += ",ParaWarning" + str(inverter) + ":" + nums[14]
                    data += ",InverterChargeStatus" + str(inverter) + ":" + nums[16]


                elif command == "QPIRI":
                    response_num.rstrip()
                    nums = response_num.split(' ', 99)
                    data += "BatteryType" + str(inverter) + ":" + nums[12] # BatteryType (0: AGM; 1: Flooded; 2: User; 3: PYL; 4: WECO)
                    data += ",CurrentMaxACChargingCurrent" + str(inverter) + ":" + nums[13]
                    data += ",CurrentMaxChargingCurrent" + str(inverter) + ":" + nums[14]
                    
                elif command == "QBV":
                    response_num.rstrip()
                    nums = response_num.split(' ', 99)
                    data += "Battery_voltage_compensated" + str(inverter) + ":" + nums[0]
                    data += ",SoC" + str(inverter) + ":" + nums[1]

                elif command == "QMCHGCR":
                    response_num.rstrip()
                    nums = response_num.split(' ', 99)
                    data += "MaxSolarChargingCurrent" + str(inverter) + ":" + nums[0]

                elif command == "QMUCHGCR":
                    response_num.rstrip()
                    nums = response_num.split(' ', 99)
                    data += "MaxUtilityChargingCurrent" + str(inverter) + ":" + nums[0]

                else: return ''
                data += "}"

    except Exception, e:
            print "error parsing inverter data...: " + str(e)
            print "problem command: " + command +": " + response
            return ''

    return data

def set_charge_current():
    # Automaticly adjust axpert inverter grid charging current

    # 2A = 100W, 10A = 500W, 20A = 1000W, 30 = 1500W
    # load >3000W -> 02A
    # load <3000W -> 10A
    # load <2000W -> 20A
    # load <1000W -> 30A

    try:
        if ( connection == "serial" and ser.isOpen() or connection == "USB" ):
            current = 0
            load_power = 0
            response = serial_command("QPGS0",usb0)
            if "NAKss" in response:
                if connection == "serial": time.sleep(0.5)
                return ''
            response.rstrip()
            nums = response.split(' ', 99)
            current = int ( nums[24] )
            response = serial_command("QPIGS",usb0)
            if "NAKss" in response:
                if connection == "serial": time.sleep(0.5)
                return ''
            response.rstrip()
            nums = response.split(' ', 99)
            load_power = int ( nums[5] )
            print load_power
            if load_power > 3000:
                if not current == 2:
                    current = 2
                    response = serial_command("MUCHGC002",usb0)
            elif load_power > 2000:
                if not current == 10:
                    current = 10
                    response = serial_command("MUCHGC010",usb0)
            elif load_power > 1000:
                if not current == 20:
                    current = 20
                    response = serial_command("MUCHGC020",usb0)
            else:
                if not current == 30:
                    current = 30
                    response = serial_command("MUCHGC030",usb0)
            print current
            if "NAKss" in response:
                if connection == "serial": time.sleep(0.5)
                return ''

        elif ( connection == "serial" ):
            ser.close()
            print "cannot use serial port ..."
            return ""

    except Exception, e:
            print "error parsing inverter data...: " + str(e)
            return ''

    return current

def get_battery_level():
    #get actual battery level
    battery_level = -1
    try:
        if ( connection == "serial" and ser.isOpen() or connection == "USB" ):
            response = serial_command("QPIGS",usb0)
            if "NAKss" in response:
                if connection == "serial": time.sleep(0.5)
                return ""
            response.rstrip()
            nums = response.split(' ', 99)
            battery_level = nums[10]

        elif ( connection == "serial" ):
            ser.close()
            print "cannot use serial port ..."
            return ""

    except Exception, e:
            print "error parsing inverter data...: " + str(e)
            return ""

    return battery_level

def get_output_source_priority():
    #get inverter output mode priority
    output_source_priority = "8"
    try:
        if ( connection == "serial" and ser.isOpen() or connection == "USB" ):
            response = serial_command("QPIRI",usb0)
            if "NAKss" in response:
                if connection == "serial": time.sleep(0.5)
                return ""
            response.rstrip()
            nums = response.split(' ', 99)
            output_source_priority = nums[16]

        elif ( connection == "serial" ):
            ser.close()
            print "cannot use serial port ..."
            return ""

    except Exception, e:
            print "error parsing inverter data...: " + str(e)
            return ""

    return output_source_priority

def get_charger_source_priority():
    #get inverter charger mode priority
    charger_source_priority = "8"
    try:
        if ( connection == "serial" and ser.isOpen() or connection == "USB" ):
            response = serial_command("QPIRI",usb0)
            if "NAKss" in response:
                if connection == "serial": time.sleep(0.5)
                return ""
            response.rstrip()
            nums = response.split(' ', 99)
            charger_source_priority = nums[17]

        elif ( connection == "serial" ):
            ser.close()
            print "cannot use serial port ..."
            return ""

    except Exception, e:
            print "error parsing inverter data...: " + str(e)
            return ""

    return charger_source_priority

def set_output_source_priority(output_source_priority):
    #set inverter output mode priority
        if not output_source_priority == "":
            try:
                if ( connection == "serial" and ser.isOpen() or connection == "USB" ):
                    if output_source_priority == 0:
                        response = serial_command("POP00",usb0)
                        print response
                    elif output_source_priority == 1:
                        response = serial_command("POP01",usb0)
                        print response
                    elif output_source_priority == 2:
                        response = serial_command("POP02",usb0)
                        print response

                elif ( connection == "serial" ):
                    ser.close()
                    print "cannot use serial port ..."
                    return ""

            except Exception, e:
                print "error parsing inverter data...: " + str(e)
                return ''

        return 1

def set_charger_source_priority(charger_source_priority):
    #set inverter charge mode priority
        if not charger_source_priority == "":
            try:
                if ( connection == "serial" and ser.isOpen() or connection == "USB" ):

                    if charger_source_priority == 0:
                        response = serial_command("PCP00",usb0)
                        print response
                    elif charger_source_priority == 1:
                        response = serial_command("PCP01",usb0)
                        print response
                    elif charger_source_priority == 2:
                        response = serial_command("PCP02",usb0)
                        print response
                    elif charger_source_priority == 3:
                        response = serial_command("PCP03",usb0)
                        print response

                elif ( connection == "serial" ):
                    ser.close()
                    print "cannot use serial port ..."
                    return ""

            except Exception, e:
                    print "error parsing inverter data...: " + str(e)
                    return ''

        return 1

def send_data(data):
    # Send data to emoncms server
    try:
        conn = httplib.HTTPConnection(server)
        conn.request("GET", "/"+emoncmspath+"/input/post.json?&node="+str(nodeid0)+"&json="+data+"&apikey="+apikey)
        response = conn.getresponse()
        conn.close()

        conn = httplib.HTTPConnection(server2)
        conn.request("GET", "/"+emoncmspath+"/input/post.json?&node="+str(nodeid0)+"&json="+data+"&apikey="+apikey2)
        response = conn.getresponse()
        conn.close()

    except Exception as e:
        print "error sending to emoncms...: " + str(e)
        return ''
    return 1

def read_hdo(id):
    # Read high/low tarif from emoncms (the acctual tarif information can be created by cron script, or from emonTX input)
    # in Czech Republic, West Bohemia it is perriodicaly, tarif name is for example: A1B8DP5 => (8 hours of low and 16 hours of high) / each day
    try:
        conn = httplib.HTTPConnection(server)
        conn.request("GET", "/"+emoncmspath+"/feed/value.json?id="+str(id)+"&apikey="+apikey)
        response = conn.getresponse()
        response_tmp = response.read()
        conn.close()
        return response_tmp

    except Exception as e:
        print "error reading from emoncms...: " + str(e)
        return ''
    return 1


def serial_command(command,device):
    try:
        response = ""
        xmodem_crc_func = crcmod.predefined.mkCrcFun('xmodem')
        # wierd mistake in Axpert firmware - correct CRC is: 0xE2 0x0A
        if command == "POP02": command_crc = '\x50\x4f\x50\x30\x32\xe2\x0b\x0d\r'
        else: command_crc = command + unhexlify(hex(xmodem_crc_func(command)).replace('0x','',1)) + '\r'
        
        # Set the signal handler and a 5-second alarm 
        signal.signal(signal.SIGALRM, handler)
        signal.alarm(10)
        if len (command_crc) < 9:
            time.sleep (0.35)
            os.write(device, command_crc)
            
        else:
            cmd1 = command_crc[:8]
            cmd2 = command_crc[8:]
            time.sleep (0.35)
            os.write(device, cmd1)
            time.sleep (0.35)
            os.write(device, cmd2)
            time.sleep (0.25)
        while True:
            time.sleep (0.15)
            r = os.read(device, 256)
            response += r
            if '\r' in r: break

    except Exception, e:
        print "error reading inverter...: " + str(e) + "Response :" + response
        data = ""
        if connection == "serial":
            time.sleep(20)  # Problem with some USB-Serial adapters, they are some times disconnecting, 20 second helps to reconnect at same ttySxx
            ser.open()
            time.sleep(0.5)
            return ''

    signal.alarm(0)

    sys.stdout.write (command + " : ")
    sys.stdout.flush ()
    print response
    return response

def dynamic_control():
    # Automaticly adjust axpert inverter wakeup and standby mode
    #0:Line mode
    #1:Battery mode
    #2:Stand by mode
    #3:Fault mode
    #-1: Unknown mode
    # load > 1800 W -> Both inverters UP
    # load < 1500 W -> Master Running Slave in standby
    # minimum time to run 5 minutes = 300 seconds
    global wake_up_start
    global mode0
    global mode1
    global load
    response = " no command "
    time_tmp = (time.time() - wake_up_start)
    try:
        print "Load: " + str(load) + " W, MODE: " + str (mode0) + "|"  + str(mode1) + ", time: " + str (int(time_tmp)) + " seconds"
        if (load < 1500 and mode0 == 1 and mode1 == 1 and time_tmp > 300):
            print "Second inverter go to standby mode"
            response = serial_command("MNCHGC1497",usb0)
        elif (load < 1500 and mode0 == 1 and mode1 == 1 and time_tmp < 300):
            print "waiting 5 minutes to be sure that inverter could go sleep"
        elif (load > 1800 and mode0 == 1 and mode1 == 2):
            print "Second Inverter wake up"
            response = serial_command("MNCHGC1498",usb0)
            wake_up_start = time.time()
        elif (load < 1800 and mode0 == 1 and mode1 == 2):
            print "Second inverter already sleeping"
        elif (load > 1800 and mode0 == 1 and mode1 == 1):
            print "Both inverters running"
        else:
            print "No idea what to do"
        if "NAKss" in response:
            print "Inverter didn't recognized command"
            return

    except Exception, e:
            print "error setting inverter mode...: " + str(e)
            return

    return 1

def main():
    global mode0
    global mode1
    global parrallel_num
    global wake_up_start
    global load
    wake_up_start = time.time()

#    for inverter in range (0, 2):

    inverter = 0
#        if (inverter == 1 and parrallel_num < 1): break
    data = get_data("QBV",inverter)
    if not data == "": send = send_data(data)
    data = get_data("Q1",inverter)
    if not data == "": send = send_data(data)
    data = get_data("QPIGS", inverter)
    if not data == "": send = send_data(data)
    data = get_data("QMCHGCR", inverter)
    if not data == "": send = send_data(data)
    data = get_data("QMUCHGCR", inverter)
    if not data == "": send = send_data(data)
    data = get_data("QPIRI", inverter)
    if not data == "": send = send_data(data)



    if inverter == 0:
        data = get_data("QPGS0", inverter)
        if not data == "": send = send_data(data)
#    elif inverter == 1:
#        data = get_data("QPGS1", inverter)
#        if not data == "": send = send_data(data)
#        time.sleep(15)
#        if (load > 0 and mode0 >= 0 and mode1 >= 0 and parrallel_num == 1):
#            dynamic_control()

#    charge_current = set_charge_current ()

    try:
        if not sys.argv[1] == "" : hdo_cmd = sys.argv[1]
    except Exception, e:
        print("No command line argument for tarrif change")
        hdo_cmd=""
        
    batt_level = int(get_battery_level())

    hdo_cmd = hdo_cmd.upper()
    if ( hdo_cmd == "LT" or hdo_cmd == "HT" or hdo_cmd == "SET"):
        output_source_priority = get_output_source_priority()
        charger_source_priority = get_charger_source_priority()
    else :
        print("Wrong command line argument use LT or HT or SET")
        hdo_cmd = ""
    
    if not hdo_cmd == "":
        if ( not output_source_priority == "8" and not charger_source_priority == "8" ):
            if ( hdo_cmd == "LT" and batt_level < min_batt and batt_level > -1 ): # electricity is cheap, so charge batteries from grid and hold them fully charged if the value is > than min_batt! important for Lead Acid Batteries Only!
                print("Low tarrif and battery level " + str(min_batt) + " %, switching to solar+utility (limit value " + str(batt_level) + "%)")
                print("Actual battery level " + str(batt_level) + " %")
                if not output_source_priority == "1":       # Utility First (0: Utility first, 1: Solar First, 2: SBU)
                    set_output_source_priority(1)
                if not charger_source_priority == "2":      # Utility First (0: Utility first, 1: Solar First, 2: Solar+Utility, 3: Solar Only)
                    set_charger_source_priority(2)
            elif hdo_cmd == "LT" :
                print("Low tarrif and battery level >" + str(min_batt) + " %, solar only") # electricity is cheap, but batteries are charged
                print("Actual battery level " + str(batt_level) + " %")
            elif hdo_cmd == "HT":
                print("High tarrif")  # electricity is expensive, so supply everything from batteries not from grid
                if not output_source_priority == "2":       # Utility First (0: Utility first, 1: Solar First, 2: SBU)
                    set_output_source_priority(2)
                if not charger_source_priority == "3":      # Utility First (0: Utility first, 1: Solar First, 2: Solar+Utility, 3: Solar Only)
                    set_charger_source_priority(3)
            if hdo_cmd == "SET" : print("Settings to be displayed")
            print("Actual settings:")
            if not output_source_priority == "8":
                if output_source_priority == "0": print("Output priority : Utility first")
                if output_source_priority == "1": print("Output priority : Solar first")
                if output_source_priority == "2": print("Output priority : SBU")
            if not charger_source_priority == "8":
                if charger_source_priority == "0": print("Charger priority: Utility first")
                if charger_source_priority == "1": print("Charger priority: Solar first")
                if charger_source_priority == "2": print("Charger priority: Solar+Utility first")
                if charger_source_priority == "3": print("Charger priority: Solar only")


if __name__ == '__main__':
    main()
