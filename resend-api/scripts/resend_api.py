#!/usr/bin/env python3
"""Agent-oriented Resend API helper.

This script is designed for skills-compatible agents that need a light-weight local tool for:
- discovering endpoints from a bundled catalogue
- choosing the correct Resend primitive for a task
- linting common payload mistakes before mutation
- scaffolding JSON payloads or cURL commands
- diagnosing common errors
- making cautious live API requests

Environment variables:
- RESEND_API_KEY        Required for live requests and optional for some doctor checks
- RESEND_BASE_URL       Optional; defaults to https://api.resend.com
- RESEND_USER_AGENT     Optional; defaults to resend-api-skill/2.0
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
ASSETS_DIR = SKILL_ROOT / "assets"

CATALOG_PATH = ASSETS_DIR / "endpoint-catalog.json"
ROUTER_PATH = ASSETS_DIR / "task-router.json"
ERROR_MAP_PATH = ASSETS_DIR / "error-map.json"
SCAFFOLD_INDEX_PATH = ASSETS_DIR / "scaffold-index.json"

DEFAULT_BASE_URL = "https://api.resend.com"
DEFAULT_USER_AGENT = "resend-api-skill/2.0"

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")
FROM_WITH_NAME_RE = re.compile(r"^\s*.+<([^<>@\s]+@[^<>@\s]+\.[^<>@\s]+)>\s*$")
TAG_RE = re.compile(r"^[A-Za-z0-9_-]{1,256}$")
PROPERTY_KEY_RE = re.compile(r"^[A-Za-z0-9_]{1,50}$")
TEMPLATE_VAR_KEY_RE = re.compile(r"^[A-Za-z0-9_]{1,50}$")
ISO_LIKE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T")
UNSUPPORTED_ATTACHMENT_EXTENSIONS = {
    ".adp",".app",".asp",".bas",".bat",".cer",".chm",".cmd",".com",".cpl",
    ".crt",".csh",".der",".exe",".fxp",".gadget",".hlp",".hta",".inf",".ins",
    ".isp",".its",".js",".jse",".ksh",".lib",".lnk",".mad",".maf",".mag",
    ".mam",".maq",".mar",".mas",".mat",".mau",".mav",".maw",".mda",".mdb",
    ".mde",".mdt",".mdw",".mdz",".msc",".msh",".msh1",".msh2",".mshxml",
    ".msh1xml",".msh2xml",".msi",".msp",".mst",".ops",".pcd",".pif",".plg",
    ".prf",".prg",".reg",".scf",".scr",".sct",".shb",".shs",".sys",".ps1",
    ".ps1xml",".ps2",".ps2xml",".psc1",".psc2",".tmp",".url",".vb",".vbe",
    ".vbs",".vps",".vsmacros",".vss",".vst",".vsw",".vxd",".ws",".wsc",
    ".wsf",".wsh",".xnk",
}
TOPIC_SUBSCRIPTIONS = {"opt_in", "opt_out"}
DOMAIN_REGIONS = {"us-east-1", "eu-west-1", "sa-east-1", "ap-northeast-1"}
TLS_MODES = {"opportunistic", "enforced"}
API_KEY_PERMISSIONS = {"full_access", "sending_access"}
CONTACT_PROPERTY_TYPES = {"string", "number"}
TEMPLATE_RESERVED_VARIABLES = {"FIRST_NAME", "LAST_NAME", "EMAIL", "UNSUBSCRIBE_URL"}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def print_json(obj: Any) -> None:
    json.dump(obj, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")


def load_catalog() -> Dict[str, Any]:
    return load_json(CATALOG_PATH)


def load_router() -> Dict[str, Any]:
    return load_json(ROUTER_PATH)


def load_error_map() -> Dict[str, Any]:
    return load_json(ERROR_MAP_PATH)


def load_scaffold_index() -> Dict[str, Any]:
    return load_json(SCAFFOLD_INDEX_PATH)


def iter_endpoints(catalog: Dict[str, Any], include_beta: bool = False) -> Iterable[Dict[str, Any]]:
    for tag in catalog.get("tags", []):
        for endpoint in tag.get("endpoints", []):
            item = dict(endpoint)
            item["group"] = tag.get("name")
            item["group_description"] = tag.get("description")
            yield item

    if include_beta:
        beta = catalog.get("beta_notes", {})
        for beta_group, info in beta.items():
            for endpoint in info.get("confirmed_endpoints", []):
                item = dict(endpoint)
                item["group"] = f"beta:{beta_group}"
                item["group_description"] = info.get("ga_stability")
                item["beta_status"] = info.get("status")
                yield item


def endpoint_match_score(template_path: str, actual_path: str) -> Optional[int]:
    if template_path == actual_path:
        return 10_000
    pattern = re.sub(r"\{[^/]+\}", r"[^/]+", template_path)
    if re.match("^" + pattern + "$", actual_path):
        return 100 + template_path.count("{")
    return None


def find_endpoint(catalog: Dict[str, Any], method: str, path: str, include_beta: bool = True) -> Dict[str, Any]:
    method = method.upper()
    best: Optional[Tuple[int, Dict[str, Any]]] = None
    for endpoint in iter_endpoints(catalog, include_beta=include_beta):
        if endpoint.get("method", "").upper() != method:
            continue
        score = endpoint_match_score(str(endpoint.get("path", "")), path)
        if score is None:
            continue
        if best is None or score > best[0]:
            best = (score, endpoint)
    if best is None:
        raise SystemExit(f"Error: no endpoint matched {method} {path}")
    return best[1]


def parse_kv_pairs(pairs: List[str]) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise SystemExit(f"Error: expected KEY=VALUE, got: {pair}")
        key, value = pair.split("=", 1)
        parsed[key] = value
    return parsed


def parse_headers(items: List[str]) -> Dict[str, str]:
    headers: Dict[str, str] = {}
    for item in items:
        if ":" not in item:
            raise SystemExit(f"Error: expected 'Name: value', got: {item}")
        name, value = item.split(":", 1)
        headers[name.strip()] = value.strip()
    return headers


def load_json_body(inline_json: Optional[str], json_file: Optional[str]) -> Any:
    if inline_json and json_file:
        raise SystemExit("Error: choose either --json or --json-file, not both")
    if inline_json:
        try:
            return json.loads(inline_json)
        except json.JSONDecodeError as e:
            raise SystemExit(f"Error: invalid --json payload: {e}")
    if json_file:
        try:
            return json.loads(Path(json_file).read_text(encoding="utf-8"))
        except Exception as e:
            raise SystemExit(f"Error: failed to read --json-file: {e}")
    return None


def mask_headers(headers: Dict[str, str]) -> Dict[str, str]:
    masked = dict(headers)
    for key in list(masked):
        if key.lower() == "authorization":
            masked[key] = "Bearer ***"
    return masked


def lower_tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9_@./+-]+", text.lower())


def contains_phrase(text: str, phrase: str) -> bool:
    return phrase.lower() in text.lower()


def extract_email(address: str) -> Optional[str]:
    address = address.strip()
    if EMAIL_RE.match(address):
        return address
    m = FROM_WITH_NAME_RE.match(address)
    if m:
        return m.group(1)
    return None


def extract_domain(address: str) -> Optional[str]:
    email = extract_email(address)
    if not email:
        return None
    return email.split("@", 1)[1].lower()


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def build_url(base_url: str, path: str, query: Dict[str, str]) -> str:
    if not path.startswith("/"):
        raise SystemExit("Error: path must start with '/'")
    url = base_url.rstrip("/") + path
    if query:
        url += "?" + urllib.parse.urlencode(query, doseq=True)
    return url


def parse_response_body(content_type: str, raw_bytes: bytes) -> Any:
    lowered = (content_type or "").lower()
    if "application/json" in lowered or lowered.endswith("+json"):
        try:
            return json.loads(raw_bytes.decode("utf-8"))
        except Exception:
            return {"_raw_text": raw_bytes.decode("utf-8", errors="replace")}
    if lowered.startswith("text/") or "charset=" in lowered:
        return raw_bytes.decode("utf-8", errors="replace")
    return {
        "_binary_base64": base64.b64encode(raw_bytes).decode("ascii"),
        "_content_type": content_type,
        "_byte_length": len(raw_bytes),
        "_hint": "Binary response. Prefer --output FILE for attachments or large payloads."
    }


def should_retry(method: str, status: Optional[int], attempt: int, max_retries: int) -> bool:
    if attempt > max_retries:
        return False
    if status is None:
        return True
    return status in RETRYABLE_STATUSES


def maybe_paginate(
    opener: urllib.request.OpenerDirector,
    method: str,
    url: str,
    headers: Dict[str, str],
    timeout: float,
    page_limit: int,
) -> Dict[str, Any]:
    pages: List[Any] = []
    page_urls: List[str] = []
    next_url = url
    page_count = 0

    while next_url and page_count < page_limit:
        req = urllib.request.Request(next_url, method=method, headers=headers)
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read()
            content_type = resp.headers.get("Content-Type", "")
            body = parse_response_body(content_type, raw)
            pages.append(body)
            page_urls.append(next_url)
            page_count += 1

            next_candidate = None
            if (
                isinstance(body, dict)
                and body.get("object") == "list"
                and body.get("has_more")
                and isinstance(body.get("data"), list)
                and body["data"]
                and isinstance(body["data"][-1], dict)
                and body["data"][-1].get("id")
            ):
                parsed = urllib.parse.urlparse(next_url)
                current_query = dict(urllib.parse.parse_qsl(parsed.query))
                current_query["after"] = str(body["data"][-1]["id"])
                current_query.pop("before", None)
                next_candidate = urllib.parse.urlunparse(
                    (
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        parsed.params,
                        urllib.parse.urlencode(current_query, doseq=True),
                        parsed.fragment,
                    )
                )
            next_url = next_candidate

    return {
        "pages": pages,
        "page_urls": page_urls,
        "page_count": page_count,
        "truncated": page_count >= page_limit and next_url is not None,
    }


def route_score(task: str, route: Dict[str, Any]) -> int:
    task_l = task.lower()
    tokens = set(lower_tokens(task))
    score = 0
    for keyword in route.get("keywords", []):
        kw = keyword.lower()
        if kw in task_l:
            score += max(3, len(kw.split()) * 4)
        kw_tokens = set(lower_tokens(kw))
        if kw_tokens and kw_tokens.issubset(tokens):
            score += len(kw_tokens) * 2
        else:
            score += len(kw_tokens & tokens)
    for endpoint in route.get("endpoints", []):
        path = endpoint.get("path", "").lower()
        if path and path in task_l:
            score += 15
    return score


def command_catalog(args: argparse.Namespace) -> int:
    catalog = load_catalog()
    results = []
    for endpoint in iter_endpoints(catalog, include_beta=args.include_beta):
        group = str(endpoint.get("group") or "")
        if args.group and group.lower() != args.group.lower():
            continue
        if args.method and str(endpoint.get("method") or "").upper() != args.method.upper():
            continue
        haystack = " ".join(
            str(x or "")
            for x in [group, endpoint.get("path"), endpoint.get("summary"), endpoint.get("description")]
        ).lower()
        if args.search and args.search.lower() not in haystack:
            continue
        if not args.include_deprecated and endpoint.get("deprecated"):
            continue
        results.append(
            {
                "group": group,
                "method": endpoint.get("method"),
                "path": endpoint.get("path"),
                "summary": endpoint.get("summary"),
                "deprecated": bool(endpoint.get("deprecated", False)),
                "beta_status": endpoint.get("beta_status"),
            }
        )

    if args.format == "json":
        print_json({"count": len(results), "endpoints": results})
        return 0

    if not results:
        print("No endpoints matched.", file=sys.stderr)
        return 1

    group_width = max(len(item["group"] or "") for item in results)
    method_width = max(len(item["method"] or "") for item in results)
    path_width = max(len(item["path"] or "") for item in results)
    header = f"{'GROUP'.ljust(group_width)}  {'METHOD'.ljust(method_width)}  {'PATH'.ljust(path_width)}  SUMMARY"
    print(header)
    print("-" * len(header))
    for item in results:
        beta = f" [{item['beta_status']}]" if item.get("beta_status") else ""
        print(
            f"{(item['group'] or '').ljust(group_width)}  "
            f"{(item['method'] or '').ljust(method_width)}  "
            f"{(item['path'] or '').ljust(path_width)}  "
            f"{item['summary'] or ''}{beta}"
        )
    return 0


def command_schema(args: argparse.Namespace) -> int:
    catalog = load_catalog()
    endpoint = find_endpoint(catalog, args.method, args.path, include_beta=True)
    result = {
        "group": endpoint.get("group"),
        "method": endpoint.get("method"),
        "path": endpoint.get("path"),
        "summary": endpoint.get("summary"),
        "description": endpoint.get("description"),
        "deprecated": endpoint.get("deprecated", False),
        "beta_status": endpoint.get("beta_status"),
        "parameters": endpoint.get("parameters"),
        "request_body": endpoint.get("request_body"),
        "responses": endpoint.get("responses"),
        "group_description": endpoint.get("group_description"),
    }
    print_json(result)
    return 0


def command_recommend(args: argparse.Namespace) -> int:
    router = load_router()
    task = args.task.strip()
    ranked = []
    for route in router.get("routes", []):
        score = route_score(task, route)
        ranked.append((score, route))
    ranked.sort(key=lambda item: item[0], reverse=True)

    best_score = ranked[0][0] if ranked else 0
    selected = []
    for score, route in ranked[: args.top]:
        if score <= 0 and not args.include_low_confidence:
            continue
        selected.append(
            {
                "score": score,
                "id": route.get("id"),
                "name": route.get("name"),
                "surfaces": route.get("surfaces"),
                "endpoints": route.get("endpoints"),
                "samples": route.get("samples"),
                "references": route.get("references"),
                "notes": route.get("notes"),
                "anti_patterns": route.get("anti_patterns"),
            }
        )

    confidence = "low"
    if best_score >= 25:
        confidence = "high"
    elif best_score >= 12:
        confidence = "medium"

    print_json(
        {
            "task": task,
            "confidence": confidence,
            "best_score": best_score,
            "recommendations": selected,
        }
    )
    return 0


class LintCollector:
    def __init__(self) -> None:
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def note(self, message: str) -> None:
        self.info.append(message)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "ok": not self.errors,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
        }


def validate_email_address(value: Any) -> bool:
    return isinstance(value, str) and extract_email(value) is not None


def validate_to_count(value: Any) -> Optional[int]:
    recipients = as_list(value)
    if recipients and all(isinstance(item, str) for item in recipients):
        return len(recipients)
    return None


def iter_email_strings(value: Any) -> List[str]:
    recipients = as_list(value)
    if all(isinstance(item, str) for item in recipients):
        return recipients
    return []


def attachment_size_estimate_bytes(attachment: Dict[str, Any]) -> int:
    if not isinstance(attachment, dict):
        return 0
    content = attachment.get("content")
    if isinstance(content, str):
        try:
            return len(base64.b64decode(content, validate=True))
        except Exception:
            return int(len(content) * 0.75)
    return 0


def attachment_extension(attachment: Dict[str, Any]) -> Optional[str]:
    if not isinstance(attachment, dict):
        return None
    filename = attachment.get("filename")
    if not filename and isinstance(attachment.get("path"), str):
        filename = attachment["path"].rsplit("/", 1)[-1]
    if not isinstance(filename, str) or "." not in filename:
        return None
    return "." + filename.rsplit(".", 1)[-1].lower()


def lint_send_email(body: Any, headers: Dict[str, str], collector: LintCollector) -> None:
    if not isinstance(body, dict):
        collector.error("POST /emails expects a JSON object.")
        return

    for key in ("from", "to", "subject"):
        if key not in body:
            collector.error(f"Missing required field: {key}")

    from_value = body.get("from")
    if from_value is not None and not validate_email_address(from_value):
        collector.error("from must be 'email@example.com' or 'Name <email@example.com>'.")
    from_domain = extract_domain(from_value) if isinstance(from_value, str) else None
    if from_domain == "resend.dev":
        collector.warn("from uses resend.dev, which is testing-only. Verify a custom domain for real sends.")

    to_count = validate_to_count(body.get("to"))
    if to_count is None and body.get("to") is not None:
        collector.error("to must be a string email address or an array of string email addresses.")
    elif to_count is not None and to_count > 50:
        collector.error("POST /emails supports at most 50 recipients in to.")
    for recipient in iter_email_strings(body.get("to")):
        domain = extract_domain(recipient)
        if domain in {"example.com", "test.com"}:
            collector.error(f"Recipient '{recipient}' uses a blocked fake test domain.")

    template = body.get("template")
    has_raw_content = any(field in body for field in ("html", "text", "react"))
    if template is not None and has_raw_content:
        collector.error("Do not combine template with html, text, or react in POST /emails.")
    if template is None and not has_raw_content:
        collector.error("Provide message content (html/text/react) or template.")

    if template is not None:
        if not isinstance(template, dict) or not template.get("id"):
            collector.error("template must be an object containing id.")
        variables = template.get("variables")
        if variables is not None:
            if not isinstance(variables, dict):
                collector.error("template.variables must be an object.")
            else:
                for key, value in variables.items():
                    if not TEMPLATE_VAR_KEY_RE.match(str(key)):
                        collector.error(f"Template variable key '{key}' is not valid.")
                    if key in TEMPLATE_RESERVED_VARIABLES:
                        collector.note(f"Template variable '{key}' is reserved by Resend; use it intentionally.")
                    if isinstance(value, str) and len(value) > 2000:
                        collector.error(f"Template variable '{key}' exceeds the 2000-character limit.")
                    if isinstance(value, int) and abs(value) > 9_007_199_254_740_991:
                        collector.error(f"Template variable '{key}' is outside the safe integer range.")

    tags = body.get("tags")
    if tags is not None:
        if not isinstance(tags, list):
            collector.error("tags must be an array of objects.")
        else:
            for index, tag in enumerate(tags):
                if not isinstance(tag, dict):
                    collector.error(f"tags[{index}] must be an object.")
                    continue
                name = tag.get("name")
                value = tag.get("value")
                if not isinstance(name, str) or not TAG_RE.match(name):
                    collector.error(f"tags[{index}].name must match [A-Za-z0-9_-] and be <= 256 chars.")
                if not isinstance(value, str) or not TAG_RE.match(value):
                    collector.error(f"tags[{index}].value must match [A-Za-z0-9_-] and be <= 256 chars.")

    scheduled_at = body.get("scheduled_at")
    if scheduled_at is not None:
        if not isinstance(scheduled_at, str):
            collector.error("scheduled_at must be a string.")
        elif ISO_LIKE_RE.match(scheduled_at):
            collector.note("scheduled_at looks like ISO 8601, which is preferred in generated code.")
        else:
            collector.note("scheduled_at looks like natural language. This can work, but prefer ISO 8601 in generated code.")

    attachments = body.get("attachments")
    if attachments is not None:
        if not isinstance(attachments, list):
            collector.error("attachments must be an array.")
        else:
            total_estimated = 0
            for index, attachment in enumerate(attachments):
                if not isinstance(attachment, dict):
                    collector.error(f"attachments[{index}] must be an object.")
                    continue
                if "content" not in attachment and "path" not in attachment:
                    collector.error(f"attachments[{index}] must include content or path.")
                ext = attachment_extension(attachment)
                if ext in UNSUPPORTED_ATTACHMENT_EXTENSIONS:
                    collector.error(f"attachments[{index}] uses unsupported outbound attachment extension {ext}.")
                total_estimated += attachment_size_estimate_bytes(attachment)
            if total_estimated > 40 * 1024 * 1024:
                collector.error("Estimated attachment payload exceeds the 40 MB email limit after Base64 overhead considerations.")
            elif total_estimated > 0:
                collector.note(f"Estimated attachment payload bytes (decoded only): {total_estimated}")

    topic_id = body.get("topic_id")
    if topic_id is not None and not isinstance(topic_id, str):
        collector.error("topic_id must be a string.")
    elif topic_id is not None:
        collector.note("topic_id scopes the send to a Topic's subscription rules.")

    if "Idempotency-Key" not in headers and "idempotency-key" not in {k.lower(): v for k, v in headers.items()}:
        collector.warn("Consider adding Idempotency-Key for POST /emails if the request might be retried.")


def lint_send_batch(body: Any, headers: Dict[str, str], collector: LintCollector) -> None:
    if not isinstance(body, list):
        collector.error("POST /emails/batch expects a JSON array.")
        return
    if not body:
        collector.warn("Empty batch payload.")
    if len(body) > 100:
        collector.error("POST /emails/batch supports at most 100 items per request.")
    for index, item in enumerate(body):
        if not isinstance(item, dict):
            collector.error(f"batch item {index} must be an object.")
            continue
        for key in ("from", "to", "subject"):
            if key not in item:
                collector.error(f"batch item {index} is missing required field: {key}")
        from_domain = extract_domain(item.get("from")) if isinstance(item.get("from"), str) else None
        if from_domain == "resend.dev":
            collector.warn(f"batch item {index} uses resend.dev in from, which is testing-only.")
        for recipient in iter_email_strings(item.get("to")):
            domain = extract_domain(recipient)
            if domain in {"example.com", "test.com"}:
                collector.error(f"batch item {index} recipient '{recipient}' uses a blocked fake test domain.")
        if item.get("attachments") is not None:
            collector.error(f"batch item {index} includes attachments, which are not supported on /emails/batch.")
        if item.get("scheduled_at") is not None:
            collector.error(f"batch item {index} includes scheduled_at, which is not supported on /emails/batch.")
        if item.get("template") is not None and any(field in item for field in ("html", "text", "react")):
            collector.error(f"batch item {index} combines template with html/text/react.")
        to_count = validate_to_count(item.get("to"))
        if to_count is None and item.get("to") is not None:
            collector.error(f"batch item {index} has an invalid to field.")
        elif to_count is not None and to_count > 50:
            collector.error(f"batch item {index} exceeds the 50-recipient to limit.")
    if "Idempotency-Key" not in headers and "idempotency-key" not in {k.lower(): v for k, v in headers.items()}:
        collector.warn("Consider adding Idempotency-Key for POST /emails/batch if the request might be retried.")


def lint_update_email(body: Any, collector: LintCollector) -> None:
    if not isinstance(body, dict):
        collector.error("PATCH /emails/{email_id} expects a JSON object.")
        return
    if not body:
        collector.warn("Empty payload.")
    scheduled_at = body.get("scheduled_at")
    if scheduled_at is None:
        collector.warn("PATCH /emails/{email_id} is usually used to update scheduled_at.")
    elif not isinstance(scheduled_at, str):
        collector.error("scheduled_at must be a string.")
    elif ISO_LIKE_RE.match(scheduled_at):
        collector.note("scheduled_at looks like ISO 8601.")
    else:
        collector.note("scheduled_at looks like natural language; prefer ISO 8601 in generated code.")


def lint_create_domain(body: Any, collector: LintCollector) -> None:
    if not isinstance(body, dict):
        collector.error("POST /domains expects a JSON object.")
        return
    if not body.get("name"):
        collector.error("Missing required field: name")
    region = body.get("region")
    if region is not None and region not in DOMAIN_REGIONS:
        collector.error(f"region must be one of: {', '.join(sorted(DOMAIN_REGIONS))}")
    tls = body.get("tls")
    if tls is not None and tls not in TLS_MODES:
        collector.error(f"tls must be one of: {', '.join(sorted(TLS_MODES))}")
    capabilities = body.get("capabilities")
    if capabilities is not None:
        if not isinstance(capabilities, dict):
            collector.error("capabilities must be an object.")
        else:
            if not capabilities.get("sending") and not capabilities.get("receiving"):
                collector.error("At least one of capabilities.sending or capabilities.receiving must be true.")
            if capabilities.get("receiving"):
                collector.note("Receiving often works best on a dedicated subdomain if the root domain already has MX records.")


def lint_create_webhook(body: Any, collector: LintCollector) -> None:
    if not isinstance(body, dict):
        collector.error("POST /webhooks expects a JSON object.")
        return
    if not body.get("endpoint"):
        collector.error("Missing required field: endpoint")
    elif not str(body.get("endpoint")).startswith("https://"):
        collector.warn("Webhook endpoints should normally be HTTPS URLs.")
    events = body.get("events")
    if not isinstance(events, list) or not events:
        collector.error("events must be a non-empty array.")
    else:
        collector.note("Remember to verify webhook signatures using the raw request body.")


def lint_create_contact(body: Any, collector: LintCollector) -> None:
    if not isinstance(body, dict):
        collector.error("POST /contacts expects a JSON object.")
        return
    if not validate_email_address(body.get("email", "")):
        collector.error("contacts.email must be a valid email address.")
    topics = body.get("topics")
    if topics is not None:
        if not isinstance(topics, list):
            collector.error("topics must be an array.")
        else:
            for index, item in enumerate(topics):
                if not isinstance(item, dict):
                    collector.error(f"topics[{index}] must be an object.")
                    continue
                if not item.get("id"):
                    collector.error(f"topics[{index}].id is required.")
                sub = item.get("subscription")
                if sub not in TOPIC_SUBSCRIPTIONS:
                    collector.error(f"topics[{index}].subscription must be one of {sorted(TOPIC_SUBSCRIPTIONS)}.")
    segments = body.get("segments")
    if segments is not None and (not isinstance(segments, list) or not all(isinstance(x, str) for x in segments)):
        collector.error("segments must be an array of segment IDs.")
    if body.get("unsubscribed") is True and topics:
        collector.warn("unsubscribed=true globally overrides Broadcast subscriptions, even if some topics are opt_in.")
    if body.get("audience_id") is not None:
        collector.warn("audience_id is deprecated; prefer segments for new builds.")


def lint_update_contact_topics(body: Any, collector: LintCollector) -> None:
    if not isinstance(body, dict):
        collector.error("PATCH /contacts/{contact_id}/topics expects a JSON object.")
        return
    topics = body.get("topics")
    if not isinstance(topics, list) or not topics:
        collector.error("topics must be a non-empty array.")
        return
    for index, item in enumerate(topics):
        if not isinstance(item, dict):
            collector.error(f"topics[{index}] must be an object.")
            continue
        if not item.get("id"):
            collector.error(f"topics[{index}].id is required.")
        if item.get("subscription") not in TOPIC_SUBSCRIPTIONS:
            collector.error(f"topics[{index}].subscription must be one of {sorted(TOPIC_SUBSCRIPTIONS)}.")


def lint_create_topic(body: Any, collector: LintCollector) -> None:
    if not isinstance(body, dict):
        collector.error("POST /topics expects a JSON object.")
        return
    if not body.get("name"):
        collector.error("Missing required field: name")
    elif len(str(body.get("name"))) > 50:
        collector.error("Topic name must be at most 50 characters.")
    if body.get("description") is not None and len(str(body.get("description"))) > 200:
        collector.error("Topic description must be at most 200 characters.")
    default_subscription = body.get("default_subscription")
    if default_subscription not in TOPIC_SUBSCRIPTIONS:
        collector.error(f"default_subscription must be one of {sorted(TOPIC_SUBSCRIPTIONS)}.")
    visibility = body.get("visibility")
    if visibility is not None and visibility not in {"public", "private"}:
        collector.error("visibility must be public or private.")
    collector.note("Choose default_subscription carefully; it cannot be changed casually later.")


def lint_create_segment(body: Any, collector: LintCollector) -> None:
    if not isinstance(body, dict):
        collector.error("POST /segments expects a JSON object.")
        return
    if not body.get("name"):
        collector.error("Missing required field: name")
    if body.get("audience_id") is not None:
        collector.warn("audience_id is legacy/deprecated territory; prefer segment-first designs.")


def lint_create_contact_property(body: Any, collector: LintCollector) -> None:
    if not isinstance(body, dict):
        collector.error("POST /contact-properties expects a JSON object.")
        return
    key = body.get("key")
    prop_type = body.get("type")
    if not isinstance(key, str) or not PROPERTY_KEY_RE.match(key):
        collector.error("key must be <= 50 chars and contain only letters, numbers, or underscores.")
    if prop_type not in CONTACT_PROPERTY_TYPES:
        collector.error(f"type must be one of {sorted(CONTACT_PROPERTY_TYPES)}.")
    if "fallback_value" in body:
        fv = body.get("fallback_value")
        if prop_type == "string" and not isinstance(fv, str):
            collector.error("fallback_value must be a string when type=string.")
        if prop_type == "number" and not isinstance(fv, (int, float)):
            collector.error("fallback_value must be a number when type=number.")


def lint_create_broadcast(body: Any, collector: LintCollector) -> None:
    if not isinstance(body, dict):
        collector.error("POST /broadcasts expects a JSON object.")
        return
    for key in ("from", "subject", "segment_id"):
        if key not in body:
            collector.error(f"Missing required field: {key}")
    if "html" not in body and "text" not in body:
        collector.error("Provide html or text content for the broadcast.")
    send = body.get("send")
    if body.get("scheduled_at") is not None and send is not True:
        collector.error("scheduled_at can only be used when send=true.")
    if body.get("topic_id") is None:
        collector.warn("Consider adding topic_id so unsubscribes can be scoped to a content category.")
    if body.get("audience_id") is not None:
        collector.warn("audience_id is deprecated; use segment_id instead.")


def lint_create_api_key(body: Any, collector: LintCollector) -> None:
    if not isinstance(body, dict):
        collector.error("POST /api-keys expects a JSON object.")
        return
    if not body.get("name"):
        collector.error("Missing required field: name")
    permission = body.get("permission")
    if permission is not None and permission not in API_KEY_PERMISSIONS:
        collector.error(f"permission must be one of {sorted(API_KEY_PERMISSIONS)}.")
    if permission == "full_access":
        collector.warn("Prefer sending_access unless the task truly needs full resource-management scope.")
    if body.get("domain_id") is not None and permission not in (None, "sending_access"):
        collector.warn("domain_id restriction only matters for sending_access keys.")


def lint_create_template(body: Any, collector: LintCollector) -> None:
    if not isinstance(body, dict):
        collector.error("POST /templates expects a JSON object.")
        return
    for key in ("name", "html"):
        if not body.get(key):
            collector.error(f"Missing required field: {key}")
    variables = body.get("variables")
    if variables is not None:
        if not isinstance(variables, list):
            collector.error("variables must be an array.")
        else:
            for index, item in enumerate(variables):
                if not isinstance(item, dict):
                    collector.error(f"variables[{index}] must be an object.")
                    continue
                if not item.get("key"):
                    collector.error(f"variables[{index}].key is required.")
                if item.get("type") not in {"string", "number", "boolean", "object", "list"}:
                    collector.error(f"variables[{index}].type is not recognised.")


def lint_generic(method: str, path: str, body: Any, headers: Dict[str, str], collector: LintCollector, surface: str) -> None:
    if surface == "raw-rest" and "User-Agent" not in headers and "user-agent" not in {k.lower() for k in headers}:
        collector.warn("Raw REST requests should include a User-Agent header or they may be rejected.")
    if method in {"POST", "PATCH", "PUT"} and body is None and path not in {"/emails/{email_id}/cancel"}:
        collector.warn("No JSON body was provided.")


def command_lint(args: argparse.Namespace) -> int:
    method = args.method.upper()
    path = args.path
    headers = parse_headers(args.header)
    if args.idempotency_key:
        headers["Idempotency-Key"] = args.idempotency_key
    body = load_json_body(args.json, args.json_file)
    collector = LintCollector()

    lint_generic(method, path, body, headers, collector, args.surface)
    if method == "POST" and path == "/emails":
        lint_send_email(body, headers, collector)
    elif method == "POST" and path == "/emails/batch":
        lint_send_batch(body, headers, collector)
    elif method == "PATCH" and path == "/emails/{email_id}":
        lint_update_email(body, collector)
    elif method == "POST" and path == "/domains":
        lint_create_domain(body, collector)
    elif method == "POST" and path == "/webhooks":
        lint_create_webhook(body, collector)
    elif method == "POST" and path == "/contacts":
        lint_create_contact(body, collector)
    elif method == "PATCH" and path == "/contacts/{contact_id}/topics":
        lint_update_contact_topics(body, collector)
    elif method == "POST" and path == "/topics":
        lint_create_topic(body, collector)
    elif method == "POST" and path == "/segments":
        lint_create_segment(body, collector)
    elif method == "POST" and path == "/contact-properties":
        lint_create_contact_property(body, collector)
    elif method == "POST" and path == "/broadcasts":
        lint_create_broadcast(body, collector)
    elif method == "POST" and path == "/api-keys":
        lint_create_api_key(body, collector)
    elif method == "POST" and path == "/templates":
        lint_create_template(body, collector)

    print_json(
        {
            "method": method,
            "path": path,
            "surface": args.surface,
            **collector.as_dict(),
        }
    )
    return 0 if not collector.errors else 1


def command_scaffold(args: argparse.Namespace) -> int:
    index = load_scaffold_index()
    scaffolds = {item["name"]: item for item in index.get("scaffolds", [])}
    if args.list:
        print_json({"scaffolds": list(scaffolds.values())})
        return 0
    if not args.name:
        raise SystemExit("Error: scaffold name is required unless --list is used")
    if args.name not in scaffolds:
        raise SystemExit(f"Error: unknown scaffold '{args.name}'. Use --list to see available names.")
    item = scaffolds[args.name]
    asset_path = SKILL_ROOT / item["asset"]
    payload = json.loads(asset_path.read_text(encoding="utf-8"))
    if args.format == "json":
        print_json({"name": args.name, "method": item["method"], "path": item["path"], "payload": payload})
        return 0

    method = item["method"].upper()
    path = item["path"]
    url = f"{DEFAULT_BASE_URL}{path}"
    lines = [f"curl -X {method} \\"]

    if method == "GET" and isinstance(payload, dict) and isinstance(payload.get("query_parameters"), dict):
        query = urllib.parse.urlencode(payload["query_parameters"], doseq=True)
        url = url + ("?" + query if query else "")
        lines.extend([
            f"  '{url}' \\",
            "  -H 'Authorization: Bearer $RESEND_API_KEY' \\",
            f"  -H 'User-Agent: {DEFAULT_USER_AGENT}'",
        ])
    else:
        body = json.dumps(payload, indent=2, ensure_ascii=False)
        lines.extend([
            f"  '{url}' \\",
            "  -H 'Authorization: Bearer $RESEND_API_KEY' \\",
            f"  -H 'User-Agent: {DEFAULT_USER_AGENT}' \\",
            "  -H 'Content-Type: application/json' \\",
            "  --data-binary @- <<'JSON'",
            body,
            "JSON",
        ])

    result = {
        "name": args.name,
        "method": item["method"],
        "path": item["path"],
        "description": item.get("description"),
        "curl": "\n".join(lines),
    }
    print_json(result)
    return 0


def http_get_json(path: str, timeout: float = 30.0) -> Tuple[int, Dict[str, str], Any]:
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        raise SystemExit("Error: RESEND_API_KEY is required for this operation")
    base_url = os.environ.get("RESEND_BASE_URL", DEFAULT_BASE_URL)
    user_agent = os.environ.get("RESEND_USER_AGENT", DEFAULT_USER_AGENT)
    headers = {"Authorization": f"Bearer {api_key}", "User-Agent": user_agent}
    url = build_url(base_url, path, {})
    req = urllib.request.Request(url, method="GET", headers=headers)
    opener = urllib.request.build_opener()
    with opener.open(req, timeout=timeout) as resp:
        raw = resp.read()
        body = parse_response_body(resp.headers.get("Content-Type", ""), raw)
        return resp.getcode(), dict(resp.headers.items()), body


def command_doctor(args: argparse.Namespace) -> int:
    error_map = load_error_map()
    clues = []
    haystack = " ".join(part for part in [args.message or "", args.code or ""]).lower()
    status = args.status

    for case in error_map.get("cases", []):
        match = case.get("match", {})
        statuses = match.get("status", [])
        substrings = [s.lower() for s in match.get("substrings", [])]
        ok_status = not statuses or status in statuses
        ok_substring = not substrings or any(sub in haystack for sub in substrings)
        if ok_status and ok_substring:
            clues.append(case)

    from_domain = extract_domain(args.from_address) if args.from_address else None
    to_domain = extract_domain(args.to_address) if args.to_address else None

    heuristic_warnings: List[str] = []
    heuristic_info: List[str] = []

    if from_domain == "resend.dev":
        heuristic_warnings.append("from is on resend.dev. That domain is only for testing; verify a custom domain for real sends.")
    if to_domain in {"example.com", "test.com"}:
        heuristic_warnings.append("to uses a blocked fake test domain. Use Resend's safe testing addresses instead.")
    if args.verified_domain and from_domain and from_domain != args.verified_domain.lower():
        heuristic_warnings.append(
            f"from domain '{from_domain}' does not exactly match the provided verified domain '{args.verified_domain.lower()}'."
        )

    live_domains = None
    if args.fetch_domains:
        try:
            _, _, body = http_get_json("/domains", timeout=args.timeout)
            live_domains = []
            if isinstance(body, dict):
                items = body.get("data") if isinstance(body.get("data"), list) else []
                for item in items:
                    if isinstance(item, dict) and item.get("name"):
                        live_domains.append(str(item["name"]).lower())
            if from_domain and live_domains and from_domain not in set(live_domains):
                heuristic_warnings.append(
                    f"from domain '{from_domain}' is not present in the live domain list returned by GET /domains."
                )
            if live_domains:
                heuristic_info.append("Live domains fetched successfully from GET /domains.")
        except Exception as e:
            heuristic_warnings.append(f"Could not fetch live domains: {e}")

    print_json(
        {
            "status": status,
            "message": args.message,
            "code": args.code,
            "from_domain": from_domain,
            "to_domain": to_domain,
            "matched_cases": [
                {
                    "id": case.get("id"),
                    "summary": case.get("summary"),
                    "checks": case.get("checks"),
                    "fixes": case.get("fixes"),
                    "confidence": case.get("confidence"),
                }
                for case in clues
            ],
            "heuristic_warnings": heuristic_warnings,
            "heuristic_info": heuristic_info,
            "live_domains": live_domains,
        }
    )
    return 0


def command_request(args: argparse.Namespace) -> int:
    method = args.method.upper()
    query = parse_kv_pairs(args.query)
    extra_headers = parse_headers(args.header)
    base_url = os.environ.get("RESEND_BASE_URL", DEFAULT_BASE_URL)
    user_agent = os.environ.get("RESEND_USER_AGENT", DEFAULT_USER_AGENT)
    api_key = os.environ.get("RESEND_API_KEY")

    if method not in SAFE_METHODS and args.retries > 0 and not (args.idempotency_key or args.unsafe_retries):
        raise SystemExit(
            "Error: refusing to auto-retry a non-safe method without --idempotency-key or --unsafe-retries"
        )

    if args.paginate and method != "GET":
        raise SystemExit("Error: --paginate is only supported for GET requests")

    body_obj = load_json_body(args.json, args.json_file)
    body_bytes: Optional[bytes] = None
    if body_obj is not None:
        body_bytes = json.dumps(body_obj).encode("utf-8")

    headers: Dict[str, str] = {"User-Agent": user_agent}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if body_bytes is not None:
        headers["Content-Type"] = "application/json"
    if args.idempotency_key:
        headers["Idempotency-Key"] = args.idempotency_key
    headers.update(extra_headers)

    if args.require_auth and "Authorization" not in headers and not args.dry_run:
        raise SystemExit("Error: RESEND_API_KEY is required for request mode")

    url = build_url(base_url, args.path, query)
    prepared = {
        "method": method,
        "url": url,
        "headers": mask_headers(headers),
        "json_body": body_obj,
    }

    if args.dry_run:
        print_json({"dry_run": True, "request": prepared})
        return 0

    opener = urllib.request.build_opener()
    attempt = 0
    last_status: Optional[int] = None

    while True:
        attempt += 1
        req = urllib.request.Request(url, data=body_bytes, method=method, headers=headers)
        try:
            if args.paginate:
                paginated = maybe_paginate(
                    opener=opener,
                    method=method,
                    url=url,
                    headers=headers,
                    timeout=args.timeout,
                    page_limit=args.page_limit,
                )
                result = {
                    "ok": True,
                    "status": 200,
                    "request": prepared,
                    "pagination": paginated,
                }
                if args.output:
                    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
                    print_json({"ok": True, "status": 200, "output_file": str(args.output)})
                else:
                    print_json(result)
                return 0

            with opener.open(req, timeout=args.timeout) as resp:
                status = resp.getcode()
                last_status = status
                raw = resp.read()
                content_type = resp.headers.get("Content-Type", "")
                parsed_body = parse_response_body(content_type, raw)
                result = {
                    "ok": 200 <= status < 300,
                    "status": status,
                    "request": prepared,
                    "response": {
                        "content_type": content_type,
                        "body": parsed_body,
                    },
                }
                if args.include_headers:
                    result["response"]["headers"] = dict(resp.headers.items())

                if args.output:
                    if isinstance(parsed_body, dict) and "_binary_base64" in parsed_body and args.binary_output:
                        Path(args.binary_output).write_bytes(base64.b64decode(parsed_body["_binary_base64"]))
                        result["response"]["saved_binary_to"] = str(args.binary_output)
                    Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
                    print_json({"ok": result["ok"], "status": status, "output_file": str(args.output)})
                else:
                    print_json(result)
                return 0 if result["ok"] else 1

        except urllib.error.HTTPError as e:
            last_status = e.code
            raw = e.read()
            content_type = e.headers.get("Content-Type", "")
            parsed_body = parse_response_body(content_type, raw)
            error_result = {
                "ok": False,
                "status": e.code,
                "request": prepared,
                "response": {
                    "content_type": content_type,
                    "body": parsed_body,
                },
                "attempt": attempt,
            }
            if args.include_headers:
                error_result["response"]["headers"] = dict(e.headers.items())

            if should_retry(method, e.code, attempt, args.retries):
                retry_after = e.headers.get("Retry-After")
                if args.respect_retry_after and retry_after:
                    try:
                        sleep_for = max(float(retry_after), args.backoff)
                    except ValueError:
                        sleep_for = args.backoff
                else:
                    sleep_for = args.backoff
                print(
                    f"Retrying after HTTP {e.code} (attempt {attempt} of {args.retries + 1})...",
                    file=sys.stderr,
                )
                time.sleep(sleep_for)
                continue

            if args.output:
                Path(args.output).write_text(json.dumps(error_result, indent=2, ensure_ascii=False), encoding="utf-8")
                print_json({"ok": False, "status": e.code, "output_file": str(args.output)})
            else:
                print_json(error_result)
            return 1

        except urllib.error.URLError as e:
            if should_retry(method, None, attempt, args.retries):
                print(
                    f"Retrying after network error: {e.reason} (attempt {attempt} of {args.retries + 1})...",
                    file=sys.stderr,
                )
                time.sleep(args.backoff)
                continue
            print_json(
                {
                    "ok": False,
                    "status": last_status,
                    "request": prepared,
                    "error": {
                        "type": "network_error",
                        "message": str(e.reason),
                    },
                    "attempt": attempt,
                }
            )
            return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect, lint, diagnose, and call the bundled Resend API skill resources."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_catalog = subparsers.add_parser("catalog", help="List known endpoints")
    p_catalog.add_argument("--group", help="Filter by group/tag, e.g. Emails")
    p_catalog.add_argument("--method", help="Filter by HTTP method, e.g. POST")
    p_catalog.add_argument("--search", help="Free-text filter over group/path/summary")
    p_catalog.add_argument("--format", choices=["json", "table"], default="table")
    p_catalog.add_argument("--include-beta", action="store_true", help="Include beta/private-alpha notes")
    p_catalog.add_argument("--include-deprecated", action="store_true", help="Include deprecated endpoints")
    p_catalog.set_defaults(func=command_catalog)

    p_schema = subparsers.add_parser("schema", help="Show schema/parameter summary for an endpoint")
    p_schema.add_argument("method", help="HTTP method, e.g. POST")
    p_schema.add_argument("path", help="Endpoint path, e.g. /emails or /domains/{domain_id}")
    p_schema.set_defaults(func=command_schema)

    p_recommend = subparsers.add_parser("recommend", help="Recommend the right Resend primitive for a task")
    p_recommend.add_argument("task", help="Free-text task description")
    p_recommend.add_argument("--top", type=int, default=3, help="Number of routes to return")
    p_recommend.add_argument("--include-low-confidence", action="store_true", help="Include zero-score matches")
    p_recommend.set_defaults(func=command_recommend)

    p_lint = subparsers.add_parser("lint", help="Lint common payload mistakes for a specific endpoint")
    p_lint.add_argument("method", help="HTTP method")
    p_lint.add_argument("path", help="Endpoint path template, e.g. /emails or /contacts/{contact_id}/topics")
    p_lint.add_argument("--json", help="Inline JSON request body")
    p_lint.add_argument("--json-file", help="Path to a JSON request body")
    p_lint.add_argument("--header", action="append", default=[], help="Header as 'Name: value'")
    p_lint.add_argument("--idempotency-key", help="Add an Idempotency-Key header for linting")
    p_lint.add_argument("--surface", choices=["raw-rest", "sdk", "mcp", "cli", "unknown"], default="raw-rest")
    p_lint.set_defaults(func=command_lint)

    p_scaffold = subparsers.add_parser("scaffold", help="Print a scaffolded JSON payload or cURL command")
    p_scaffold.add_argument("name", nargs="?", help="Scaffold name, e.g. send-email-basic")
    p_scaffold.add_argument("--format", choices=["json", "curl"], default="json")
    p_scaffold.add_argument("--list", action="store_true", help="List available scaffolds")
    p_scaffold.set_defaults(func=command_scaffold)

    p_doctor = subparsers.add_parser("doctor", help="Diagnose a likely Resend failure")
    p_doctor.add_argument("--status", type=int, help="HTTP status code")
    p_doctor.add_argument("--message", help="Error message text")
    p_doctor.add_argument("--code", help="Error code text")
    p_doctor.add_argument("--from-address", help="from address involved in the failing request")
    p_doctor.add_argument("--to-address", help="to address involved in the failing request")
    p_doctor.add_argument("--verified-domain", help="Expected verified domain for exact-match comparisons")
    p_doctor.add_argument("--fetch-domains", action="store_true", help="Fetch live domains via GET /domains")
    p_doctor.add_argument("--timeout", type=float, default=30.0, help="Timeout for live checks")
    p_doctor.set_defaults(func=command_doctor)

    p_request = subparsers.add_parser("request", help="Make a live API request")
    p_request.add_argument("method", help="HTTP method")
    p_request.add_argument("path", help="Endpoint path")
    p_request.add_argument("--query", action="append", help="Query parameter as KEY=VALUE", default=[])
    p_request.add_argument("--header", action="append", help="Additional header as 'Name: value'", default=[])
    p_request.add_argument("--json", help="Inline JSON request body")
    p_request.add_argument("--json-file", help="Path to a JSON request body")
    p_request.add_argument("--idempotency-key", help="Idempotency-Key header value")
    p_request.add_argument("--timeout", type=float, default=30.0, help="Request timeout in seconds")
    p_request.add_argument("--retries", type=int, default=0, help="Retry count for 429/5xx/network errors")
    p_request.add_argument("--backoff", type=float, default=1.0, help="Base sleep between retries in seconds")
    p_request.add_argument("--respect-retry-after", dest="respect_retry_after", action="store_true", default=True, help="Use Retry-After when present (default: true)")
    p_request.add_argument("--no-respect-retry-after", dest="respect_retry_after", action="store_false", help="Ignore Retry-After and use fixed backoff")
    p_request.add_argument("--dry-run", action="store_true", help="Print the prepared request without sending it")
    p_request.add_argument("--paginate", action="store_true", help="Follow cursor pagination for GET list endpoints")
    p_request.add_argument("--page-limit", type=int, default=5, help="Max pages when --paginate is used")
    p_request.add_argument("--output", help="Write the structured result JSON to a file")
    p_request.add_argument("--binary-output", help="Decode and save binary response bytes to a file")
    p_request.add_argument("--include-headers", action="store_true", help="Include response headers in output")
    p_request.add_argument("--unsafe-retries", action="store_true", help="Allow retries for non-safe methods")
    p_request.add_argument("--no-auth-check", dest="require_auth", action="store_false", help="Allow unauthenticated dry runs")
    p_request.set_defaults(func=command_request, require_auth=True)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
