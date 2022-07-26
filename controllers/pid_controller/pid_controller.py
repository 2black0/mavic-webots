"""pid_controller controller"""

# get the variable
from var import *

# declaration library
from controller import Robot
from controller import Keyboard
from controller import Motor
from controller import Camera
from controller import Gyro
from controller import Compass
from controller import InertialUnit
from controller import GPS
from controller import LED

import numpy as np
import math
import cv2
from cv2 import aruco
import time

# instance the robot
robot = Robot()

# time step
timestep = int(robot.getBasicTimeStep())


class Sensor:
    def __init__(self, robot):
        self.robot = robot
        self.imu = self.robot.getDevice("inertial unit")
        self.gyro = self.robot.getDevice("gyro")
        self.gps = self.robot.getDevice("gps")
        self.compass = self.robot.getDevice("compass")
        self.camera = self.robot.getDevice("camera")

    def enable(self, timestep):
        self.imu.enable(timestep)
        self.gyro.enable(timestep)
        self.gps.enable(timestep)
        self.compass.enable(timestep)
        self.camera.enable(timestep)

    def read_imu(self):
        self.roll = self.imu.getRollPitchYaw()[0] + math.pi / 2.0
        self.pitch = self.imu.getRollPitchYaw()[1]
        self.yaw = self.imu.getRollPitchYaw()[2]
        return self.roll, self.pitch, self.yaw

    def read_gyro(self):
        self.roll_accel = self.gyro.getValues()[0]
        self.pitch_accel = self.gyro.getValues()[1]
        self.yaw_accel = self.gyro.getValues()[2]
        return self.roll_accel, self.pitch_accel, self.yaw_accel

    def read_gps(self):
        self.xpos = self.gps.getValues()[0]
        self.ypos = self.gps.getValues()[2]
        self.zpos = self.gps.getValues()[1]
        return self.xpos, self.ypos, self.zpos

    def read_compass(self):
        self.compass_value = self.compass.getValues()
        self.heading = math.atan2(self.compass_value[0], self.compass_value[1]) - (math.pi / 2)
        if self.heading < -math.pi:
            self.heading = self.heading + (2 * math.pi)
        return self.heading

    def read_camera(self):
        self.camera_height = self.camera.getHeight()
        self.camera_width = self.camera.getWidth()
        self.image = self.camera.getImage()
        self.image = np.frombuffer(self.image, np.uint8).reshape((self.camera_height, self.camera_width, 4))
        return self.image, self.camera_height, self.camera_width


class Actuator:
    def __init__(self, robot):
        self.robot = robot
        self.motor_fl = self.robot.getDevice("front left propeller")
        self.motor_fr = self.robot.getDevice("front right propeller")
        self.motor_rl = self.robot.getDevice("rear left propeller")
        self.motor_rr = self.robot.getDevice("rear right propeller")
        self.camera_roll = self.robot.getDevice("camera roll")
        self.camera_pitch = self.robot.getDevice("camera pitch")
        self.camera_yaw = self.robot.getDevice("camera yaw")

    def arming(self, arming_speed=0.0):
        self.motor_fl.setPosition(float("inf"))
        self.motor_fl.setVelocity(arming_speed)
        self.motor_fr.setPosition(float("inf"))
        self.motor_fr.setVelocity(arming_speed)
        self.motor_rl.setPosition(float("inf"))
        self.motor_rl.setVelocity(arming_speed)
        self.motor_rr.setPosition(float("inf"))
        self.motor_rr.setVelocity(arming_speed)

    def gimbal_down(self, roll_angle=0.0, pitch_angle=0.0, yaw_angle=0.0):
        self.camera_roll.setPosition(roll_angle)
        self.camera_pitch.setPosition(pitch_angle)
        self.camera_yaw.setPosition(yaw_angle)

    def motor_speed(self, motor_fl=0, motor_fr=0, motor_rl=0, motor_rr=0):
        self.motor_fl.setVelocity(motor_fl)
        self.motor_fr.setVelocity(-motor_fr)
        self.motor_rl.setVelocity(-motor_rl)
        self.motor_rr.setVelocity(motor_rr)


class Controller:
    def __init__(
        self,
        roll_param,
        pitch_param,
        yaw_param,
        z_param,
        yaw_target=0.0,
        x_target=0.0,
        y_target=0.0,
        z_target=3.0,
        z_takeoff=68.5,
        z_offset=0.6,
    ):
        self.roll_param = roll_param
        self.pitch_param = pitch_param
        self.yaw_param = yaw_param
        self.z_param = z_param
        self.yaw_target = yaw_target
        self.x_target = x_target
        self.y_target = y_target
        self.z_target = z_target
        self.z_takeoff = z_takeoff
        self.z_offset = z_offset

    def convert_to_attitude(self, x_error, y_error, yaw):
        self.c, self.s = np.cos(yaw), np.sin(yaw)
        self.R = np.array(((self.c, -self.s), (self.s, self.c)))
        self.converted = np.matmul([x_error, y_error], self.R)
        return self.converted

    def error_calculation(self, gps=[0, 0, 0], marker=[0, 0, 0, 0], status=False):
        self.z_error = self.z_target - gps[2]
        if status:
            if marker[1] != 0:
                self.y_error = (marker[2] - marker[1]) / (marker[1] / 3)
                self.x_error = -(marker[3] - marker[0]) / (marker[0] / 3)
            else:
                self.x_error = 0
                self.y_error = 0
        else:
            self.x_error = gps[0] - self.x_target
            self.y_error = gps[1] - self.y_target
        return self.x_error, self.y_error, self.z_error

    def calculate(self, imu=[0, 0, 0], gyro=[0, 0, 0], error=[0, 0, 0], head=0):
        self.error = error
        self.pitch_error, self.roll_error = self.convert_to_attitude(
            np.clip(self.error[0], -3.5, 3.5), np.clip(self.error[1], -3.5, 3.5), head
        )

        self.roll_input = (
            self.roll_param[0] * np.clip(imu[0], -0.5, 0.5) + gyro[0] + np.clip(self.roll_error, -1.0, 1.0)
        )
        self.pitch_input = (
            self.pitch_param[0] * np.clip(imu[1], -0.5, 0.5) - gyro[1] - np.clip(self.pitch_error, -1.0, 1.0)
        )
        self.yaw_input = self.yaw_param[0] * (self.yaw_target - head)
        self.z_diff = np.clip(self.error[2] + self.z_offset, -1.0, 1.0)
        self.z_input = self.z_param[0] * math.pow(self.z_diff, 3.0)
        return self.z_takeoff, self.z_input, self.roll_input, self.pitch_input, self.yaw_input

    def gimbal_control(self, gyro=[0, 0, 0], roll_angle=0.0, pitch_angle=0.0, yaw_angle=0.0):
        pitch_gimbal = np.clip(((-0.1 * gyro[1]) + pitch_angle), -0.5, 1.7)
        roll_gimbal = np.clip((-0.115 * gyro[0] + roll_angle), -0.5, 0.5)
        yaw_gimbal = np.clip((-0.115 * gyro[2] + yaw_angle), -1.7, 1.7)
        return roll_gimbal, pitch_gimbal, yaw_gimbal


class Marker:
    def __init__(self):
        self.radius = 3
        self.color_blue = (0, 0, 255)
        self.color_red = (255, 0, 0)
        self.thickness = 3

    def find_aruco(self, image):
        self.image = image[0]
        self.image_height = image[1]
        self.image_width = image[2]
        self.gray = cv2.cvtColor(self.image, cv2.COLOR_BGR2GRAY)
        self.aruco_dict = aruco.Dictionary_get(aruco.DICT_6X6_250)
        self.parameters = aruco.DetectorParameters_create()
        self.corner, self.id, self.reject = aruco.detectMarkers(self.gray, self.aruco_dict, parameters=self.parameters)
        return self.corner, self.id, self.reject

    def get_center(self):
        self.corner_lb = (int(self.corner[0][0][0][0]), int(self.corner[0][0][0][1]))
        self.corner_lt = (int(self.corner[0][0][1][0]), int(self.corner[0][0][1][1]))
        self.corner_rb = (int(self.corner[0][0][2][0]), int(self.corner[0][0][2][1]))
        self.corner_rt = (int(self.corner[0][0][3][0]), int(self.corner[0][0][3][1]))
        self.center_x = (int(self.corner[0][0][3][0]) / 2) + (int(self.corner[0][0][0][0]) / 2)
        self.center_y = (int(self.corner[0][0][2][1]) / 2) + (int(self.corner[0][0][3][1]) / 2)
        return self.image_height, self.image_width, self.center_x, self.center_y

    def create_marker(self, xpos, ypos, radius=3, color=(255, 0, 0), thickness=2):
        self.image = cv2.circle(self.image, (int(xpos), int(ypos)), radius, color, thickness)
        return self.image, 0, 0


sensor = Sensor(robot)
sensor.enable(timestep)

motor = Actuator(robot)
motor.arming()
marker = Marker()

keyboard = Keyboard()
keyboard.enable(timestep)

while robot.step(timestep) != -1:
    imu = sensor.read_imu()
    gyro = sensor.read_gyro()
    gps = sensor.read_gps()
    head = sensor.read_compass()
    image = sensor.read_camera()

    # print("roll={: .2f} | pitch={: .2f} | yaw={: .2f}".format(imu[0], imu[1], imu[2]))
    # print("roll_accel={: .2f} | pitch_accel={: .2f} | yaw_accel={: .2f}".format(gyro[0], gyro[1], gyro[2]))
    # print("xpos={: .2f} | ypos={: .2f} | zpos={: .2f}".format(gps[0], gps[1], gps[2]))
    # print("heading={: .2f}".format(head))
    # print("x_tar={: .2f}|y_tar={: .2f}|z_tar={: .2f}|yaw_tar={: .2f}".format(x_target, y_target, z_target, yaw_target))

    key = keyboard.getKey()
    while key > 0:
        if key == ord("T") and status_takeoff == False:
            status_takeoff = True
            motor.arming(arming_speed=1.0)
            motor.gimbal_down(pitch_angle=1.6)
            z_target = 5.0
            print("Arming and Take Off")
            time.sleep(0.1)
            break
        if key == Keyboard.UP:
            z_target += 0.01
            print("z_target=", z_target)
            break
        if key == Keyboard.DOWN:
            z_target -= 0.01
            print("z_target=", z_target)
            break
        if key == Keyboard.RIGHT:
            yaw_target += 0.01
            print("yaw_target=", yaw_target)
            break
        if key == Keyboard.LEFT:
            yaw_target -= 0.01
            print("yaw_target=", yaw_target)
            break
        if key == ord("W"):
            x_target -= 0.01
            print("x_target=", x_target)
            break
        if key == ord("S"):
            x_target += 0.01
            print("x_target=", x_target)
            break
        if key == ord("A"):
            y_target += 0.01
            print("y_target=", y_target)
            break
        if key == ord("D"):
            y_target -= 0.01
            print("y_target=", y_target)
            break
        if key == ord("R") and status_takeoff == True:
            status_aruco = not status_aruco
            print("Status Aruco:", status_aruco)
            time.sleep(0.1)
            break
        if key == Keyboard.HOME:
            print(" Go Home")
            x_target = 0.0
            y_target = 0.0
            z_target = 10.0
            yaw_target = 0.0
            time.sleep(0.1)
            break
        """
        if key == ord("G") and status_takeoff == True:
            status_gimbal = not status_gimbal
            print("Status Gimbal:", status_gimbal)
            time.sleep(0.1)
            break
        if key == ord("L") and status_takeoff == True:
            print("Landing Mode")
            status_landing = True
            x_target = 0.0
            y_target = 0.0
            z_target = 10.0
            yaw_target = 0.0
            status_aruco = True
            time.sleep(0.1)
            break"""

    # if status_landing == False:
    #    z_target = z_target

    controller = Controller(
        roll_param=roll_param,
        pitch_param=pitch_param,
        yaw_param=yaw_param,
        z_param=z_param,
        yaw_target=yaw_target,
        x_target=x_target,
        y_target=y_target,
        z_target=z_target,
        # z_takeoff=68.5,
        # z_offset=0.6,
    )

    error_cal = controller.error_calculation(gps=gps, marker=marker_pos, status=status_aruco)
    action = controller.calculate(imu=imu, gyro=gyro, error=error_cal, head=head)
    gimbal_cal = controller.gimbal_control(gyro=gyro, pitch_angle=1.6)

    motor_fl = action[0] + action[1] - action[2] - action[3] + action[4]
    motor_fr = action[0] + action[1] + action[2] - action[3] - action[4]
    motor_rl = action[0] + action[1] - action[2] + action[3] - action[4]
    motor_rr = action[0] + action[1] + action[2] + action[3] + action[4]

    if status_takeoff == False:
        motor_fl = motor_fr = motor_rl = motor_rr = 0.0

    # print(
    #    "z_in:{: .2f} | roll_in:{: .2f} | pitch_in:{: .2f} | yaw_in:{: .2f} | motor_fl:{: .2f} | motor_fr:{: .2f} | motor_rl:{: .2f} | motor_rr:{: .2f}".format(
    #        action[1], action[2], action[3], action[4], motor_fl, motor_fr, motor_rl, motor_rr
    #    )
    # )

    # if status_takeoff == True and status_landing == True:
    #    z_target = z_target - 0.05

    motor.motor_speed(motor_fl=motor_fl, motor_fr=motor_fr, motor_rl=motor_rl, motor_rr=motor_rr)
    motor.gimbal_down(gimbal_cal[0], gimbal_cal[1], gimbal_cal[2])

    corner, id, reject = marker.find_aruco(image=image)
    if id is not None and status_aruco == True:
        marker_pos = marker.get_center()
        image = marker.create_marker(xpos=int(marker_pos[1] / 2), ypos=int(marker_pos[0] / 2), color=(255, 255, 0))
        image = marker.create_marker(xpos=marker_pos[2], ypos=marker_pos[3])

    cv2.imshow("camera", image[0])
    cv2.waitKey(1)

cv2.destroyAllWindows()
