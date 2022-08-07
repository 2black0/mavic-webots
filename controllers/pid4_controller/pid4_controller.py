"""pid4_controller controller."""

from controller import Robot, Keyboard
from mavic_toolkit import Sensor, Actuator
from time import sleep
from params import *
from simple_pid import PID
import numpy as np
import cv2

robot = Robot()
timestep = int(robot.getBasicTimeStep())
sensor = Sensor(robot)
sensor.enable(timestep)
motor = Actuator(robot)
motor.arming(5.0)
keyboard = Keyboard()
keyboard.enable(timestep)

xPID = PID(float(x_param[0]), float(x_param[1]), float(x_param[2]), setpoint=float(x_target))
yPID = PID(float(y_param[0]), float(y_param[1]), float(y_param[2]), setpoint=float(y_target))
zPID = PID(float(z_param[0]), float(z_param[1]), float(z_param[2]), setpoint=float(z_target))
yawPID = PID(float(yaw_param[0]), float(yaw_param[1]), float(yaw_param[2]), setpoint=float(yaw_target))

xPID.output_limits = (-2.5, 2.5)
yPID.output_limits = (-2.5, 2.5)
zPID.output_limits = (-5, 5)
yawPID.output_limits = (-2.5, 2.5)

while robot.step(timestep) != -1:
    roll, pitch, yaw = sensor.read_imu(show=True)
    roll_accel, pitch_accel, yaw_accel = sensor.read_gyro()
    xpos, ypos, zpos = sensor.read_gps()
    head = sensor.read_compass_head()

    key = keyboard.getKey()
    while key > 0:
        if key == ord("T") and status_takeoff == False:
            status_takeoff = True
            status_landing = False
            z_target = 3.0
            print("Arming and Take Off")
            sleep(0.25)
            break
        if key == Keyboard.UP:
            z_target += 0.1
            print("z_target=", z_target)
            break
        if key == Keyboard.DOWN:
            z_target -= 0.1
            print("z_target=", z_target)
            break
        if key == ord("W"):
            x_target -= 1
            print("x_target=", x_target)
            break
        if key == ord("S"):
            x_target += 1
            print("x_target=", x_target)
            break
        if key == ord("A"):
            y_target += 1
            print("y_target=", y_target)
            break
        if key == ord("D"):
            y_target -= 1
            print("y_target=", y_target)
            break
        if key == Keyboard.RIGHT:
            yaw_target += 1
            if yaw_target >= 180:
                yaw_target = 180
            elif yaw_target <= -180:
                yaw_target = -180
            print("yaw_target=", yaw_target)
            break
        if key == Keyboard.LEFT:
            yaw_target -= 1
            if yaw_target >= 180:
                yaw_target = 180
            elif yaw_target <= -180:
                yaw_target = -180
            print("yaw_target=", yaw_target)
            break
        if key == ord("G"):
            status_gimbal = not status_gimbal
            if status_gimbal == True:
                pitch_gimbal_angle = 1.6
            print("Gimbal Stabilize ", status_gimbal)
            sleep(0.25)
            break
        if key == ord("I"):
            pitch_gimbal_angle += 0.005
            if pitch_gimbal_angle >= 1.7:
                pitch_gimbal_angle = 1.7
            print("pitch_gimbal_angle=", pitch_gimbal_angle)
            break
        if key == ord("K"):
            pitch_gimbal_angle -= 0.005
            if pitch_gimbal_angle <= -0.5:
                pitch_gimbal_angle = -0.5
            print("pitch_gimbal_angle=", pitch_gimbal_angle)
            break
        if key == Keyboard.HOME:
            print("Go Home")
            x_target = 0.0
            y_target = 0.0
            z_target = 10.0
            yaw_target = 0.0
            sleep(0.25)
            break
        if key == ord("L") and status_landing == False:
            status_landing = True
            status_takeoff = False
            z_target = 0.0
            print("Landing")
            sleep(0.25)
            break

    xPID.setpoint = x_target
    yPID.setpoint = y_target
    zPID.setpoint = z_target
    yawPID.setpoint = yaw_target

    roll_error = yPID(ypos)
    pitch_error = xPID(xpos)

    vertical_input = zPID(zpos)
    roll_input = (roll_param[0] * roll) + (roll_param[2] * roll_accel) - roll_error
    pitch_input = (pitch_param[0] * pitch) - (pitch_param[2] * pitch_accel) + pitch_error
    yaw_input = yawPID(head)

    motor_fl = np.clip((vertical_thrust + vertical_input - roll_input - pitch_input - yaw_input), 0, 100)
    motor_fr = np.clip((vertical_thrust + vertical_input + roll_input - pitch_input + yaw_input), 0, 100)
    motor_rl = np.clip((vertical_thrust + vertical_input - roll_input + pitch_input + yaw_input), 0, 100)
    motor_rr = np.clip((vertical_thrust + vertical_input + roll_input + pitch_input - yaw_input), 0, 100)

    if status_gimbal == True:
        roll_gimbal = np.clip((-0.001 * roll_accel + roll_gimbal_angle), -0.5, 0.5)
        pitch_gimbal = np.clip(((-0.001 * pitch_accel) + pitch_gimbal_angle), -0.5, 1.7)
        yaw_gimbal = np.clip((-0.001 * yaw_accel + yaw_gimbal_angle), -1.7, 1.7)
        motor.gimbal_down(roll_gimbal, pitch_gimbal, yaw_gimbal)

    if status_landing == False and status_takeoff == False:
        motor_fl = motor_fr = motor_rl = motor_rr = 0

    if status_landing == True and zpos <= 0.15:
        motor_fl = motor_fr = motor_rl = motor_rr = 0

    motor.motor_speed(motor_fl=motor_fl, motor_fr=motor_fr, motor_rl=motor_rl, motor_rr=motor_rr)