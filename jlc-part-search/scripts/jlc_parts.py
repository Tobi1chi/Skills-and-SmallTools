#!/usr/bin/env python3
"""Search JLC/LCSC parts with a mandatory filter/detail two-stage protocol."""

from __future__ import annotations

import argparse
import hashlib
import html
import hmac
import json
import os
import random
import re
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

JLCPCB_BASE = "https://jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood"
JLCPCB_SEARCH = f"{JLCPCB_BASE}/selectSmtComponentList/v2"
EASYEDA_COMPONENT = "https://easyeda.com/api/products/{lcsc}/components?version=6.4.19.5"
LCSC_SEARCH = "https://ips.lcsc.com/rest/wmsc2agent/search/product"
SZLCSC_SEARCH = "https://so.szlcsc.com/global.html?k={query}"
SZLCSC_ITEM = "https://item.szlcsc.com/{product_id}.html"

LCSC_RE = re.compile(r"^C\d+$", re.I)
PACKAGE_RE = re.compile(
    r"\b(?:0[2468]0[1256]|1206|1210|1812|2010|2512|SOT-?23(?:-?\d+)?|SOT-?223|"
    r"SOP-?\d+|SSOP-?\d+|TSSOP-?\d+|QFN-?\d+|QFP-?\d+|LQFP-?\d+|DFN-?\d+|"
    r"DIP-?\d+|TO-?220|TO-?252|DO-?214|SMA|SMB|SMC)\b",
    re.I,
)
ELECTRICAL_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:ohm|Ω|r|k|m|v|kv|a|ma|ua|µa|w|mw|uf|µf|nf|pf|mh|uh|µh|hz|khz|mhz|%)\b",
    re.I,
)
PREFERRED_WORDS = {
    "basic": "basic library",
    "基础库": "basic library",
    "extended": "extended library",
    "扩展库": "extended library",
    "stock": "high stock",
    "库存": "high stock",
    "cheap": "low price",
    "低价": "low price",
    "smt": "smt assembly",
    "贴片": "smt assembly",
}


def die(message: str, code: int = 2) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def http_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 25,
) -> Any:
    body = None
    req_headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "User-Agent": "jlc-part-search/1.0",
    }
    if headers:
        req_headers.update(headers)
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req_headers["Content-Type"] = "application/json;charset=UTF-8"
    req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {"_error": str(exc), "_url": url}


def http_text(url: str, headers: dict[str, str] | None = None, timeout: int = 25) -> str | dict[str, str]:
    req_headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
        "User-Agent": "jlc-part-search/1.0",
    }
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        return {"_error": str(exc), "_url": url}


def first_file_url(groups: Any, file_type: str) -> str:
    if not isinstance(groups, list):
        return ""
    for group in groups:
        if not isinstance(group, dict) or group.get("fileType") != file_type:
            continue
        details = group.get("detailVOList")
        if not isinstance(details, list):
            continue
        for detail in details:
            if not isinstance(detail, dict):
                continue
            url = str(detail.get("fileUrl") or detail.get("linkAddress") or "")
            if url:
                return "https://atta.szlcsc.com" + url if url.startswith("/") else url
    return ""


def parse_next_data(text: str) -> dict[str, Any]:
    match = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', text, re.S)
    if not match:
        return {}
    try:
        return json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError:
        return {}


def canonicalize_product(raw: dict[str, Any], source: str) -> dict[str, Any]:
    attrs = raw.get("attributes") or raw.get("componentAttributes") or []
    package = raw.get("componentSpecificationEn") or raw.get("package") or raw.get("encapsulation") or ""
    params: dict[str, Any] = {}
    if isinstance(attrs, list):
        for attr in attrs:
            if not isinstance(attr, dict):
                continue
            name = str(attr.get("attributeName") or attr.get("name") or "").strip()
            value = str(attr.get("attributeValue") or attr.get("value") or "").strip()
            if name and value:
                params[name] = value
            if not package and name.lower() in {"package", "封装"}:
                package = value
    return {
        "source": source,
        "lcsc": raw.get("componentCode") or raw.get("lcsc_part_number") or raw.get("productNumber") or raw.get("product_number") or "",
        "mpn": raw.get("componentModelEn") or raw.get("componentModel") or raw.get("productModel") or raw.get("mpn") or "",
        "manufacturer": raw.get("componentBrandEn") or raw.get("componentBrand") or raw.get("brandName") or raw.get("manufacturer") or "",
        "description": raw.get("componentName") or raw.get("describe") or raw.get("Describe") or raw.get("productIntroEn") or "",
        "package": package,
        "stock": raw.get("stockCount") or raw.get("stock") or raw.get("quantity") or "",
        "library_type": raw.get("componentTypeEn") or raw.get("componentLibraryType") or "",
        "datasheet_pdf": raw.get("dataManualUrl") or raw.get("datasheet") or "",
        "product_url": raw.get("lcscGoodsUrl") or raw.get("goodsUrl") or "",
        "category": raw.get("category") or raw.get("firstSortName") or "",
        "parameters": params,
    }


def canonicalize_szlcsc_product(record: dict[str, Any]) -> dict[str, Any]:
    product = record.get("productVO") if isinstance(record.get("productVO"), dict) else record
    product_id = str(product.get("productId") or "")
    param_map = record.get("paramLinkedMap") if isinstance(record.get("paramLinkedMap"), dict) else {}
    description_parts = [str(product.get("productName") or ""), str(product.get("remark") or "")]
    if param_map:
        description_parts.append(" ".join(f"{key}:{value}" for key, value in param_map.items()))
    stock = product.get("stockNumber")
    if stock in (None, ""):
        stock = record.get("totalStockNumber")
    return {
        "source": "szlcsc-public",
        "lcsc": product.get("productCode") or "",
        "mpn": product.get("productModel") or "",
        "manufacturer": product.get("productGradePlateName") or record.get("lightBrandName") or "",
        "description": " | ".join(part for part in description_parts if part),
        "package": product.get("encapsulationModel") or record.get("lightStandard") or "",
        "stock": stock if stock is not None else "",
        "library_type": product.get("smtLabel") or "",
        "datasheet_pdf": first_file_url(product.get("fileTypeVOList") or [], "pdf_property"),
        "product_url": SZLCSC_ITEM.format(product_id=product_id) if product_id else "",
        "product_id": product_id,
        "category": product.get("productType") or record.get("lightCatalogName") or "",
        "parameters": param_map,
    }


def search_szlcsc(query: str, page_size: int = 20) -> list[dict[str, Any]]:
    url = SZLCSC_SEARCH.format(query=urllib.parse.quote(query))
    text = http_text(url)
    if isinstance(text, dict) and text.get("_error"):
        return [{"source": "szlcsc-public", "error": text["_error"], "url": url}]
    data = parse_next_data(str(text))
    page_props = ((data.get("props") or {}).get("pageProps") or {}) if isinstance(data, dict) else {}
    records = (((page_props.get("soData") or {}).get("searchResult") or {}).get("productRecordList") or [])
    return [canonicalize_szlcsc_product(item) for item in records if isinstance(item, dict)][:page_size]


def search_jlcpcb(query: str, page_size: int = 20) -> list[dict[str, Any]]:
    payload = {
        "keyword": query,
        "currentPage": 1,
        "pageSize": min(max(page_size, 1), 100),
        "presaleType": "",
        "searchType": 2,
        "componentLibraryType": None,
        "componentAttributeList": [],
        "componentBrandList": [],
        "componentSpecificationList": [],
        "paramList": [],
        "firstSortName": None,
        "secondSortName": None,
        "searchSource": "search",
        "stockFlag": False,
    }
    data = http_json("POST", JLCPCB_SEARCH, payload)
    if isinstance(data, dict) and data.get("_error"):
        return [{"source": "jlcpcb-public", "error": data["_error"]}]
    products = (((data or {}).get("data") or {}).get("componentPageInfo") or {}).get("list") or []
    return [canonicalize_product(item, "jlcpcb-public") for item in products]


def lcsc_signature(params: dict[str, str], secret: str) -> str:
    base = "&".join(f"{k}={params[k]}" for k in sorted(params) if k != "signature")
    return hmac.new(secret.encode("utf-8"), base.encode("utf-8"), hashlib.sha256).hexdigest()


def search_lcsc_official(query: str, page_size: int = 20) -> list[dict[str, Any]]:
    key = os.environ.get("LCSC_API_KEY")
    secret = os.environ.get("LCSC_API_SECRET")
    if not key or not secret:
        return []
    nonce = "".join(random.choice(string.ascii_letters + string.digits) for _ in range(16))
    params = {
        "key": key,
        "nonce": nonce,
        "timestamp": str(int(time.time() * 1000)),
        "keyword": query,
        "current_page": "1",
        "page_size": str(min(max(page_size, 1), 30)),
        "match_type": "exact" if not LCSC_RE.match(query) else "fuzzy",
        "currency": os.environ.get("LCSC_API_CURRENCY", "CNY"),
    }
    params["signature"] = lcsc_signature(params, secret)
    data = http_json("GET", f"{LCSC_SEARCH}?{urllib.parse.urlencode(params)}")
    if isinstance(data, dict) and data.get("_error"):
        return [{"source": "lcsc-official", "error": data["_error"]}]
    candidates = []
    for key_name in ("data", "result", "list", "rows"):
        value = data.get(key_name) if isinstance(data, dict) else None
        if isinstance(value, list):
            candidates = value
            break
        if isinstance(value, dict):
            for sub in ("list", "rows", "content"):
                if isinstance(value.get(sub), list):
                    candidates = value[sub]
                    break
    return [canonicalize_product(item, "lcsc-official") for item in candidates]


def usable_candidates(candidates: list[dict[str, Any]]) -> bool:
    return any(item.get("lcsc") and not item.get("error") for item in candidates)


def dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in candidates:
        key = str(item.get("lcsc") or item.get("product_url") or item.get("mpn") or json.dumps(item, sort_keys=True, ensure_ascii=False))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def collect_candidates(query: str, page_size: int, source: str) -> list[dict[str, Any]]:
    if source == "szlcsc":
        return search_szlcsc(query, page_size)
    if source == "jlcpcb":
        return search_jlcpcb(query, page_size)
    if source == "lcsc":
        return search_lcsc_official(query, page_size)
    if source == "auto":
        results = search_szlcsc(query, page_size=page_size)
        if not usable_candidates(results):
            results.extend(search_jlcpcb(query, page_size=page_size))
            results.extend(search_lcsc_official(query, page_size=page_size))
        return dedupe_candidates(results)[:page_size]
    die(f"unknown source: {source}")


def fetch_easyeda(lcsc: str) -> dict[str, Any]:
    if not LCSC_RE.match(lcsc or ""):
        return {}
    data = http_json("GET", EASYEDA_COMPONENT.format(lcsc=lcsc.upper()))
    if isinstance(data, dict) and data.get("_error"):
        return {"error": data["_error"]}
    result = data.get("result") if isinstance(data, dict) else None
    if not isinstance(result, dict):
        return {"error": "missing EasyEDA result"}
    info = {"symbol_uuid": str(result.get("uuid") or ""), "symbol_title": str(result.get("title") or "")}
    package_detail = result.get("packageDetail") if isinstance(result.get("packageDetail"), dict) else {}
    if package_detail:
        info["footprint_uuid"] = str(package_detail.get("uuid") or "")
        info["footprint_name"] = str(package_detail.get("title") or "")
    for key in ("package", "Package", "footprint", "footprintName", "packageName", "title", "name"):
        value = find_key_recursive(result, key)
        if value:
            info.setdefault(key, value)
    return info


def find_key_recursive(obj: Any, wanted: str) -> str:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key) == wanted and isinstance(value, (str, int, float)):
                return str(value)
        for value in obj.values():
            found = find_key_recursive(value, wanted)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = find_key_recursive(item, wanted)
            if found:
                return found
    return ""


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def candidate_text(candidate: dict[str, Any]) -> str:
    parts = [
        candidate.get("lcsc", ""),
        candidate.get("mpn", ""),
        candidate.get("manufacturer", ""),
        candidate.get("description", ""),
        candidate.get("package", ""),
        candidate.get("category", ""),
        candidate.get("library_type", ""),
    ]
    params = candidate.get("parameters")
    if isinstance(params, dict):
        parts.extend(f"{key}:{value}" for key, value in params.items())
    return normalize_text(" ".join(str(part) for part in parts))


def extract_constraints(query: str) -> tuple[list[str], list[str]]:
    required: list[str] = []
    preferred: list[str] = []
    for match in PACKAGE_RE.finditer(query):
        required.append(match.group(0).upper())
    for match in ELECTRICAL_RE.finditer(query):
        token = re.sub(r"\s+", "", match.group(0)).lower()
        if token not in [item.lower() for item in required]:
            required.append(token)
    lowered = query.lower()
    for word, label in PREFERRED_WORDS.items():
        if word.lower() in lowered and label not in preferred:
            preferred.append(label)
    if not required:
        required = [query.strip()]
    return required, preferred


def score_filter_candidate(candidate: dict[str, Any], required: list[str], preferred: list[str]) -> dict[str, Any]:
    text = candidate_text(candidate)
    package = normalize_text(candidate.get("package"))
    matched: list[str] = []
    uncertain: list[str] = []
    failed: list[str] = []
    score = 0.15 if candidate.get("lcsc") else 0.0
    for constraint in required:
        normalized = normalize_text(constraint).replace(" ", "")
        if PACKAGE_RE.fullmatch(constraint) and normalized not in package.replace(" ", "").replace("-", ""):
            failed.append(constraint)
            score -= 0.30
        elif normalized and normalized in text.replace(" ", "").replace("-", ""):
            matched.append(constraint)
            score += 0.20
        else:
            uncertain.append(constraint)
            score -= 0.03
    if candidate.get("stock") not in ("", 0, "0", None):
        score += 0.08
    if candidate.get("datasheet_pdf"):
        score += 0.05
    if preferred:
        pref_text = " ".join(preferred).lower()
        if "basic" in pref_text and "基础" in str(candidate.get("library_type")):
            score += 0.08
        if "smt" in pref_text and candidate.get("library_type"):
            score += 0.05
    return {
        "score": max(0.0, min(1.0, score)),
        "matched_constraints": matched,
        "uncertain_constraints": uncertain,
        "failed_constraints": failed,
    }


def filter_output(query: str, candidates: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    required, preferred = extract_constraints(query)
    rows = []
    for candidate in candidates:
        if candidate.get("error"):
            continue
        scoring = score_filter_candidate(candidate, required, preferred)
        rows.append({**candidate, **scoring})
    rows.sort(key=lambda item: (not item.get("failed_constraints"), item.get("score", 0)), reverse=True)
    formatted = [format_filter_candidate(idx + 1, item) for idx, item in enumerate(rows[:limit])]
    if not formatted:
        status = "no_catalog_match"
    elif any(not item["failed_constraints"] for item in formatted):
        status = "candidates"
    else:
        status = "no_verified_candidates"
    return {
        "stage": "filter",
        "status": status,
        "query": query,
        "required_constraints": required,
        "preferred_constraints": preferred,
        "candidates": formatted,
        "next_required_action": "run_detail_for_one_candidate" if formatted else "revise_query_or_try_other_sources",
        "availability_note": "Catalog candidates are availability evidence only, not proof of design suitability.",
    }


def format_filter_candidate(rank: int, item: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": rank,
        "lcsc": item.get("lcsc", ""),
        "mpn": item.get("mpn", ""),
        "manufacturer": item.get("manufacturer", ""),
        "package": item.get("package", ""),
        "summary": item.get("description", ""),
        "stock": item.get("stock", ""),
        "library_type": item.get("library_type", ""),
        "product_url": item.get("product_url", ""),
        "datasheet_pdf": item.get("datasheet_pdf", ""),
        "score": round(float(item.get("score", 0.0)), 3),
        "matched_constraints": item.get("matched_constraints", []),
        "uncertain_constraints": item.get("uncertain_constraints", []),
        "failed_constraints": item.get("failed_constraints", []),
        "evidence_source": item.get("source", ""),
    }


def exact_identifier_matches(identifier: str, source: str, limit: int) -> list[dict[str, Any]]:
    candidates = collect_candidates(identifier, page_size=max(limit, 10), source=source)
    ident = identifier.strip().lower()
    if LCSC_RE.match(identifier):
        exact = [item for item in candidates if str(item.get("lcsc", "")).lower() == ident]
        return exact or []
    exact = [item for item in candidates if normalize_text(item.get("mpn")) == normalize_text(identifier)]
    return exact


def detail_payload(identifier: str, source: str, limit: int, include_enet: bool) -> dict[str, Any]:
    matches = exact_identifier_matches(identifier, source, limit)
    if not matches:
        return {
            "stage": "enet" if include_enet else "detail",
            "status": "no_catalog_match",
            "identifier": identifier,
            "availability_note": "No exact catalog match was found. This is not proof that the design requirement is impossible.",
        }
    deduped = dedupe_candidates(matches)
    if len(deduped) > 1:
        return {
            "stage": "enet" if include_enet else "detail",
            "status": "ambiguous_identifier",
            "identifier": identifier,
            "candidates": [format_filter_candidate(idx + 1, {**item, "score": 0.0}) for idx, item in enumerate(deduped[:limit])],
            "next_required_action": "choose_one_lcsc_code",
        }
    part = deduped[0]
    easyeda = fetch_easyeda(str(part.get("lcsc", ""))) if part.get("lcsc") else {}
    if include_enet:
        return format_enet_detail(part, easyeda)
    return format_detail(part, easyeda)


def format_detail(part: dict[str, Any], easyeda: dict[str, Any]) -> dict[str, Any]:
    return {
        "stage": "detail",
        "status": "detail",
        "lcsc": part.get("lcsc", ""),
        "mpn": part.get("mpn", ""),
        "manufacturer": part.get("manufacturer", ""),
        "package": part.get("package", ""),
        "description": part.get("description", ""),
        "category": part.get("category", ""),
        "stock": part.get("stock", ""),
        "library_type": part.get("library_type", ""),
        "datasheet_pdf": part.get("datasheet_pdf", ""),
        "product_url": part.get("product_url", ""),
        "parameters": part.get("parameters", {}),
        "easyeda": easyeda,
        "verification": {
            "hard_constraints_verified": [],
            "hard_constraints_unverified": ["No design requirements are verified in detail mode unless checked by the caller."],
            "notes": ["This is an exact-part fact lookup, not a circuit design validation."],
        },
    }


def format_enet_detail(part: dict[str, Any], easyeda: dict[str, Any]) -> dict[str, Any]:
    footprint_name = (
        easyeda.get("footprint_name")
        or easyeda.get("package")
        or easyeda.get("footprintName")
        or easyeda.get("packageName")
        or part.get("package", "")
    )
    footprint_uuid = easyeda.get("footprint_uuid") or easyeda.get("footprintUuid") or easyeda.get("packageUuid") or ""
    return {
        "stage": "enet",
        "status": "enet_fields",
        "selected": {
            "lcsc": part.get("lcsc", ""),
            "mpn": part.get("mpn", ""),
            "manufacturer": part.get("manufacturer", ""),
            "package": part.get("package", ""),
        },
        "enet_fields": {
            "LCSC": part.get("lcsc", ""),
            "MPN": part.get("mpn", ""),
            "Manufacturer": part.get("manufacturer", ""),
            "Package": part.get("package", ""),
            "footprintName": footprint_name,
            "footprintUuid": footprint_uuid,
        },
        "easyeda": easyeda,
        "evidence": {
            "product_url": part.get("product_url", ""),
            "datasheet_pdf": part.get("datasheet_pdf", ""),
            "source": part.get("source", ""),
        },
        "file_write_note": "No .enet file was created or modified.",
    }


def command_filter(args: argparse.Namespace) -> None:
    candidates = collect_candidates(args.query, page_size=max(args.limit * 2, args.limit), source=args.source)
    print_json(filter_output(args.query, candidates, args.limit))


def command_detail(args: argparse.Namespace, include_enet: bool = False) -> None:
    print_json(detail_payload(args.identifier, args.source, args.limit, include_enet=include_enet))


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def self_test() -> None:
    record = {
        "productVO": {
            "productId": "123",
            "productCode": "C25804",
            "productModel": "RC0402FR-0710KL",
            "productGradePlateName": "YAGEO",
            "productName": "Chip Resistor",
            "encapsulationModel": "0402",
            "stockNumber": 1000,
            "smtLabel": "基础库",
        },
        "paramLinkedMap": {"Resistance": "10k", "Tolerance": "1%"},
    }
    part = canonicalize_szlcsc_product(record)
    payload = filter_output("10k 1% 0402 resistor", [part], 10)
    assert payload["stage"] == "filter"
    assert "selected" not in payload
    assert "enet_fields" not in payload
    detail = format_detail(part, {"symbol_uuid": "sym", "footprint_uuid": "pkg", "footprint_name": "R0402"})
    assert detail["stage"] == "detail"
    assert "enet_fields" not in detail
    enet = format_enet_detail(part, {"symbol_uuid": "sym", "footprint_uuid": "pkg", "footprint_name": "R0402"})
    assert enet["stage"] == "enet"
    assert enet["enet_fields"]["LCSC"] == "C25804"
    assert enet["file_write_note"]
    print_json({"self_test": "ok"})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("filter", help="Stage 1: return catalog candidates for broad requirements")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--source", choices=["auto", "szlcsc", "jlcpcb", "lcsc"], default="auto")

    p = sub.add_parser("detail", help="Stage 2: return facts for one explicit LCSC code or exact MPN")
    p.add_argument("identifier")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--source", choices=["auto", "szlcsc", "jlcpcb", "lcsc"], default="auto")

    p = sub.add_parser("enet", help="Stage 2: return ENET-compatible fields for one explicit part")
    p.add_argument("identifier")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--source", choices=["auto", "szlcsc", "jlcpcb", "lcsc"], default="auto")

    sub.add_parser("self-test", help="Run offline output-contract tests")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "filter":
        command_filter(args)
    elif args.command == "detail":
        command_detail(args, include_enet=False)
    elif args.command == "enet":
        command_detail(args, include_enet=True)
    elif args.command == "self-test":
        self_test()


if __name__ == "__main__":
    main()
