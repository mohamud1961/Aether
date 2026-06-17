# Trajectory Repository

This directory contains execution trajectories and results for various agents evaluated on terminal-based benchmarks.

**Last Updated:** 2026-03-29

## Directory Structure

- **[BigAI/](./BigAI/)**: Trajectories and traces from the BigAI system.
- **[deepagents/](./deepagents/)**: Extracted trajectories from the DeepAgent-Harbor agent on Terminal Bench 2.0.
- **[terminus-kira/](./terminus-kira/)**: Trajectories from the Terminus-KIRA agent.

## Content Format
Each task-specific directory typically contains:
- `*-traj.txt`: A step-by-step log of the agent's actions and observations.
- `*.tar.gz` or similar: The final state of the task workspace for verification.
