---
name: ha-docker-yaml-sync
description: Inspect a running Docker environment for Home Assistant containers, copy `scenes.yaml`, `automations.yaml`, and `scripts.yaml` out of the active HA container into the local working directory, edit the requested YAML safely, copy the updated files back into the container, and provide the restart command. Use when the user wants to modify Home Assistant YAML stored inside a Docker container rather than editing files directly on the host.
---

# HA Docker YAML Sync

Use this skill when Home Assistant runs in Docker and the task is to inspect or edit the YAML files stored inside the running container.

## Workflow

1. Identify the active Home Assistant container.
   - Run `docker ps --format '{{.Names}}\t{{.Image}}'`.
   - Prefer containers whose name or image clearly matches `homeassistant`, `home-assistant`, or `ha`.
   - If more than one plausible container appears, stop and surface the ambiguity instead of guessing.

2. Copy the target files from the container to the current working directory.
   - Assume the Home Assistant config directory inside the container is `/config` unless inspection proves otherwise.
   - Copy these files:
     - `scenes.yaml`
     - `automations.yaml`
     - `scripts.yaml`
   - Use `docker cp <container>:/config/<file> ./<file>`.
   - If a file is missing, report that clearly and continue only with the files that actually exist.

3. Inspect and edit only the file(s) needed for the user's request.
   - Follow Home Assistant YAML conventions:
     - Use 2-space indentation.
     - Keep booleans lowercase: `true` / `false`.
     - Quote strings only when needed.
     - Keep entity IDs in `domain.object_id` format.
   - Preserve the existing file structure and style instead of rewriting unrelated entries.
   - For `automations.yaml`, remember the top level is usually a YAML list of automation objects.
   - For `scripts.yaml`, remember the top level is usually a mapping keyed by script ID.
   - For `scenes.yaml`, preserve the existing scene object layout and existing entity blocks.
   - Do not invent device IDs, entity IDs, or service names; reuse what is already present or ask the user when the target is unclear.

4. Copy the modified files back into the container.
   - Use `docker cp ./<file> <container>:/config/<file>`.
   - Only copy back the files you actually changed.
   - Do not restart the container automatically unless the user explicitly asks for it.

5. Provide the restart command to the user.
   - Prefer:
     - `docker restart <container>`
   - If the container is obviously managed by Compose and the compose project name is known from context, it is acceptable to also mention the equivalent Compose restart command.

## Command Pattern

List likely Home Assistant containers:

```bash
docker ps --format '{{.Names}}\t{{.Image}}' | rg -i 'homeassistant|home-assistant|(^|[-_])ha($|[-_])'
```

Copy the three YAML files out:

```bash
docker cp <container>:/config/scenes.yaml ./scenes.yaml
docker cp <container>:/config/automations.yaml ./automations.yaml
docker cp <container>:/config/scripts.yaml ./scripts.yaml
```

Copy changed files back:

```bash
docker cp ./automations.yaml <container>:/config/automations.yaml
docker cp ./scripts.yaml <container>:/config/scripts.yaml
docker cp ./scenes.yaml <container>:/config/scenes.yaml
```

Restart command to provide:

```bash
docker restart <container>
```

## Guardrails

- Do not modify unrelated YAML entries just to normalize formatting.
- Do not assume every HA container uses the same path layout if inspection contradicts `/config`.
- Do not overwrite host-side files outside the current working directory.
- Do not restart the Home Assistant container automatically unless the user explicitly requests execution.
- Do not claim the changes are active until the container is restarted or HA reloads the relevant configuration.
