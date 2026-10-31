# City Delivery Simulator

A small simulated city, a delivery operation, and plenty of room to experiment.

## The Idea

It started with a simple question: What would it take to simulate a small city and the delivery operations happening inside it?

I wanted to build an environment where houses, roads, intersections, traffic lights, drivers, vehicles, and delivery requests coexist and interact.

Not just a visualization of cars moving around a map, but a functioning system in which each element follows its own rules and contributes to what happens next.

A delivery request creates a sequence of decisions: where is the pickup, where does it need to go, which driver should take it, and which route should they follow?

Meanwhile, the city doesn't stop operating. Traffic lights change, vehicles queue at intersections, new requests arrive, and drivers compete for limited road space.

This became the starting point for the City Delivery Simulator.

The idea is to build a simplified representation of a real world system, establish its underlying mechanisms, and gradually introduce more complicated conditions.

I don't intend to reproduce an actual city or delivery company.

Instead, I want to create a controlled environment in which I can experiment with different assumptions, observe their consequences, and investigate how the system can operate more efficiently.

## From Idea to Simulation

I approached this as an environment building experiment.

Rather than starting with a particular optimization algorithm, I started by identifying the elements that would need to exist for the city to function.

* The city: A grid based road network with houses, buildings, intersections, and connections between them.
* Traffic infrastructure: Traffic lights with independent timers and alternating movement phases.
* Drivers and vehicles: Separate entities responsible for operating and moving through the road network.
* Delivery requests: Requests connecting two locations, creating pickup and delivery tasks.
* Routing: A mechanism for determining how vehicles travel between locations.
* Dispatching: A mechanism for assigning available drivers to waiting requests.

Each component has its own responsibilities, but none operates in isolation.

Their interactions are what make the simulation interesting.

I also wanted to be able to watch the environment rather than rely exclusively on numerical outputs.

The renderer therefore provides a visual representation of the city as it evolves, while the underlying simulation remains independent of the graphical interface.

This separation also allows the environment to run without rendering, making repeated experiments and performance comparisons possible.

## What I Want to Explore

The current implementation establishes the initial operating environment. However, most of the interesting questions are still ahead.

I intend to develop the simulator through successive experiments, changing individual mechanisms and observing how those changes affect the overall system.

### 1. Routing Strategies

How should drivers navigate the city?

The current implementation uses a base dispatcher class, with shortest path routing.

This provides a straightforward baseline, but the shortest route isn't necessarily the fastest or most efficient one.

Future experiments could investigate:

* Traffic aware routing.
* Time based route estimation.
* Alternative paths under congestion.
* Routes accounting for road conditions.
* Comparing different routing strategies under identical conditions.

### 2. Dispatching Strategies

How should delivery requests be assigned to drivers?

Choosing the nearest available driver is a reasonable starting point, but it doesn't necessarily produce the best overall outcome.

I want to investigate different assignment strategies and how they affect delivery times, driver utilization, waiting requests, and overall efficiency.

### 3. Demand and Traffic Generation

A city doesn't experience uniform demand throughout the day.

I want to experiment with different request generation mechanisms and traffic conditions, including:

* Uniform and varying delivery demand.
* Rush hour scenarios.
* Uneven distribution of requests.
* Different fleet sizes.
* Changes in traffic light timing.

This will help investigate how the same delivery system behaves under different operating conditions.

### 4. Real World Scenarios and Uncertainty

The initial environment follows basic driving rules.

Eventually, I want to introduce the less predictable elements of real world transportation.

Some possibilities include:

* Drivers occasionally speeding or ignoring traffic signals.
* Accidents and road obstructions.
* Police stops and traffic violations.
* Drivers taking breaks or becoming unavailable.
* Failed or delayed deliveries.
* Weather and other environmental conditions.

The interesting part isn't simply adding random events.

It's understanding how these events interact and how a disruption in one part of the city can affect the rest of the system.

### 5. Intelligent Decision Making

Once the environment and its mechanisms are sufficiently established, I want to explore where intelligent decision making can improve its operation.

Potential directions include heuristic optimization, reinforcement learning, and eventually multi agent approaches.

For example:

* Can a dispatcher learn better assignment policies?
* Can a driver learn to anticipate congestion?
* Can adaptive traffic lights improve overall traffic flow?
* How do different objectives affect the behavior of the system?
* Can cooperation between independent agents produce better outcomes?

These are directions for experimentation, not assumptions about what will work best.

---

## Project Architecture

The simulator is organized around a simulation core that operates independently of the user interface.

The main components are:

| Component       | Responsibility                                                         |
| --------------- | ---------------------------------------------------------------------- |
| src/sim/        | Simulation execution, clock, controller, events and state progression. |
| src/city/       | City generation, roads, intersections, buildings and traffic.          |
| src/agents/     | Drivers, vehicles and generators.                                      |
| src/delivery/   | Delivery requests, dispatching and routing strategies.                 |
|  src/render/    | Graphical representation of the simulation.                            |
|  src/config.py  | Configuration definitions, defaults and validation.                    |
|  src/rng.py     | Controlled random-number generation and reproducibility.               |

### How the Simulation Works

The simulation advances through fixed time steps. Each step coordinates the different systems:

Simulation Clock
       |
       v
Request & Event Generation
       |
       v
Traffic Light Updates
       |
       v
Driver Assignment
       |
       v
Route Planning
       |
       v
Vehicle Movement
       |
       v
Pickup & Delivery Processing
       |
       v
Metrics & State Updates
       |
       v
Next Timestep

The renderer receives simulation snapshots and displays the resulting state. It does not control the underlying mechanics.

### Configurable Strategies

One of the main design considerations is making individual mechanisms replaceable.

For example, routing and dispatching are separate strategies that can be selected through configuration or injected when constructing a simulation.

The current implementations include:

* nearest: Assigns waiting requests to available drivers based on pickup route cost.
* first_available: Assigns waiting requests to available drivers in ID order.
* shortest_path: Finds routes that minimize road distance.

Request and event generation follow similar extension patterns.

The intention is to make experimentation possible without having to rewrite the simulation every time I want to investigate a different approach.

### Reproducibility and Metrics

Randomness is controlled through configurable seeds and independent random streams.

This allows the same initial conditions and generated scenarios to be reproduced, making comparisons between different strategies more meaningful.

The simulator also records metrics such as:

* Completed deliveries.
* Delivery and waiting times.
* Driver utilization.
* Distance travelled.
* Travel and stopped time.
* Active requests.

These measurements provide a way to evaluate what happens beyond simply watching the simulation.

---

## Running the Simulator

Requires Python 3.10 or newer.

### Graphical simulation

Launch the interactive city renderer:

python -m src.cli

The graphical interface allows you to watch vehicles move, observe traffic lights, and follow delivery requests as the simulation progresses.

### Headless simulation

Run without opening the graphical interface:

python -m src.cli --headless

This is useful for running repeated experiments and comparing different configurations.

### Configuration

Print the default configuration:

python -m src.cli --print-config

Load a custom configuration:

python -m src.cli --headless --config scenario.json

Override individual settings:

python -m src.cli --headless --set city.width=14 --set city.height=12

You can also change the random seed, number of drivers, request rate, and dispatcher through command line arguments.

For all available options:

python -m src.cli --help

The full configuration schema and defaults are defined in src/config.py.

---

## Experimenting With the Simulator

The intended workflow is simple:

1. Establish a baseline configuration.
2. Choose a random seed.
3. Change one mechanism or parameter.
4. Run the simulation.
5. Observe the visual behavior and compare the resulting metrics.
6. Repeat under different seeds to investigate whether the results remain consistent.

For example, you could compare two dispatching strategies while keeping the city, fleet, request generation, and random seed unchanged.

The goal is to understand not just which strategy performs better, but also why.

---

## Current State and Limitations

The current version establishes the basic city, traffic, vehicle movement, delivery lifecycle, routing, dispatching, and rendering systems.

It uses a simplified grid based road network, fixed cycle traffic lights, and discrete time vehicle movement.

The default request generator uses a Poisson arrival process, with pickup and destination locations sampled independently.

These are deliberate simplifications.

The simulator is an experimental model, not a calibrated representation of an actual city or delivery operation.

There is still plenty to investigate, improve, and extend.

## Where This Goes Next

I don't consider the current implementation a finished product. It's the foundation for a series of experiments.

I want to keep expanding the environment, introducing new conditions, testing different strategies, and investigating the relationships between individual decisions and overall system performance.

The broader idea is to build a world, understand how its mechanisms work, and then experiment with how it can be controlled and improved.

For now, the city is running. The interesting experiments are just beginning.
