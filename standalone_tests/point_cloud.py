# Numpy Clouds
# http://app.wandb.ai/nbaryd/client-standalone_tests/runs/ly8g46vm?workspace=user-nbaryd

# 3D models
# http://app.test/nbaryd/client-standalone_tests/runs/0rb3xwke?workspace=user-nbaryd

import numpy as np
import wandb
from math import sin, cos, pi

point_cloud_1 = np.array([[0, 0, 0, 1],
                          [0, 0, 1, 13],
                          [0, 1, 0, 2],
                          [0, 1, 0, 4]])

point_cloud_2 = np.array([[0, 0, 0],
                          [0, 0, 1],
                          [0, 1, 0],
                          [0, 1, 0]])

# Generate a symetric pattern
POINT_COUNT = 20000

# Choose a random sample
theta_chi = pi * np.random.rand(POINT_COUNT, 2)


def gen_point(theta, chi, i):
    p = sin(theta) * 4.5 * sin(i + 1 / 2 * (i * i + 2)) + \
        cos(chi) * 7 * sin((2 * i - 4) / 2 * (i + 2))

    x = p * sin(chi) * cos(theta)
    y = p * sin(chi) * sin(theta)
    z = p * cos(chi)

    r = sin(theta) * 120 + 120
    g = sin(x) * 120 + 120
    b = cos(y) * 120 + 120

    return [x, y, z, r, g, b]


def wave_pattern(i):
    return np.array([gen_point(theta, chi, i) for [theta, chi] in theta_chi])


wandb.init()

# Tests 3d OBJ

wandb.log({"gltf": wandb.Object3D(open("tests/fixtures/Duck.gltf")),
           "obj": wandb.Object3D(open("tests/fixtures/cube.obj"))})

# Tests numpy clouds
# for i in range(0, 200, 10):
#     wandb.log({"Clouds": [wandb.Object3D(point_cloud_1), wandb.Object3D(point_cloud_2)],
#                "Colored_Cloud": wandb.Object3D(wave_pattern(i))})
