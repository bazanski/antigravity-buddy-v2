#!/usr/bin/env python3
import sys
import json
import time
import urllib.request
import urllib.error

HUB_URL = "http://127.0.0.1:38900"

def log_err(msg):
    # Hook output to stdout MUST remain strictly JSON. Log everything to stderr.
    sys.stderr.write(f"[hook_handler] {msg}\n")
    sys.stderr.flush()
    try:
        with open("c:/Users/bazba/Sync/Personal projects/antigravity-buddy-v2/hooks_run.log", "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")
    except Exception:
        pass

def post_event(payload, retries=2):
    for attempt in range(retries + 1):
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                f"{HUB_URL}/event",
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=3.0) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            if attempt < retries:
                log_err(f"POST attempt {attempt+1} failed, retrying: {e}")
                time.sleep(0.3)
            else:
                log_err(f"Failed to post event after {retries+1} attempts: {e}")
    return None

def poll_resolution(prompt_id):
    start_time = time.time()
    while time.time() - start_time < 60.0:
        try:
            with urllib.request.urlopen(f"{HUB_URL}/prompt/{prompt_id}", timeout=2.0) as r:
                res = json.loads(r.read().decode('utf-8'))
                if res.get("resolved") is True:
                    return res.get("decision"), res.get("reason", "")
        except Exception as e:
            log_err(f"Polling error: {e}")
        time.sleep(0.5)
    return "deny", "Approval request timed out after 60s"

def main():
    try:
        # ── Parse hook event type from --event argument ──
        hook_event = None
        for i, arg in enumerate(sys.argv):
            if arg == "--event" and i + 1 < len(sys.argv):
                hook_event = sys.argv[i + 1]
            elif arg.startswith("--event="):
                hook_event = arg.split("=", 1)[1]

        # ── Dump env vars for debugging ──
        import os
        hook_env_keys = [k for k in sorted(os.environ.keys()) if 'HOOK' in k.upper() or 'AGENT' in k.upper() or 'GEMINI' in k.upper() or 'ANTIGRAVITY' in k.upper() or 'TOOL' in k.upper() or 'EVENT' in k.upper()]
        if hook_env_keys:
            for k in hook_env_keys:
                log_err(f"ENV {k}={os.environ[k]}")

        # Read the raw JSON input passed via stdin from the CLI runner
        raw_input = sys.stdin.read()
        if not raw_input.strip():
            log_err("Received empty stdin.")
            sys.exit(0)
            
        data = json.loads(raw_input)
        conversation_id = data.get("conversationId", "unknown")
        transcript_path = data.get("transcriptPath", "")
        log_err(f"Raw hook input: {raw_input.strip()}")
        log_err(f"Hook event type: {hook_event or '(not set)'}")

        # Determine if this is a blocking tool event
        tool_call = data.get("toolCall", None)
        has_tool = tool_call is not None and isinstance(tool_call, dict) and tool_call.get("name")

        # PostToolUse / AfterTool etc are NEVER blocking.
        # PreToolUse IS blocking — it's the only hook that actually fires from hooks.json
        # (settings.json BeforeTool is ignored by the IDE when hooks.json exists)
        non_blocking_events = {"PostToolUse", "PostToolExecution",
                               "AfterTool", "AfterAgent",
                               "SessionStart", "BeforeAgent", "BeforeModel",
                               "AfterModel", "HookTelemetry"}
        is_blocking = (
            has_tool
            and (hook_event is None or hook_event not in non_blocking_events)
        )

        if not is_blocking:
            # Non-blocking telemetry — send to hub and exit immediately
            event_name = hook_event or "HookTelemetry"
            if has_tool:
                event_name = hook_event or "PostToolUse"
            log_err(f"Non-blocking event {event_name} (step {data.get('stepIdx', '?')})")
            event_payload = {
                "session_id": conversation_id,
                "event": event_name,
                "timestamp": time.time(),
                "data": data
            }
            post_event(event_payload)
            sys.exit(0)

        # ── Blocking tool verification ──
        tool_name = tool_call.get("name", "unknown_tool")
        tool_args = tool_call.get("args", {})
        prompt_id = f"prompt_{int(time.time() * 1000)}"
        
        # Format a clear hint of the action to display on screens
        hint = ""
        if tool_args:
            if "CommandLine" in tool_args:
                hint = tool_args["CommandLine"]
            elif "TargetFile" in tool_args:
                hint = f"Edit {tool_args['TargetFile']}"
            elif "command" in tool_args:
                hint = str(tool_args["command"])
            elif "file_path" in tool_args:
                hint = f"Edit {tool_args['file_path']}"
            elif "path" in tool_args:
                hint = f"Edit {tool_args['path']}"
            else:
                hint = json.dumps(tool_args)[:80]
        else:
            hint = f"Run: {tool_name}"

        # Determine available options - pass through if the hook provides them
        opts = data.get("opts", None)
        if not opts:
            opts = data.get("options", None)
        if not opts or not isinstance(opts, list) or len(opts) == 0:
            opts = ["Approve", "Deny"]

        # Post the blocking prompt
        prompt_payload = {
            "session_id": conversation_id,
            "event": hook_event or "BeforeTool",
            "timestamp": time.time(),
            "prompt": {
                "id": prompt_id,
                "tool": tool_name,
                "hint": hint,
                "opts": opts
            }
        }
        
        log_err(f"Tool block [{tool_name}] registered. Awaiting resolution on {prompt_id}...")
        post_event(prompt_payload)

        # Poll the hub for user approval/denial
        decision, reason = poll_resolution(prompt_id)
        log_err(f"Hook resolved with decision: [{decision}] - {reason}")

        # Output the exact JSON output to stdout. CLI parses this to unblock.
        response = {
            "decision": decision,
            "reason": reason,
            "systemMessage": f"Cooperative verification: {decision.upper()}"
        }
        
        print(json.dumps(response))
        sys.stdout.flush()

        # If user denied/blocked, exit with status code 2 to trigger a System Block
        if decision == "deny":
            sys.exit(2)
        else:
            sys.exit(0)

    except Exception as e:
        log_err(f"Fatal exception inside hook handler: {e}")
        # Fail safe: allow the tool to continue on script crash to avoid freezing IDE
        print(json.dumps({"decision": "allow", "reason": f"Hook runner crash: {e}"}))
        sys.exit(0)

if __name__ == '__main__':
    main()
