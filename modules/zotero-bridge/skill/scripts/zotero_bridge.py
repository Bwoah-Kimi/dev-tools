#!/usr/bin/env python3
"""Read Zotero Desktop collections and export manifests for downstream tools."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_API_BASE = "http://127.0.0.1:23119/api"
API_VERSION = "3"
PAGE_SIZE = 100


class ZoteroBridgeError(RuntimeError):
    pass


def request_json(api_base: str, endpoint: str, params: dict[str, Any] | None = None) -> tuple[Any, dict[str, str]]:
    url = build_url(api_base, endpoint, params)
    request = urllib.request.Request(url, headers={"Zotero-API-Version": API_VERSION})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8")
            headers = {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace").strip()
        if "Local API is not enabled" in message:
            raise ZoteroBridgeError(
                "Zotero local API is not enabled. Enable Zotero Settings -> Advanced -> "
                "'Allow other applications on this computer to communicate with Zotero'."
            ) from exc
        raise ZoteroBridgeError(f"Zotero API HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise ZoteroBridgeError(f"Could not reach Zotero local API at {api_base}: {exc.reason}") from exc

    if not body:
        return None, headers
    try:
        return json.loads(body), headers
    except json.JSONDecodeError as exc:
        raise ZoteroBridgeError(f"Zotero API returned non-JSON response from {url}: {body[:200]}") from exc


def request_text(api_base: str, endpoint: str) -> str:
    url = build_url(api_base, endpoint, None)
    request = urllib.request.Request(url, headers={"Zotero-API-Version": API_VERSION})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace").strip()
        raise ZoteroBridgeError(f"Zotero API HTTP {exc.code}: {message}") from exc
    except urllib.error.URLError as exc:
        raise ZoteroBridgeError(f"Could not reach Zotero local API at {api_base}: {exc.reason}") from exc


def build_url(api_base: str, endpoint: str, params: dict[str, Any] | None) -> str:
    base = api_base.rstrip("/")
    path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    url = f"{base}{path}"
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        url = f"{url}?{query}"
    return url


def paged_request(api_base: str, endpoint: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    merged = dict(params or {})
    merged.setdefault("format", "json")
    merged.setdefault("limit", PAGE_SIZE)

    start = int(merged.get("start", 0))
    results: list[dict[str, Any]] = []
    while True:
        merged["start"] = start
        page, _headers = request_json(api_base, endpoint, merged)
        if not isinstance(page, list):
            raise ZoteroBridgeError(f"Expected a list from {endpoint}")
        results.extend(page)
        if len(page) < int(merged["limit"]):
            break
        start += len(page)
    return results


def get_collections(api_base: str) -> list[dict[str, Any]]:
    return paged_request(api_base, "/users/0/collections", {"include": "data"})


def collection_parent_key(collection: dict[str, Any]) -> str | None:
    parent = collection.get("data", {}).get("parentCollection")
    return None if parent is False else parent


def collection_name(collection: dict[str, Any]) -> str:
    return str(collection.get("data", {}).get("name", ""))


def collection_key(collection: dict[str, Any]) -> str:
    return str(collection.get("key") or collection.get("data", {}).get("key", ""))


def child_collection_map(collections: list[dict[str, Any]]) -> dict[str | None, list[dict[str, Any]]]:
    children: dict[str | None, list[dict[str, Any]]] = {}
    for collection in collections:
        children.setdefault(collection_parent_key(collection), []).append(collection)
    for entries in children.values():
        entries.sort(key=lambda entry: collection_name(entry).lower())
    return children


def render_collection_tree(collections: list[dict[str, Any]]) -> str:
    children = child_collection_map(collections)
    lines: list[str] = []

    def visit(collection: dict[str, Any], depth: int) -> None:
        meta = collection.get("meta", {})
        lines.append(
            f"{'  ' * depth}- {collection_name(collection)} "
            f"[{collection_key(collection)}] "
            f"items={meta.get('numItems', 0)} children={meta.get('numCollections', 0)}"
        )
        for child in children.get(collection_key(collection), []):
            visit(child, depth + 1)

    for root in children.get(None, []):
        visit(root, 0)
    return "\n".join(lines)


def resolve_collection(collections: list[dict[str, Any]], query: str) -> dict[str, Any]:
    normalized = query.casefold()
    by_key = [collection for collection in collections if collection_key(collection).casefold() == normalized]
    if by_key:
        return by_key[0]

    by_exact_name = [collection for collection in collections if collection_name(collection).casefold() == normalized]
    if len(by_exact_name) == 1:
        return by_exact_name[0]
    if len(by_exact_name) > 1:
        raise ZoteroBridgeError(format_ambiguous_collection(query, by_exact_name))

    by_partial = [collection for collection in collections if normalized in collection_name(collection).casefold()]
    if len(by_partial) == 1:
        return by_partial[0]
    if len(by_partial) > 1:
        raise ZoteroBridgeError(format_ambiguous_collection(query, by_partial))

    raise ZoteroBridgeError(f"No Zotero collection matched: {query}")


def format_ambiguous_collection(query: str, matches: list[dict[str, Any]]) -> str:
    choices = "\n".join(f"- {collection_name(item)} [{collection_key(item)}]" for item in matches)
    return f"Collection name is ambiguous: {query}\nMatching collections:\n{choices}"


def descendant_collection_keys(collections: list[dict[str, Any]], root_key: str) -> list[str]:
    children = child_collection_map(collections)
    keys = [root_key]

    def visit(key: str) -> None:
        for child in children.get(key, []):
            child_key = collection_key(child)
            keys.append(child_key)
            visit(child_key)

    visit(root_key)
    return keys


def get_collection_items(api_base: str, key: str) -> list[dict[str, Any]]:
    return paged_request(
        api_base,
        f"/users/0/collections/{urllib.parse.quote(key)}/items",
        {"include": "data", "format": "json"},
    )


def get_item_children(api_base: str, key: str) -> list[dict[str, Any]]:
    return paged_request(
        api_base,
        f"/users/0/items/{urllib.parse.quote(key)}/children",
        {"include": "data", "format": "json"},
    )


def file_url_to_path(url: str) -> str | None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "file":
        return None
    path = urllib.parse.unquote(parsed.path)
    if os.name == "nt" and len(path) >= 3 and path[0] == "/" and path[2] == ":":
        path = path[1:]
    return path.replace("/", os.sep)


def attachment_record(attachment: dict[str, Any]) -> dict[str, Any] | None:
    data = attachment.get("data", {})
    if data.get("itemType") != "attachment":
        return None
    content_type = str(data.get("contentType", ""))
    enclosure = attachment.get("links", {}).get("enclosure", {})
    href = str(enclosure.get("href", ""))
    if content_type != "application/pdf" and not href.lower().endswith(".pdf"):
        return None
    local_path = file_url_to_path(href)
    return {
        "attachment_key": attachment.get("key"),
        "title": data.get("title"),
        "filename": data.get("filename") or enclosure.get("title"),
        "content_type": content_type or enclosure.get("type"),
        "url": data.get("url"),
        "local_path": local_path,
        "exists": bool(local_path and Path(local_path).exists()),
        "link_mode": data.get("linkMode"),
    }


def creator_names(item: dict[str, Any]) -> list[str]:
    names = []
    for creator in item.get("data", {}).get("creators", []):
        last = creator.get("lastName", "")
        first = creator.get("firstName", "")
        name = " ".join(part for part in [first, last] if part).strip()
        if name:
            names.append(name)
    return names


def item_record(api_base: str, item: dict[str, Any]) -> dict[str, Any] | None:
    data = item.get("data", {})
    item_type = data.get("itemType")
    if item_type in {"attachment", "annotation", "note"}:
        return None

    attachments = []
    for child in get_item_children(api_base, str(item.get("key"))):
        record = attachment_record(child)
        if record:
            attachments.append(record)

    return {
        "item_key": item.get("key"),
        "item_type": item_type,
        "title": data.get("title"),
        "creators": creator_names(item),
        "date": data.get("date"),
        "year": item.get("meta", {}).get("parsedDate", "")[:4],
        "doi": data.get("DOI"),
        "url": data.get("url"),
        "publication": data.get("publicationTitle") or data.get("conferenceName") or data.get("publisher"),
        "abstract": data.get("abstractNote"),
        "tags": [tag.get("tag") for tag in data.get("tags", []) if tag.get("tag")],
        "collections": data.get("collections", []),
        "date_added": data.get("dateAdded"),
        "date_modified": data.get("dateModified"),
        "pdf_attachments": attachments,
    }


def export_manifest(api_base: str, collection_query: str, wiki_root: str, recursive: bool) -> dict[str, Any]:
    collections = get_collections(api_base)
    collection = resolve_collection(collections, collection_query)
    selected_key = collection_key(collection)
    keys = descendant_collection_keys(collections, selected_key) if recursive else [selected_key]

    records_by_key: dict[str, dict[str, Any]] = {}
    for key in keys:
        for item in get_collection_items(api_base, key):
            record = item_record(api_base, item)
            if record:
                records_by_key[str(record["item_key"])] = record

    items = sorted(records_by_key.values(), key=lambda entry: (str(entry.get("year") or ""), str(entry.get("title") or "")))
    missing_pdf = [entry["item_key"] for entry in items if not entry.get("pdf_attachments")]

    return {
        "schema": "zotero-bridge-manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "api_base": api_base,
        "wiki_root": str(Path(wiki_root)),
        "collection": {
            "key": selected_key,
            "name": collection_name(collection),
            "recursive": recursive,
            "included_collection_keys": keys,
        },
        "summary": {
            "item_count": len(items),
            "items_with_pdf": sum(1 for entry in items if entry.get("pdf_attachments")),
            "items_missing_pdf": len(missing_pdf),
        },
        "items": items,
    }


def default_manifest_path(wiki_root: str, collection_key_value: str) -> Path:
    return Path(wiki_root) / ".zotero" / f"{collection_key_value}.manifest.json"


def command_status(args: argparse.Namespace) -> int:
    text = request_text(args.api_base, "/")
    print(f"Zotero local API responded: {text.strip()}")
    return 0


def command_list_collections(args: argparse.Namespace) -> int:
    collections = get_collections(args.api_base)
    print(render_collection_tree(collections))
    return 0


def command_export_manifest(args: argparse.Namespace) -> int:
    manifest = export_manifest(args.api_base, args.collection, args.wiki_root, args.recursive)
    output = Path(args.output) if args.output else default_manifest_path(args.wiki_root, manifest["collection"]["key"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote manifest: {output}")
    print(
        "Items: {item_count}, with PDF: {items_with_pdf}, missing PDF: {items_missing_pdf}".format(
            **manifest["summary"]
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bridge Zotero Desktop collections to downstream research workflows.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help=f"Zotero API base URL (default: {DEFAULT_API_BASE})")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="Check whether Zotero local API is reachable.")
    status.set_defaults(func=command_status)

    collections = subparsers.add_parser("list-collections", help="Print Zotero collection tree.")
    collections.set_defaults(func=command_list_collections)

    manifest = subparsers.add_parser("export-manifest", help="Export a collection manifest with PDF attachment paths.")
    manifest.add_argument("collection", help="Collection key, exact name, or unambiguous partial name.")
    manifest.add_argument("--wiki-root", required=True, help="Target wiki root that will own the manifest.")
    manifest.add_argument("--output", help="Manifest output path. Defaults to <wiki-root>/.zotero/<collection-key>.manifest.json.")
    manifest.add_argument("--recursive", action="store_true", help="Include child collections recursively.")
    manifest.set_defaults(func=command_export_manifest)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except ZoteroBridgeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
