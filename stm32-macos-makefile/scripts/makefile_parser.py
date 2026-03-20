import os


def install_tools():
    """Print the Homebrew command for the CLI tools used by this workflow."""
    tools = [
        "tree",
        "bear",
        "make",
        "openocd",
        "stlink",
        "uv",
        "python",
    ]
    print("Copy and paste the following command to install the tools:\n")
    print("brew install " + " ".join(tools))


def find_files_and_dirs(
    root_dir, ignore_dirs=("build", ".git", ".vscode", ".idea")
):
    """
    Scan the project root and collect:
    1. All .c files for C_SOURCES
    2. All directories that contain .h files for C_INCLUDES
    """
    c_sources = []
    inc_dirs = set()

    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in ignore_dirs and not d.startswith(".")]

        rel_dir = os.path.relpath(dirpath, root_dir)
        if rel_dir == ".":
            rel_dir = ""

        for filename in filenames:
            if filename.endswith(".c"):
                path = os.path.join(rel_dir, filename) if rel_dir else filename
                c_sources.append(path)
            elif filename.endswith(".h"):
                inc_dirs.add(rel_dir if rel_dir else ".")

    return sorted(c_sources), sorted(inc_dirs)


def format_makefile_var(var_name, items, prefix=""):
    """Render a Makefile variable block with line continuations."""
    if not items:
        return f"{var_name} = \n"

    lines = [f"{var_name} =  \\"]
    for index, item in enumerate(items):
        suffix = "" if index == len(items) - 1 else " \\"
        lines.append(f"{prefix}{item}{suffix}")
    return "\n".join(lines)


def main():
    root_dir = os.getcwd()
    print(f"Scanning directory: {root_dir} ...\n")

    c_sources, inc_dirs = find_files_and_dirs(root_dir)

    print("-" * 40)
    print("COPY THE CONTENT BELOW INTO YOUR MAKEFILE")
    print("-" * 40)
    print()

    print("#######################################")
    print("# source")
    print("#######################################")
    print("# C sources")
    print(format_makefile_var("C_SOURCES", c_sources))
    print()

    print("#######################################")
    print("# C includes")
    print("#######################################")
    print(format_makefile_var("C_INCLUDES", inc_dirs, prefix="-I"))
    print()
    print("-" * 40)


if __name__ == "__main__":
    install_tools()
    main()
