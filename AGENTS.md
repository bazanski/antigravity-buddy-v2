# Workspace Context & Handover Rules - Antigravity Buddy v2 🛸

This is the project root of **Antigravity Buddy v2**, a completely separate, next-generation terminal/IDE companion system using native hooks and WiFi WebSockets.

> [!IMPORTANT]
> This is **Version 2** of the project. Do NOT confuse it with Version 1 (antigravity-buddy) and do NOT mix their statuses. Keep them strictly isolated!

## 🔄 State Synchronization Skill (`agentsync`)

To prevent duplicate work and ensure clean transitions across different agent sessions (e.g. Antigravity, Claude-code, Opencode), you **must** follow the **State Synchronization Pipeline** on startup and completion:

### 1. Startup Checklist (Do this FIRST before anything else)
1. **Pull the latest remote state:** Execute the following command immediately inside the project root:
   ```bash
   python ~/.agentsync/agentsync.py pull
   ```
2. **Read the Active State Checkpoint:** View the [.agent_state.md](.agent_state.md) file at the root of this project folder to inspect:
   * **Active Milestone & Goal** for this project.
   * **Active Ports and Hardware Configurations** (Port 38900, Xiao ESP32-S3 pins, GC9A01 LCD driver) to avoid device conflicts.
   * **Troubleshooting Logs** detailing resolved or outstanding issues.

### 2. Turn-Completion Checklist (Do this before concluding)
1. **Update local progress:** You can update the local state checkpoint manually by editing [.agent_state.md](.agent_state.md) directly, or by using the CLI save command:
   ```bash
   python ~/.agentsync/agentsync.py save -m "[New Milestone]" -c "[Semicolon-separated completed items]" -n "[Semicolon-separated next steps]"
   ```
2. **Push the State to GitHub:** Push your progress to the central state repo so the next local or remote agent can pull it instantly:
   ```bash
   python ~/.agentsync/agentsync.py sync
   ```

> [!IMPORTANT]
> To save tokens and avoid context pollution, do NOT read `GEMINI.md` or `CLAUDE.md` — they both redirect to this file. Always use [README.md](README.md) for project-wide structure and rules.
