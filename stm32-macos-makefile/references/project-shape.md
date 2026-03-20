# STM32 Makefile Project Shape

Use this reference when you need to decide whether the repository should use
the `stm32-macos-makefile` workflow and how much of the bundled template can be
applied directly.

## Good Matches

This skill is a good fit when the repository contains most of these signals:

- a `Makefile` that defines `C_SOURCES`, `C_INCLUDES`, linker flags, or ARM GCC
  variables;
- STM32-specific folders such as `Core/`, `Drivers/`, `Middlewares/`, `USB_*`,
  or `usrlib/`;
- startup files like `startup_stm32*.s`;
- linker scripts like `STM32*.ld`;
- build outputs under `build/`.

## Partial Matches

These cases can still use parts of the skill:

- The repo already builds, but `clangd` is missing or broken.
- The repo already has a Makefile, but source/include lists are incomplete.
- The repo already flashes with a custom OpenOCD config, so only the parser or
  `.clangd` template should be reused.

## Bad Matches

Do not force this skill onto repositories that are primarily:

- STM32CubeIDE-managed without a Makefile workflow;
- PlatformIO-based;
- CMake-based;
- non-STM32 embedded projects.

## Family-Specific Caveat

The bundled shell helper uses:

```bash
-f interface/stlink.cfg -f target/stm32f1x.cfg
```

Treat that as an example, not a universal default. Before recommending the
helper unchanged, inspect the actual MCU family from:

- project names;
- linker scripts;
- startup assembly filenames;
- `Drivers/CMSIS/Device/ST/...`;
- CubeMX `.ioc` files, when present.

If the family differs, update the OpenOCD target script accordingly.
