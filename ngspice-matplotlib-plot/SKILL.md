---
name: ngspice-matplotlib-plot
description: Use when the task is to run an ngspice .cir netlist from the command line and generate waveform plots with matplotlib. Trigger on requests to simulate SPICE files, run ngspice automatically, plot wrdata output, or turn .cir files into waveform images.
---

# ngspice Matplotlib Plot

Use this skill when a task needs to run `ngspice` on a `.cir` file and turn the generated `wrdata` output into a plot.

## Environment Requirements

- A Python environment with `matplotlib` installed.
- `ngspice` installed and callable as `ngspice`.
- The bundled script writes matplotlib config and cache data into the current working directory if needed.
- Prefer a project-local `.venv` when one exists.
- If no project-local environment exists, use a Python interpreter explicitly instead of assuming `python` resolves correctly.
- Before invoking Python plotting, it is safe to set:
  ```bash
  MPLCONFIGDIR="$(pwd)/.mplconfig"
  XDG_CACHE_HOME="$(pwd)/.cache"
  ```

## Default Workflow

1. Confirm the `.cir` file contains a `wrdata ...` line.
2. Choose a Python interpreter:
   - Prefer `./.venv/bin/python` if the repo already has one.
   - Otherwise use an explicitly chosen interpreter such as `python3`.
3. Run the bundled script with that interpreter.
4. By default, let the script delete the generated `.dat` file after plotting.
5. Use `--keep-data` only when the user wants to inspect or reuse the raw exported data.

## Command Pattern

```bash
MPLCONFIGDIR="$(pwd)/.mplconfig" \
XDG_CACHE_HOME="$(pwd)/.cache" \
python3 \
~/.codex/skills/ngspice-matplotlib-plot/scripts/run_ngspice_and_plot.py \
<path-to-netlist.cir> [--output output.png] [--title "Plot Title"] [--keep-data]
```

## Notes

- The script expects `wrdata` output in the netlist. It parses the file name and expressions from that command.
- The generated image defaults to `<netlist_stem>_plot.png` in the same directory as the netlist.
- The bundled script uses the non-interactive `Agg` matplotlib backend, so it works in headless terminal sessions.
- If a collaborator stores skills somewhere other than `~/.codex/skills/`, adjust the script path accordingly.
