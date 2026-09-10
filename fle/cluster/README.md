# Local Factorio Cluster

This directory contains scripts and configuration files for running and managing multiple Factorio game servers locally using Docker containers.

## Overview

The system allows you to:

- Create and manage multiple Factorio server instances using Docker
- Automatically connect to and initialize each server instance
- Configure server settings, ports, and resources for each instance
- Share scenarios across instances
- Choose between different scenarios (open_world or default_lab_scenario)

## `run-envs.sh`

 - Main script for generating compose yaml
 - Running and managing Factorio instances with options for scenario selection

## Setup and Usage

### Watch an Agent

The local cluster reserves the multiplayer identity `fle-observer`. The scenario
changes that client to a read-only spectator with no character whenever it joins.
It is excluded from agent inventories and entity census. A private, per-cluster
password is generated outside the repository and supplied automatically by
`fle watch`.

Before connecting, set the Factorio multiplayer player name to `fle-observer`.
Then validate the local client and server versions without launching:

```bash
fle watch --check
```

Launch the installed graphical client and connect to instance zero:

```bash
fle watch
```

Instance `N` maps to game port `34197 + N`; select it with
`fle watch --instance N`. The benchmark
server deliberately runs base Factorio only, so a Space Age client may offer to
synchronize its enabled mods before joining. Observer sessions are diagnostic;
official throughput results continue to use the configured accelerated game
speed.

The observer can join, leave, and reconnect while an evaluation is running. FLE
packages its callable Lua runtime as a generated local mod shared by the server
and an isolated observer mod directory, while Factorio `storage` contains data
only. Multiplayer map transfer therefore does not depend on attach order and
your normal Space Age mod configuration is not changed.

For a deliberately non-official, human-readable session, start envd with
`--execution-game-speed 1`. The default remains `10`; changing speed alters
wall-clock behavior and must be reported with any result even though simulated
tick deadlines are unchanged.

### Prerequisites

- Docker installed and running
- Optional: Factorio game client installed locally

### Managing Server Instances with run-envs.sh

The `run-envs.sh` script provides a convenient way to start, stop, and manage Factorio server instances.

#### Basic Usage

```bash
# Start a single instance on a normally generated open_world map
./run-envs.sh

# Start 5 instances with default scenario
./run-envs.sh -n 5

# Start 3 instances with open_world scenario
./run-envs.sh -n 3 -s open_world

# Stop all running instances
./run-envs.sh stop

# Restart the current cluster with the same configuration
./run-envs.sh restart

# Show help information
./run-envs.sh help
```

#### Command Line Options

- `-n NUMBER` - Number of Factorio instances to run (1-33, default: 1)
- `-s SCENARIO` - Scenario to run (open_world or default_lab_scenario, default: open_world)

#### Available Commands

- `start` - Start Factorio instances (default command)
- `stop` - Stop all running instances
- `restart` - Restart the current cluster with the same configuration
- `help` - Show help information

#### Examples with Explicit Commands

```bash
# Start 10 instances with open_world scenario
./run-envs.sh start -n 10 -s open_world

# Restart the current cluster
./run-envs.sh restart
```


### Server Configuration

Each Factorio instance is configured with:

- Resource limits: 1 CPU core and 1024MB memory
- Shared scenarios directory
- Unique UDP port for game traffic (starting at 34197)
- Unique TCP port for RCON (starting at 27015)
- Choice of scenario (open_world or default_lab_scenario)

## Port Mappings

- Game ports (UDP): 34197 + instance_number
- RCON ports (TCP): 27000 + instance_number

## Volume Mounts

The following directories are mounted in each container:

- Scenarios: `../scenarios/default_lab_scenario`, `../scenarios/open_world`
- Mods: `~/Applications/Factorio.app/Contents/Resources/mods`
- Screenshots: `../../data/_screenshots`

## Notes

- The server instances use the `factorio:latest` Docker image (which you can build from the provided Dockerfile in the `docker` directory)
- Each instance can run with either the `default_lab_scenario` or `open_world` scenario
- RCON password is set to "factorio"
- Containers are configured to restart unless stopped manually

## Troubleshooting

### Moving the observer while simulation is paused

`fle watch` automatically opens the companion camera palette after the graphical
observer connects, or reopens it if the observer is already connected and the
palette was closed. `fle watch --check` only checks readiness. You can also open
the palette separately:

```powershell
uv run python -m fle.cluster.observer_camera
```

Use the arrows (or WASD while the palette has focus), choose a 4–64 tile pan
step, and use Zoom +/−. **Agent** or Home recenters on the model's character.
The palette stays above the Factorio window. `--instance N` selects another
local server. Closing the palette leaves the evaluation and observer running.

The controls reposition only the existing read-only spectator through RCON;
they work during model thinking pauses without stepping simulation time or
enabling editor mode. Native WASD inside Factorio still depends on simulation
ticks. A disconnected observer produces an error; reconnect it with `fle watch`
and retry. Pan destinations must already have generated terrain. The palette
does not expose world editing, pause, speed, or benchmark controls.

If you encounter issues:

1. Ensure Docker is running and has sufficient resources
2. Check container logs using `docker logs factorio_<instance_number>`
3. Verify port availability using `netstat` or similar tools
