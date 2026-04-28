---
name: keats-course-downloader
description: Use when the user wants to download a KEATS course from a course URL plus a browser cookie file or Playwright auth-state JSON, organize materials into section-based folders such as Week or Topic, or avoid manually copying KEATS/Moodle cookies.
---

# KEATS Course Downloader

Use this skill when a user provides a KEATS course URL and either a cookie file or a Playwright auth-state JSON file, and wants the course content downloaded locally into per-section folders.

## Quick Start

The bundled one-command entrypoint accepts either a raw cookie file or a Playwright `auth-state.json` file.

Cookie-file mode:

```bash
"$HOME/.codex/skills/keats-course-downloader/scripts/download-keats-course.sh" \
  "https://keats.kcl.ac.uk/course/view.php?id=134598" \
  "/absolute/path/to/cookies.txt"
```

Auth-state mode:

```bash
"$HOME/.codex/skills/keats-course-downloader/scripts/download-keats-course.sh" \
  "https://keats.kcl.ac.uk/course/view.php?id=134598" \
  --auth-state "/absolute/path/to/auth-state.json"
```

Optional third argument overrides the output directory:

```bash
"$HOME/.codex/skills/keats-course-downloader/scripts/download-keats-course.sh" \
  "https://keats.kcl.ac.uk/course/view.php?id=134598" \
  "/absolute/path/to/cookies.txt" \
  "/absolute/path/to/output"
```

For auth-state mode, the output directory is the optional fourth argument:

```bash
"$HOME/.codex/skills/keats-course-downloader/scripts/download-keats-course.sh" \
  "https://keats.kcl.ac.uk/course/view.php?id=134598" \
  --auth-state "/absolute/path/to/auth-state.json" \
  "/absolute/path/to/output"
```

## Cookie File Format

The cookie file must contain a single raw `Cookie` header string, for example:

```text
MoodleSession=abc123; other_cookie=value; another_cookie=value2
```

Do not ask the user to paste sensitive cookies into chat if a local file path will do.

## Auth State Format

`auth-state.json` should be a Playwright `storage_state` JSON file containing a top-level `cookies` array. The downloader extracts cookies for `keats.kcl.ac.uk` and builds the request session automatically.

Use browser automation to help the user reach the KEATS course page and complete SSO/MFA interactively, then prefer a saved Playwright auth state over asking the user to manually copy cookies.

To capture or refresh an auth state interactively:

```bash
"$HOME/.codex/skills/keats-course-downloader/scripts/capture-keats-auth-state.sh" \
  "https://keats.kcl.ac.uk/course/view.php?id=134598" \
  "/absolute/path/to/auth-state.json"
```

This opens a headed browser. The user completes KEATS SSO/MFA manually, then returns to the terminal and presses Enter after the course page is visible.

## Dependencies

Run Python through `uv`; do not ask the user to install packages manually unless `uv` itself is unavailable.

The download wrapper uses:

```bash
uv run --with requests --with beautifulsoup4 python scripts/download_keats_course.py
```

The auth-state capture wrapper uses:

```bash
uv run --with playwright python scripts/capture_keats_auth_state.py
```

If Playwright is not already cached, `uv` may download the Python package on first run. The capture flow requires a headed browser because the user must complete KEATS SSO/MFA manually.

If running directly from a cloned copy of this repository before installing the skill, replace `$HOME/.codex/skills/keats-course-downloader` with the local `keats-course-downloader` directory.

## Workflow

1. Confirm the course URL and either a cookie file path or an auth-state file path.
2. If no valid auth-state or cookie file exists, run `scripts/capture-keats-auth-state.sh`.
3. Run `scripts/download-keats-course.sh`.
4. Check the generated `manifest.json` and section directories.
5. If the download fails with login or redirect issues, assume the cookies are expired or incomplete and ask the user to refresh auth state.

## Behavior

The bundled Python script:

- fetches the course page with the provided cookies
- parses course sections such as `Week`, `Topic`, or other section headings that contain resources
- downloads file resources into per-section folders
- resolves KEATS `URL` activities and stores the final external link in `.url.txt`
- writes `manifest.json` and `README.txt` into the output directory

## Files

- Wrapper: `scripts/download-keats-course.sh`
- Downloader: `scripts/download_keats_course.py`
- Auth-state capture wrapper: `scripts/capture-keats-auth-state.sh`
- Auth-state capture script: `scripts/capture_keats_auth_state.py`

Prefer the wrapper unless you need to change Python-level flags directly.
