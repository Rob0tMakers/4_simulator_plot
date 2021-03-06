#!/usr/bin/python3
import os
# initialize asebamedulla in background and wait 0.3s to let
# asebamedulla startup
os.system("(asebamedulla ser:name=Thymio-II &) && sleep 0.3")
import matplotlib.pyplot as plt
import numpy as np
from picamera import PiCamera
from time import sleep
import time
import dbus
import dbus.mainloop.glib
from adafruit_rplidar import RPLidar
from math import cos, sin, pi, floor
import threading
from image_processing import sense_target
from shapely.geometry import Point
from particle_filtering import approximateLocation, dtr


print("Starting robot")

#-----------------------init script--------------------------
camera = PiCamera()
    # initialize the camera and grab a reference to the raw camera capture

def dbusError(self, e):
    # dbus errors can be handled here.
    # Currently only the error is logged. Maybe interrupt the mainloop here
    print('dbus error: %s' % str(e))


# init the dbus main loop
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    
# get stub of the aseba network
bus = dbus.SessionBus()
asebaNetworkObject = bus.get_object('ch.epfl.mobots.Aseba', '/')
    
# prepare interface
asebaNetwork = dbus.Interface(
    asebaNetworkObject,
    dbus_interface='ch.epfl.mobots.AsebaNetwork'
)
    
# load the file which is run on the thymio
asebaNetwork.LoadScripts(
    'thympi.aesl',
    reply_handler=dbusError,
    error_handler=dbusError
)

sleep(2)

#signal scanning thread to exit
exit_now = False

# Setup the RPLidar
PORT_NAME = '/dev/ttyUSB0'
lidar = RPLidar(None, PORT_NAME)
#This is where we store the lidar readings
scan_data = [0]*360
# this is where we store the IR readings
prox_horiz = [0]*5
# store receiving signals here
rx = [0]
# for particle filtering
x_hat = 0
y_hat = 0
q_hat = 0
toggle = True # toggling between random sampling and gaussian sampling
delta = 5
# camera output
camera_output = 0
lidar_index = [0,315,270,225,180,135,90,45]
# dancefloors
floor_red = [0.295, 0.485]
floor_yellow = [-0.295, 0.485]
floor_green = [0.295, -0.485]
floor_blue = [-0.295, -0.485]
# dancefloor target
dancefloor = 3

#--------------------- init script end -------------------------

#NOTE: if you get adafruit_rplidar.RPLidarException: Incorrect descriptor starting bytes
# try disconnecting the usb cable and reconnect again. That should fix the issue
def lidarScan():
    print("Starting background lidar scanning")
    for scan in lidar.iter_scans():
        if(exit_now):
            return
        for (_, angle, distance) in scan:
            scan_data[min([359, floor(angle)])] = distance
            
def infraredScan():
    while True: 
        sensor_readings = asebaNetwork.GetVariable("thymio-II", 'prox.horizontal')
        for i in range(5):
            prox_horiz[i] = int(sensor_readings[i])
            # we can try to save 5 and 6 as they are back sensors


def locationFinder():
    global toggle, x_hat, y_hat, q_hat, scan_data, lidar_index, camera_output, delta

    if toggle == True:
        camera_output = calibrate()
    if camera_output > 0:
        particle, toggle, delta = approximateLocation(np.array(scan_data)[lidar_index], camera_output, x_hat, y_hat, q_hat, toggle)
        x_hat = particle[0]
        y_hat = particle[1]
        q_hat = particle[2]

def followWall(direction, gender):
    if direction == "cw":
        side_sensor = 270
        L_turnfromwall = 150
        R_turnfromwall = 10
        L_turntowall = 40
        R_turntowall = 20
        L_turncorner = 200
        R_turncorner = 0
        far_threshold = 175
        near_threshold = 75
        wait_time = 3

    else:
        side_sensor = 90
        L_turnfromwall = 100
        R_turnfromwall = 30
        L_turntowall = 150
        R_turntowall = 20
        L_turncorner = 0
        R_turncorner = 50
        far_threshold = 200
        near_threshold = 150
        wait_time = 2

    if receiveInformation() in [1,2] and receiveInformation()[0] != gender:
        asebaNetwork.SendEventName(
        'motor.target', [0,0])
        return True

    if any(sensor > 1000 for sensor in prox_horiz) and scan_data[0] > 250 : #obstacle found
        asebaNetwork.SendEventName(
        'motor.target', [0,0])
        return True

    elif scan_data[0] < 200: # sees a corner ahead
        print('corner')
        asebaNetwork.SendEventName(
        'motor.target',
        [L_turncorner, R_turncorner]) 
        sleep(wait_time)

    elif scan_data[side_sensor] < near_threshold: #Too close to the wall (adjust right)
        asebaNetwork.SendEventName(
        'motor.target',
        [L_turnfromwall, R_turnfromwall]) 

    elif scan_data[side_sensor] > far_threshold: #Too far from the wall (adjust left)
        asebaNetwork.SendEventName(
        'motor.target',
        [L_turntowall, R_turntowall]) 
    
    else: #move forward
        asebaNetwork.SendEventName(
        'motor.target',
        [200, 50]) 

    return False

def calibrate():
    targetSeen = False
    seen = sense_target(camera)
    if seen != 0:
        # wait to see if we see the same thing multiple times
        seen2 = sense_target(camera)
        if seen == seen2:
            targetSeen = True
    while not targetSeen:
        # turn counterclockwise
        asebaNetwork.SendEventName(
        'motor.target', [0,15])
        sleep(0.5)
        asebaNetwork.SendEventName(
        'motor.target', [0,0])
        seen = sense_target(camera)
        if seen != 0:
            # wait to see if we see the same thing multiple times
            seen2 = sense_target(camera)
            if seen == seen2:
                targetSeen = True
    return seen

#this enables the prox.com communication channels
asebaNetwork.SendEventName( "prox.comm.enable", [1])
asebaNetwork.SendEventName("prox.comm.rx",[0])
    

def sendInformation(number):
    #asebaNetwork.SetVariable("thymio-II", "prox.comm.tx", [number])
    asebaNetwork.SendEventName(
            "prox.comm.tx",
            [number]
            )
def get_rx_reply(r):
    print("found", r)
def get_rx_error(e):
    print("error:", e)
    print(str(e))
def receiveInformation():
    rx = asebaNetwork.GetVariable("thymio-II", "prox.comm.rx")
    #asebaNetwork.GetVariable("thymio-II", "prox.comm.rx", \
    #        reply_handler=get_rx_reply,error_handler=get_rx_error)


# -----------------------------------------------------------------

# -------------------- Party functions ----------------------------

def benchWarm():
    global dancefloor

    wait_time = 60
    t_0 = time.time()
    print("It is now " + str(t_0))
    end_time = t_0 + wait_time
    print("We will wait for a dance partner until " + str(end_time))
    gender = np.random.randint(1,3) #perhaps create class robot so you can set this to a variable defining the robot?
    if gender == 1:
        # set color to blue
        asebaNetwork.SendEventName("leds.top", [0,0,32])
    else:
        # set color to red
        asebaNetwork.SendEventName("leds.top", [32,0,0])
    
    while time.time() < end_time: ##### See if we can actually detect a dance partner this way
        sendInformation(gender)
        rx = asebaNetwork.GetVariable("thymio-II", "prox.comm.rx")
        if rx[0] not in set([0, gender]):
            print("Partner found <3 <3 <3")
            if rx[0] in [3,4,5,6]:
                dancefloor = rx[0]
                moveToDanceFloor(dancefloor)

    print("Time to go find someone myself!")
    findDancePartner(gender)

def getDistanceToTarget(target_x, target_y):
    target = Point(target_x, target_y)
    return Point(x_hat, y_hat).distance(target)

def getAngleToTarget(target_x, target_y):
    delta_x = target_x - x_hat
    delta_y = target_y - y_hat

    if delta_x == 0:
        delta_x = 0.001

    angle = np.arctan(delta_y / delta_x)

    return angle - q_hat


def goForward():
    # moves 5 - 6 cm forward per second
    asebaNetwork.SendEventName('motor.target', [200,50])

def turn():
    # 30 degrees per second (counter clockwise)
    asebaNetwork.SendEventName('motor.target', [-20,15])



def findDancePartner(gender):
    print("Finding a dance partner")
    # move clockwise. First turn along the wall blindly
    rx = [gender]
    asebaNetwork.SendEventName('motor.target', [0,100]) #adjust so a 90deg turn is done to the left.
    sleep(2.5)
    obstacle = False
    while not obstacle:
        sendInformation(gender)
        obstacle = followWall('cw', gender)
    # check to see if we have received a signal
    rx = asebaNetwork.GetVariable("thymio-II", "prox.comm.rx")
    if rx[0] != gender:
        sendInformation(gender)
        print("Partner found!!!!")
        dancefloor = np.random.randint(3,6)
        for i in range(5):
            sendInformation(dancefloor) #after it is sent 5 times, assume its been seen
        moveToDanceFloor(dancefloor)
    # if we haven't seen the right gender
    sleep(3)
    print("Lets try the other direction")
    # try opposite directions
    asebaNetwork.SendEventName('motor.target', [200,0])
    sleep(8.25)
    obstacle = False
    while not obstacle:
        sendInformation(gender)
        obstacle = followWall('ccw', gender)
    rx = asebaNetwork.GetVariable("thymio-II", "prox.comm.rx")
    if rx[0] not in set([0, gender]):
        sendInformation(gender)
        print("Partner found!!!!")
        dancefloor = np.random.randint(3,6)
        for i in range(5):
            sendInformation(dancefloor) #after it is sent 5 times, assume its been seen
        moveToDanceFloor(dancefloor)
    sleep(3)
    print('no one again')
    
    # turn so we face outagain (turn left 90 deg)
    asebaNetwork.SendEventName('motor.target', [0,50])
    sleep(2)
    benchWarm()

def checkDanceFloor():
    if x_hat > 0:
        if y_hat > 0:
            return 4 # red
        else:
            return 6 # green
    else: #negative x value
        if y_hat > 0:
            return 3 # yellow
        else:
            return 5 # blue

def moveToDanceFloor(dancefloor):
    global delta
    asebaNetwork.SendEventName("leds.top", [32,0,32])
    location = 0
    while location != dancefloor:
        print("Ok not yet.")
        delta = 5
        while delta > 1.5:
            locationFinder()
        print("I know where we are.")
        location = checkDanceFloor()
        if location == dancefloor:
            print("I am here")
            break
        # location is determined. Now we need to figure out a navigation thing
        ######## Code ###########
        print('we are at dancefloor ' + str(location))
        target = [0,0] # default

        if dancefloor == 3:
            target = floor_yellow
        if dancefloor == 4:
            target = floor_red
        if dancefloor == 5:
            target = floor_blue
        if dancefloor == 6:
            target = floor_green

        distance = getDistanceToTarget(target[0], target[1])
        angle = getAngleToTarget(target[0], target[1])

        if angle < 0:
            angle = 2 * np.pi + angle

        if angle > 4.5:
            angle = 0

        print("I know where to go")
        print(distance, angle)
        turn_time = angle / dtr(30) # 30 degrees in radians
        go_time = distance / 0.06

        print(turn_time, go_time)
        turn()
        sleep(turn_time)
        goForward()
        sleep(go_time)
        asebaNetwork.SendEventName('motor.target', [0,0])
        break # just to be competition ready. 

    print("I am here")
    dance()

def dance():
    print("See me do my dance, mom!!!")
    asebaNetwork.SendEventName('motor.target', [10,100])
    sleep(3) 
    asebaNetwork.SendEventName('motor.target', [150,10])
    sleep(5)
    asebaNetwork.SendEventName('motor.target', [10,100])
    sleep(3)
    returnToRest()

# def returnToRest():
#     #Shortest distance to wall #
#     lidar_index_short = [0,90,180,270]
#     indexoflidar = np.argmin(np.array(scan_data)[lidar_index_short]) 
#     print(indexoflidar)
#     if indexoflidar == 0:
#         asebaNetwork.SendEventName('motor.target', [200, 50])
#         if scan_data[0] < 200: 
#             #Turn 180 degree and back into wall 
#             asebaNetwork.SendEventName('motor.target', [200, 50])
#             asebaNetwork.SendEventName('motor.target', [-200, -50])
#             benchWarm()
#     elif indexoflidar == 1: 
#         #Turn 90 degree 
#         asebaNetwork.SendEventName('motor.target', [100, 50])
#         #forward
#         asebaNetwork.SendEventName('motor.target', [200, 50])
#         if scan_data[0] < 200: 
#             #Turn 180 degree and back into wall 
#             asebaNetwork.SendEventName('motor.target', [200, 50])
#             asebaNetwork.SendEventName('motor.target', [-200, -50])
#             benchWarm()
#     elif indexoflidar == 2: 
#         #Backwards until wall 😛 
#         asebaNetwork.SendEventName('motor.target', [-200, -50])
#         if scan_data[0] < 200:
#             #Turn 180 degree and back into wall 
#             asebaNetwork.SendEventName('motor.target', [200, 50])
#             asebaNetwork.SendEventName('motor.target', [-200, -50])
#             benchWarm()
#     else: 
#         #Turn 270 degree
#         asebaNetwork.SendEventName('motor.target', [100, 50])
#         #forward
#         asebaNetwork.SendEventName('motor.target', [200, 50])
#         if scan_data[0] < 200:  
#             #Turn 180 degree and back into wall 
#             asebaNetwork.SendEventName('motor.target', [200, 50])
#             asebaNetwork.SendEventName('motor.target', [-200, -50])
#             benchWarm()

# def returnToRest2(): #we can go backwards
#     # turn CCW until minimum is between 170 and 190 degrees behind you.
#     if np.argmin(np.array(scan_data)) in range(170,190):
#         inOrientation = True
#     else:
#         inOrientation = False

#     while not inOrientation:
#         asebaNetwork.SendEventName(
#         'motor.target', [0,5])
#         if np.argmin(np.array(scan_data)) in range(170,190):
#             inOrientation = True

#     asebaNetwork.SendEventName(
#     'motor.target', [0,0])
#     sleep(5)
#     print("Here. Lets go to the wall.")
#     if min((scan_data)) > 200: # we are close to the wall
#         benchWarm()
#     else:
#         asebaNetwork.SendEventName('motor.target', [-200, -50]) #move backwards
#         while min((scan_data)) > 200: # until wall is sensed.
#             sleep(0.1)
#         asebaNetwork.SendEventName('motor.target', [0, 0]) #stop as we are out of the while loop
#         benchWarm()

def returnToRest():
    # turn CCW until minimum is between 170 and 190 degrees behind you.
    if np.argmin(np.array(scan_data)) in range(350,360) or np.argmin(np.array(scan_data)) in range (0,10):
        print(np.argmin(np.array(scan_data)))
        print(scan_data[np.argmin(np.array(scan_data))])
        inOrientation = True
    else:
        inOrientation = False
    while not inOrientation:
        asebaNetwork.SendEventName(
        'motor.target', [0,5])
        if np.argmin(np.array(scan_data)) in range(350,360) or np.argmin(np.array(scan_data)) in range (0,10):
            inOrientation = True
    asebaNetwork.SendEventName(
    'motor.target', [0,0])
    sleep(5)
    print("Here. Lets go to the wall.")
    if min((scan_data)) > 150: # we are close to the wall
        asebaNetwork.SendEventName('motor.target', [0,50])
        sleep(14)
        asebaNetwork.SendEventName('motor.target', [0, 0]) #stop as we are out of the while loop
        benchWarm()
    else:
        asebaNetwork.SendEventName('motor.target', [200, 50]) #move backwards
        while min((scan_data)) > 150: # until wall is sensed.
            sleep(0.1)
        asebaNetwork.SendEventName('motor.target', [0, 0]) #stop as we are out of the while loop
        asebaNetwork.SendEventName('motor.target', [0,50])
        sleep(14)
        asebaNetwork.SendEventName('motor.target', [0, 0]) #stop as we are out of the while loop
        benchWarm()

# ----------------------------------------------------------

scanner_thread = threading.Thread(target=lidarScan, daemon = True)
scanner_thread.start()

IR_thread = threading.Thread(target=infraredScan, daemon = True)
IR_thread.start()

# receiving_thread = threading.Thread(target=receiveInformation, daemon = True)
# receiving_thread.start()

# location_thread = threading.Thread(target=locationFinder, daemon = True)
# location_thread.start()

#------------------ Main loop here -------------------------

def mainLoop():
    benchWarm() # we only call benchwarm here, because all other functions call each other

def testLoop():
    moveToDanceFloor(3)

#------------------- Main loop end ------------------------

if __name__ == '__main__':
    #testCamera()
    #testThymio()
    #testLidar()
    sleep(1) #Warmup Lidar
    try:
        while True:
            # receiveInformation()
            mainLoop()
    except KeyboardInterrupt:
        print("Stopping robot")
        exit_now = True
        sleep(1)
        lidar.stop()
        lidar.disconnect()
        asebaNetwork.SendEventName(
        'motor.target',
        [0, 0])
        os.system("pkill -n asebamedulla")
        print("asebamodulla killed")
