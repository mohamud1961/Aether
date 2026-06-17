# BigAI Architecture: Multi-Agent Framework (Tong-Cell)

**Source URL:** https://tongagents.mybigai.ac.cn/docs/Tong-Agent/features/framework/multi_agent/
**Translated on:** 2026-03-29

## The Tong-Cell Multi-Agent Framework
TongAgents is built on the `tong-cell` multi-agent framework, which provides robust capabilities for constructing complex, distributed agent systems.

### Core Concepts
1. **Actor**: The fundamental scheduling unit of the Runtime. An Actor can receive and process messages. It can be an intelligent "Agent" or a non-intelligent functional unit.
2. **Runtime**: The container for Actors. It manages Actor lifecycle, execution, and communication.

### Key Characteristics
- **Dynamic Orchestration**: 
    - Actors are created dynamically by the Runtime on demand.
    - Lifecycle management is automated.
    - The number of Actors is not fixed and changes during execution.
    - Actors themselves determine their downstream dependencies.
- **Message-Driven**:
    - Actors do not directly call each other.
    - Communication occurs via messages using `ActorId` or `TopicId`.
    - Actors are independent and decoupled.
    - Actors run concurrently, each with its own message loop.
- **Flexible Communication**:
    - `send`: Asynchronous point-to-point (send and return).
    - `request`: Synchronous point-to-point (wait for response).
    - `publish`: Pub/Sub model for further decoupling.
- **Distributed Support**:
    - **Actor Addressing**: Runtime automatically routes messages transparently.
    - **Peer Architecture**: Bi-directional communication across different nodes.
    - **Multiple Formats**: Supports `dataclass`, `pydantic model`, and `protobuf`.
    - **Seamless Migration**: Actors developed for `LocalRuntime` can move to `NetworkRuntime` without code changes.

### Common Patterns Supported
- **Round Robin**: Sequential polling.
- **Swarm**: Collective, decentralized behavior.
- **Supervisor**: A controller overseeing worker actors.
- **Graph**: Task flow defined as a directed graph.
- **Hierarchical**: Multi-level delegation.
- **Human-in-the-Loop**: Integration of human feedback into the actor loop.
