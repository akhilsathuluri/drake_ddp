#!/usr/bin/env python

##
#
# Do swing-up control of an acrobot
#
##

import numpy as np
from pydrake.all import *
import time

####################################
# Parameters
####################################

T = 2          # total simulation time (S)
dt = 1e-2      # simulation timestep

# CONST = constant (zero) torque
# DT = direct transcription
# DDP = differential dynamic programming
control_method = "CONST" 

# Initial state
x0 = np.array([0,0,0,0])

####################################
# Create system diagram
####################################
builder = DiagramBuilder()

plant, scene_graph = AddMultibodyPlantSceneGraph(builder, dt)
urdf = FindResourceOrThrow("drake/examples/acrobot/Acrobot.urdf")
robot = Parser(plant=plant).AddModelFromFile(urdf)

plant.Finalize()
assert plant.geometry_source_is_registered()

if control_method == "CONST":
    controller = builder.AddSystem(ConstantVectorSource(np.zeros(1)))
elif control_method == "DT":
    pass
elif control_method == "DDP":
    pass
else:
    raise ValueError("Unrecognized control method %s"%control_method)

builder.Connect(
        controller.get_output_port(),
        plant.get_actuation_input_port())

logger = LogVectorOutput(plant.get_state_output_port(), builder)

DrakeVisualizer().AddToBuilder(builder, scene_graph)
ConnectContactResultsToDrakeVisualizer(builder, plant, scene_graph)

diagram = builder.Build()
diagram_context = diagram.CreateDefaultContext()

######################################
## Set up simulation
######################################
simulator = Simulator(diagram, diagram_context)
simulator.set_target_realtime_rate(-1.0)

plant_context = diagram.GetMutableSubsystemContext(
        plant, diagram_context)
plant.SetPositionsAndVelocities(plant_context, x0)

#simulator.AdvanceTo(T)

#####################################
# Solve Trajectory Optimization
#####################################

# Create a system model to do the optimization over
plant_ = MultibodyPlant(dt)
Parser(plant_).AddModelFromFile(urdf)
plant_.Finalize()
context_ = plant_.CreateDefaultContext()

# Set up the solver object
trajopt = DirectTranscription(
        plant_, context_, 
        input_port_index=plant.get_actuation_input_port().get_index(),
        num_time_samples=int(T/dt))

# Add constraints
x = trajopt.state()
u = trajopt.input()
x_init = trajopt.initial_state()

trajopt.prog().AddConstraint(eq( x_init, x0 ))

x_err = x - np.array([np.pi, 0, 0, 0])

trajopt.AddRunningCost(0.01*x_err.T@x_err + 0.01*u.T@u)
trajopt.AddFinalCost(200*x_err.T@x_err)

# Solve the optimization problem
st = time.time()
res = Solve(trajopt.prog())
solve_time = time.time() - st
assert res.is_success(), "trajectory optimizer failed"
solver_name = res.get_solver_id().name()
print(f"Solved in {solve_time} seconds using {solver_name}")

# Extract the solution
timesteps = trajopt.GetSampleTimes(res)
states = trajopt.GetStateSamples(res)
inputs = trajopt.GetInputSamples(res)

#####################################
# Playback on visualizer
#####################################

while True:
    # Just keep playing back the trajectory
    for i in range(len(timesteps)):
        t = timesteps[i]
        x = states[:,i]

        diagram_context.SetTime(t)
        plant.SetPositionsAndVelocities(plant_context, x)
        diagram.Publish(diagram_context)

        time.sleep(dt-3e-4)
    time.sleep(1)
