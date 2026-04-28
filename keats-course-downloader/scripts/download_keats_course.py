#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import mimetypes
import re
from http.cookies import SimpleCookie
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

import requests
from bs4 import BeautifulSoup


RESOURCE_SUFFIXES = (
    " File",
    " URL",
    " Page",
    " Folder",
    " External tool",
    " Forum",
    " Assignment",
    " Feedback",
    " Quiz",
)


def sanitize_name(value: str, limit: int = 140) -> str:
    value = re.sub(r"[\\/:*?\"<>|]", "_", value)
    value = re.sub(r"\s+", " ", value).strip().rstrip(".")
    return value[:limit] or "untitled"


def strip_activity_suffix(title: str) -> str:
    cleaned = re.sub(r"\s+", " ", title).strip()
    for suffix in RESOURCE_SUFFIXES:
        if cleaned.endswith(suffix):
            cleaned = cleaned[: -len(suffix)].rstrip()
    return cleaned


def apply_cookie_header(session: requests.Session, cookie_header: str, cookie_domain: str) -> None:
    parser = SimpleCookie()
    parser.load(cookie_header)
    for morsel in parser.values():
        session.cookies.set(morsel.key, morsel.value, domain=cookie_domain, path="/")


def cookie_header_from_auth_state(auth_state_path: Path, cookie_domain: str) -> str:
    state = json.loads(auth_state_path.read_text(encoding="utf-8"))
    cookies = []
    for cookie in state.get("cookies", []):
        domain = cookie.get("domain", "").lstrip(".")
        if domain == cookie_domain or domain.endswith(f".{cookie_domain}"):
            name = cookie.get("name")
            value = cookie.get("value")
            if name is not None and value is not None:
                cookies.append(f"{name}={value}")
    if not cookies:
        raise SystemExit(f"No cookies for {cookie_domain} found in {auth_state_path}.")
    return "; ".join(cookies)


def load_session(cookie_header: str, cookie_domain: str) -> requests.Session:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0 Safari/537.36",
        }
    )
    apply_cookie_header(session, cookie_header, cookie_domain)
    return session


def fetch_soup(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, timeout=60)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def looks_like_login_page(soup: BeautifulSoup) -> bool:
    text = " ".join(soup.get_text(" ", strip=True).split()).lower()
    return any(
        marker in text
        for marker in (
            "log in",
            "login",
            "sign in",
            "single sign-on",
            "microsoft",
            "saml",
        )
    )


def extract_activity_items(scope: BeautifulSoup) -> list[dict]:
    items = []
    for activity in scope.select(
        "li.activity, li.modtype_resource, li.modtype_url, li.modtype_page, "
        "li.modtype_folder, li.modtype_assign, li.modtype_lti, li.modtype_forum, "
        "li.modtype_feedback, li.modtype_quiz"
    ):
        link = activity.select_one("a.aalink[href], a[href]")
        if link is None:
            continue
        title = link.select_one(".instancename")
        raw_title = title.get_text(" ", strip=True) if title else link.get_text(" ", strip=True)
        classes = activity.get("class", [])
        items.append(
            {
                "title": strip_activity_suffix(raw_title),
                "url": link["href"],
                "classes": classes,
            }
        )
    return items


def parse_sections(course_soup: BeautifulSoup) -> list[dict]:
    sections: list[dict] = []
    seen: set[tuple[str, str | None]] = set()

    for section in course_soup.select("li.section.course-section"):
        heading_el = section.select_one("h3.sectionname")
        if heading_el is None:
            continue
        heading = " ".join(heading_el.get_text(" ", strip=True).split())
        items = extract_activity_items(section)
        if items:
            key = (heading, None)
            if key not in seen:
                sections.append({"heading": heading, "items": items, "section_url": None})
                seen.add(key)

    for card in course_soup.select("div.grid-section.card a.grid-section-inner[href]"):
        heading_el = card.select_one("h3")
        heading = " ".join((heading_el.get_text(" ", strip=True) if heading_el else card.get("title", "")).split())
        section_url = card.get("href")
        if not heading or not section_url:
            continue
        key = (heading, section_url)
        if key not in seen:
            sections.append({"heading": heading, "items": [], "section_url": section_url})
            seen.add(key)

    return sections


def detect_kind(classes: Iterable[str], url: str) -> str:
    class_set = set(classes)
    if "modtype_resource" in class_set or "/mod/resource/" in url:
        return "resource"
    if "modtype_url" in class_set or "/mod/url/" in url:
        return "url"
    if "modtype_page" in class_set or "/mod/page/" in url:
        return "page"
    if "modtype_folder" in class_set or "/mod/folder/" in url:
        return "folder"
    return "link"


def filename_from_response(response: requests.Response, fallback_url: str, fallback_stem: str) -> str:
    disposition = response.headers.get("content-disposition", "")
    filename = None
    match = re.search(r"filename\\*=UTF-8''([^;]+)", disposition)
    if match:
        filename = unquote(match.group(1))
    if filename is None:
        match = re.search(r'filename="?([^";]+)"?', disposition)
        if match:
            filename = match.group(1)
    if filename is None:
        path_name = Path(unquote(urlparse(fallback_url).path)).name
        if path_name.lower() in {"view.php", "download.php", ""}:
            filename = sanitize_name(fallback_stem)
        else:
            filename = path_name
    if "." not in filename:
        ext = mimetypes.guess_extension((response.headers.get("content-type") or "").split(";")[0].strip())
        if ext:
            filename += ext
    return sanitize_name(filename, limit=200)


def write_text(path: Path, content: str) -> None:
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def download_resource(session: requests.Session, item: dict, target_dir: Path) -> list[str]:
    view_response = session.get(item["url"], timeout=60)
    view_response.raise_for_status()
    content_type = (view_response.headers.get("content-type") or "").split(";")[0].strip().lower()
    if content_type and content_type not in {"text/html", "application/xhtml+xml"}:
        filename = filename_from_response(view_response, view_response.url, item["title"])
        path = target_dir / filename
        path.write_bytes(view_response.content)
        return [path.name]

    soup = BeautifulSoup(view_response.text, "html.parser")

    plugin_links = []
    for anchor in soup.select("a[href]"):
        href = anchor.get("href", "")
        if "pluginfile.php" in href:
            plugin_links.append(href)
    plugin_links = list(dict.fromkeys(plugin_links))

    if not plugin_links:
        html_path = target_dir / f"{sanitize_name(item['title'])}.html"
        html_path.write_text(view_response.text, encoding="utf-8")
        return [html_path.name]

    saved = []
    for index, download_url in enumerate(plugin_links, start=1):
        response = session.get(download_url, timeout=120)
        response.raise_for_status()
        filename = filename_from_response(response, response.url, item["title"])
        if len(plugin_links) > 1 and filename == sanitize_name(item["title"]):
            filename = f"{sanitize_name(item['title'])}_{index}"
        path = target_dir / filename
        path.write_bytes(response.content)
        saved.append(path.name)
    return saved


def resolve_url_target(session: requests.Session, item_url: str) -> str:
    response = session.get(item_url, timeout=60)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    candidates = []
    for anchor in soup.select("a[href]"):
        href = (anchor.get("href") or "").strip()
        if not href or href.startswith("#"):
            continue
        text = " ".join(anchor.get_text(" ", strip=True).split())
        if href.startswith("https://keats.kcl.ac.uk/") or href.startswith("/"):
            continue
        candidates.append((text, href))

    if candidates:
        return candidates[-1][1]
    return item_url


def save_url_item(session: requests.Session, item: dict, target_dir: Path) -> list[str]:
    target = resolve_url_target(session, item["url"])
    path = target_dir / f"{sanitize_name(item['title'])}.url.txt"
    write_text(path, target)
    return [path.name]


def save_page_item(session: requests.Session, item: dict, target_dir: Path) -> list[str]:
    response = session.get(item["url"], timeout=60)
    response.raise_for_status()
    path = target_dir / f"{sanitize_name(item['title'])}.html"
    path.write_text(response.text, encoding="utf-8")
    return [path.name]


def save_generic_link(item: dict, target_dir: Path) -> list[str]:
    path = target_dir / f"{sanitize_name(item['title'])}.link.txt"
    write_text(path, item["url"])
    return [path.name]


def download_sections(session: requests.Session, course_url: str, output_dir: Path) -> dict:
    course_soup = fetch_soup(session, course_url)
    sections = parse_sections(course_soup)
    if not sections and looks_like_login_page(course_soup):
        raise SystemExit("No course sections found. The KEATS auth state or cookies appear to be expired.")
    manifest = {"course_url": course_url, "sections": []}

    for section in sections:
        section_dir = output_dir / sanitize_name(section["heading"])
        section_dir.mkdir(parents=True, exist_ok=True)
        section_manifest = {"heading": section["heading"], "directory": str(section_dir), "items": []}

        items = section["items"]
        if not items and section.get("section_url"):
            items = extract_activity_items(fetch_soup(session, section["section_url"]))

        if not items:
            continue

        for item in items:
            kind = detect_kind(item["classes"], item["url"])
            if kind == "resource":
                files = download_resource(session, item, section_dir)
            elif kind == "url":
                files = save_url_item(session, item, section_dir)
            elif kind == "page":
                files = save_page_item(session, item, section_dir)
            else:
                files = save_generic_link(item, section_dir)

            section_manifest["items"].append(
                {
                    "title": item["title"],
                    "kind": kind,
                    "source_url": item["url"],
                    "saved_files": files,
                }
            )

        manifest["sections"].append(section_manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Download KEATS course content grouped by week.")
    parser.add_argument("--cookie-header")
    parser.add_argument("--cookie-file", type=Path)
    parser.add_argument("--auth-state", type=Path, help="Playwright storage_state JSON containing KEATS cookies.")
    parser.add_argument("--cookie-domain", default="keats.kcl.ac.uk")
    parser.add_argument("--course-url", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    cookie_header = args.cookie_header
    if args.auth_state is not None:
        cookie_header = cookie_header_from_auth_state(args.auth_state, args.cookie_domain)
    if args.cookie_file is not None:
        cookie_header = args.cookie_file.read_text(encoding="utf-8").strip()
    if not cookie_header:
        raise SystemExit("Provide --cookie-header, --cookie-file, or --auth-state.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    session = load_session(cookie_header, args.cookie_domain)
    manifest = download_sections(session, args.course_url, args.output_dir)

    manifest_path = args.output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    summary_lines = []
    for section in manifest["sections"]:
        summary_lines.append(f"{section['heading']}: {len(section['items'])} items")
    write_text(args.output_dir / "README.txt", "\n".join(summary_lines))


if __name__ == "__main__":
    main()
