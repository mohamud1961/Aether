# DeepAgents Terminal Bench Locations

## 1. Experimental Runs (Trajectories & Results)
The extracted trajectories and results from the Terminal Bench 2.0 leaderboard for the `deepagent-harbor` agent are stored in:

`research/sources/trajectories/deepagents/`

Each subdirectory corresponds to a specific task (e.g., `adaptive-rejection-sampler`, `bn-fit-modify`). Inside each task directory, you will find:
- `*-traj.txt`: The full execution trajectory.
- `*.tar.gz`: The final workspace state (results).

## 2. DeepAgent Source Code (Harness)
The source code for the DeepAgent harness and its integration with the Harbor framework is located at:

`research/sources/codebases/deepagents/`

Key components within this codebase:
- `libs/evals/deepagents_harbor/`: The core adapter for the Harbor framework used in Terminal Bench evaluations.
- `libs/deepagents/`: Core logic and middleware.
- `libs/cli/`: Command-line interface for interacting with the agent.
- `libs/acp/`: Agent Control Protocol implementation.

This note only tracks the committed research corpus locations.
