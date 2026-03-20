---
name: stm32-macos-makefile
description: Configure or repair a macOS STM32 Makefile-based workflow with clangd, OpenOCD, ST-Link, and helper shell functions. Use when working on STM32 projects that build with a Makefile and need environment setup, `.clangd` generation, source/include discovery, flashing helpers, or diagnosis of missing ARM toolchain paths on macOS.
---

# STM32 macOS Makefile

## Overview

Use this skill for STM32 projects on macOS when the project is built with a
`Makefile` rather than STM32CubeIDE. This skill helps Codex set up or repair
the local workflow around ARM GCC, `clangd`, `openocd`, `stlink`, and the
source/include lists commonly maintained in CubeMX-generated Makefiles.

Read [references/project-shape.md](references/project-shape.md) when you need
help deciding whether the current repository matches this workflow or when the
chip family and OpenOCD target config are unclear.

## Workflow

1. Confirm that the project matches this skill:
   - Look for a top-level or generated `Makefile`.
   - Look for STM32 project directories such as `Core/`, `Drivers/`,
     `Middlewares/`, `usrlib/`, or CubeMX-generated startup and linker files.
   - If the project is clearly CubeIDE-only, PlatformIO-based, or CMake-based,
     do not force this workflow.

2. Inspect the local environment before changing files:
   - Check whether `openocd`, `stlink`, `clangd`, and an ARM GCC toolchain are
     already installed.
   - Check whether `.clangd` already exists and whether shell helpers are
     already defined elsewhere.
   - Prefer working with the repo's existing target family, include layout, and
     build outputs rather than overwriting them with generic defaults.

3. Apply the workflow components that are actually needed:
   - Use `scripts/makefile_parser.py` to scan a project root and print
     `C_SOURCES` and `C_INCLUDES` blocks for the `Makefile`.
   - Use `assets/clangd.txt` as a starting point for a project-root `.clangd`.
   - Use `assets/zshrc.txt` as a starting point for shell helpers such as
     `stm32flash` and `stm32run`.

4. Stop and surface the constraint when the environment does not match:
   - This workflow expects `gcc-arm-none-eabi` 12.3.
   - The bundled `zshrc.txt` targets `stm32f1x` with ST-Link by default.
   - The bundled `.clangd` contains placeholder STM32 include paths that may
     need to be adapted to the actual MCU family.

## Command Patterns

Run the Makefile parser from the STM32 project root:

```bash
python3 /path/to/stm32-macos-makefile/scripts/makefile_parser.py
```

Seed `.clangd` from the bundled template:

```bash
cp /path/to/stm32-macos-makefile/assets/clangd.txt .clangd
```

Append shell helpers to `~/.zshrc`:

```bash
cat /path/to/stm32-macos-makefile/assets/zshrc.txt >> ~/.zshrc
```

Replace `/path/to/stm32-macos-makefile/` with the real skill directory when
executing these commands outside `~/.codex/skills/`.

## Guardrails

- Do not claim the workflow is universal across all STM32 families.
- Do not rewrite an existing project `Makefile` blindly; inspect the current
  variable names and generated sections first.
- Do not replace a curated `.clangd` if the project already has one that is
  more specific than the template.
- Do not suggest newer ARM GNU toolchain versions as a drop-in replacement when
  the project is known to depend on 12.3 behavior.
- If the board family is not STM32F1, treat `assets/zshrc.txt` as a template
  that must be adjusted before recommending it unchanged.
