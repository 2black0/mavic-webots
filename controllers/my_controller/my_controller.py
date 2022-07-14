"""my_controller controller."""

from controller import (
    Robot,
    Motor,
    Camera,
    InertialUnit,
    Gyro,
    Compass,
    GPS,
    LED,
    Keyboard,
)

import math
import numpy as np
import struct


# import numpy as np
# import cv2, PIL
# from cv2 import aruco
# import matplotlib.pyplot as plt
# import matplotlib as mpl
# import pandas as pd

# import numpy
import cv2
import cv2.aruco as aruco
from matplotlib import pyplot as plt
import argparse
import imutils
import cv2
import sys
from time import sleep

robot = Robot()

timestep = int(robot.getBasicTimeStep())

keyboard = Keyboard()
keyboard.enable(timestep)

imu = robot.getDevice("inertial unit")
imu.enable(timestep)

camera = robot.getDevice("camera")
camera.enable(timestep)
# camera.recognitionEnable(timestep)

gps = robot.getDevice("gps")
gps.enable(timestep)

compass = robot.getDevice("compass")
compass.enable(timestep)

gyro = robot.getDevice("gyro")
gyro.enable(timestep)

camera_roll_motor = robot.getDevice("camera roll")
camera_pitch_motor = robot.getDevice("camera pitch")
camera_yaw_motor = robot.getDevice("camera yaw")

front_left_motor = robot.getDevice("front left propeller")
front_right_motor = robot.getDevice("front right propeller")
rear_left_motor = robot.getDevice("rear left propeller")
rear_right_motor = robot.getDevice("rear right propeller")
motors = [front_left_motor, front_right_motor, rear_left_motor, rear_right_motor]

for i in range(4):
    motors[i].setPosition(float("inf"))
    motors[i].setVelocity(1.0)
print("arming")

# camera face down
camera_pitch_motor.setPosition(1.6)
camera_yaw_motor.setPosition(0)
camera_roll_motor.setPosition(0)

param_roll = [50, 0, 0]
param_pitch = [30, 0, 0]
param_alti = [2, 0, 0]

set_point_roll = 0.0
set_point_pitch = 0.0
set_point_yaw = 0.0

set_point_x = 0.0
set_point_y = 0.0
set_point_alti = 3.0

int_err_roll = 0.0
int_err_pitch = 0.0
bef_err_alti = 0.0

take_off_pwm = 68.5
alti_pwm_offset = 0.6

MAX_INTEGRAL_ERROR = 4.0
MIN_INTEGRAL_ERROR = -4.0

MAX_PITCH_ANGLE = 0.5
MIN_PITCH_ANGLE = -0.5
MAX_ROLL_ANGLE = 0.5
MIN_ROLL_ANGLE = -0.5


def motor_action(frontLeftMotorSpeed, frontRightMotorSpeed, rearLeftMotorSpeed, rearRightMotorSpeed):
    front_left_motor.setVelocity(frontLeftMotorSpeed)
    front_right_motor.setVelocity(-frontRightMotorSpeed)
    rear_left_motor.setVelocity(-rearLeftMotorSpeed)
    rear_right_motor.setVelocity(rearRightMotorSpeed)


def convert_to_pitch_roll(ex, ey, yaw):
    c, s = np.cos(yaw), np.sin(yaw)
    R = np.array(((c, -s), (s, c)))
    exy_ = np.matmul([ex, ey], R)
    # print("ex = %f, ey = %f" % (ex, ey))
    # print(yaw)
    # print("ex_ = %f, ey_ = %f" % (exy_[0], exy_[1]))
    return exy_[0], exy_[1]


# tutorial https://www.youtube.com/watch?v=AQXLC2Btag4
def findAruco(img, marker_size=6, total_markers=250, draw=True):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    key = getattr(aruco, f"DICT_{marker_size}X{marker_size}_{total_markers}")
    arucoDict = aruco.Dictionary_get(key)
    arucoParam = aruco.DetectorParameters_create()
    bbox, ids, _ = aruco.detectMarkers(gray, arucoDict, parameters=arucoParam)
    print(ids)
    if draw:
        aruco.drawDetectedMarkers(img, bbox)
    return bbox, ids


# cv2.startWindowThread()
# cv2.namedWindow("preview")

while robot.step(timestep) != -1:
    roll = imu.getRollPitchYaw()[0] + math.pi / 2.0
    pitch = imu.getRollPitchYaw()[1]
    yaw = imu.getRollPitchYaw()[2]

    altitude = gps.getValues()[1]
    px = gps.getValues()[0]
    py = gps.getValues()[2]

    roll_acceleration = gyro.getValues()[0]
    pitch_acceleration = gyro.getValues()[1]
    yaw_acceleration = gyro.getValues()[2]

    err_x = px - set_point_x
    err_y = py - set_point_y
    err_alti = set_point_alti - altitude

    err_pitch, err_roll = convert_to_pitch_roll(err_x, err_y, yaw)

    """
    # set_point_pitch = err_x / 20
    if set_point_pitch >= MAX_PITCH_ANGLE:
        set_point_pitch = MAX_PITCH_ANGLE
    if set_point_pitch <= MIN_PITCH_ANGLE:
        set_point_pitch = MIN_PITCH_ANGLE

    # set_point_roll = -(err_y / 20)
    if set_point_roll >= MAX_ROLL_ANGLE:
        set_point_roll = MAX_ROLL_ANGLE
    if set_point_roll <= MIN_ROLL_ANGLE:
        set_point_roll = MIN_ROLL_ANGLE

    # err_roll = roll - set_point_roll
    int_err_roll = int_err_roll + err_roll
    if int_err_roll >= MAX_INTEGRAL_ERROR:
        int_err_roll = MAX_INTEGRAL_ERROR
    if int_err_roll <= MIN_INTEGRAL_ERROR:
        int_err_roll = MIN_INTEGRAL_ERROR
    dif_err_roll = roll_acceleration

    # err_pitch = pitch - set_point_pitch
    int_err_pitch = int_err_pitch + err_pitch
    if int_err_pitch >= MAX_INTEGRAL_ERROR:
        int_err_pitch = MAX_INTEGRAL_ERROR
    if int_err_pitch <= MIN_INTEGRAL_ERROR:
        int_err_pitch = MIN_INTEGRAL_ERROR
    dif_err_pitch = pitch_acceleration

    roll_pwm = err_roll * param_roll[0] + (dif_err_roll * param_roll[2]) + (int_err_roll * param_roll[1])
    pitch_pwm = err_pitch * param_pitch[0] - (dif_err_pitch * param_pitch[2]) + (int_err_pitch * param_pitch[1])

    alti_pwm = (err_alti * param_alti[0])# + (diff_err_alti * param_alti[2])

    """

    # camera_roll_motor.setPosition(-0.115 * roll_acceleration)
    # camera_pitch_motor.setPosition(-0.1 * pitch_acceleration)

    # camera_roll_motor.setPosition(0.5)
    # camera_pitch_motor.setPosition(1.6)
    # camera_yaw_motor.setPosition()

    roll_pwm = param_roll[0] * np.clip(roll, -1.0, 1.0) + roll_acceleration + err_roll
    pitch_pwm = param_pitch[0] * np.clip(pitch, -1.0, 1.0) - pitch_acceleration - err_pitch
    yaw_pwm = 0.05 * (set_point_yaw - yaw)

    clamped_difference_altitude = np.clip(err_alti + alti_pwm_offset, -1.0, 1.0)
    alti_pwm = param_alti[0] * math.pow(clamped_difference_altitude, 3.0)

    frontLeftMotorSpeed = take_off_pwm + alti_pwm - roll_pwm - pitch_pwm + yaw_pwm
    frontRightMotorSpeed = take_off_pwm + alti_pwm + roll_pwm - pitch_pwm - yaw_pwm
    rearLeftMotorSpeed = take_off_pwm + alti_pwm - roll_pwm + pitch_pwm - yaw_pwm
    rearRightMotorSpeed = take_off_pwm + alti_pwm + roll_pwm + pitch_pwm + yaw_pwm

    motor_action(frontLeftMotorSpeed, frontRightMotorSpeed, rearLeftMotorSpeed, rearRightMotorSpeed)

    print(
        "r:{:.2f} | p:{:.2f} | y:{:.2f} | X:{:.2f} | Y:{:.2f} | Z:{:.2f} | gr:{:.2f} | gp:{:.2f} | gy:{:.2f} | er:{:.2f} | ep:{:.2f} | eZ:{:.2f} | ex:{:.2f} | ey:{:.2f} | fl:{:.2f} | fr:{:.2f} | rl:{:.2f} | rr:{:.2f}".format(
            roll,
            pitch,
            yaw,
            px,
            py,
            altitude,
            roll_acceleration,
            pitch_acceleration,
            yaw_acceleration,
            err_roll,
            err_pitch,
            err_alti,
            err_x,
            err_y,
            frontLeftMotorSpeed,
            frontRightMotorSpeed,
            rearLeftMotorSpeed,
            rearRightMotorSpeed,
        )
    )

    # camera tutorial from this link
    # https://erebus.rcj.cloud/docs/tutorials/sensors/rgb-camera/
    image = camera.getImage()
    image = np.frombuffer(image, np.uint8).reshape((camera.getHeight(), camera.getWidth(), 4))
    # frame = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

    # cv2.imshow("frame", frame)
    cv2.imshow("camera", image)

    # im = cv2.VideoCapture(image)
    """
    ARUCO_PARAMETERS = aruco.DetectorParameters_create()
    ARUCO_DICT = aruco.Dictionary_get(aruco.DICT_5X5_1000)

    plt.figure(figsize=(20, 20))
    imgplot = plt.imshow(im, interpolation="nearest")
    plt.show()

    im = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
    corners, ids, rejectedImgPoints = aruco.detectMarkers(im, ARUCO_DICT, parameters=ARUCO_PARAMETERS)

    if ids is not None:
        print("detected: {}".format(len(ids)))
        # for i, corner in zip(ids, corners):
        # print('ID: {}; Corners: {}'.format(i, corner))

        im = aruco.drawDetectedMarkers(im, corners, borderColor=(255, 0, 0))
    else:
        print("NONE")
    plt.figure(figsize=(20, 20))
    imgplot = plt.imshow(im, interpolation="nearest")
    plt.show()
    """
    cv2.waitKey(1)  # Render imshows on screen

# roll zero 0
# roll kiri negatif
# roll kanan positif

# pitch zero 0.07
# pitch up positif
# pitch down negatif

# yaw zero 0
# yaw cw negatif
# yaw ccw positif

# height zero 0.00
# naik positif
# turun negatif

# posisi X 0
# posisi X maju positif
# posisi X mundur negatif

# posisi Y 0
# posisi Y kiri negatif
# posisi Y kanan positif

# nitip link
# https://github.sre.pub/felipenmartins/Robotics-Simulation-Labs
