import csv
import datetime as dt
import json
import os
import uuid
from pathlib import Path


FIELDS = (
    "provider", "record_type", "title", "url",
    "relevance_label", "evidence", "identity_verified"
)


def make_rows(result):
    rows = []

    # Preserve actual public search candidates.
    for candidate in result.get("retrieved_candidates", []):
        if isinstance(candidate, dict):
            rows.append(dict(candidate))

    # Export registration fields individually.
    rdap = result.get("domain_registration") or {}
    if isinstance(rdap, dict):
        source = str(rdap.get("source", ""))

        for key in (
            "domain", "registry_id", "registrar",
            "created", "updated", "expires"
        ):
            value = rdap.get(key)
            if value:
                rows.append({
                    "provider": "RDAP",
                    "record_type": "domain registration",
                    "title": key,
                    "url": source,
                    "evidence": str(value),
                    "identity_verified": False
                })

        for ns in rdap.get("nameservers", []):
            rows.append({
                "provider": "RDAP",
                "record_type": "nameserver",
                "title": str(ns),
                "url": source,
                "evidence": "Published nameserver",
                "identity_verified": False
            })

        for status in rdap.get("domain_statuses", []):
            rows.append({
                "provider": "RDAP",
                "record_type": "domain status",
                "title": str(status),
                "url": source,
                "evidence": "Published registration status",
                "identity_verified": False
            })

    # Preserve useful diagnostic information.
    for key in (
        "status", "indexed_total", "excluded_irrelevant",
        "duplicate_entries", "queries_completed",
        "raw_entries_seen"
    ):
        if key in result:
            rows.append({
                "provider": "BLACKTHORN",
                "record_type": "search diagnostic",
                "title": key,
                "evidence": str(result[key])
            })

    # Keep search shortcuts separate from findings.
    for name, url in result.get("sources", {}).items():
        rows.append({
            "provider": "PUBLIC SEARCH REFERENCE",
            "record_type": "research link only",
            "title": str(name),
            "url": str(url),
            "evidence": "Not a retrieved finding"
        })

    # Preserve public provider failures as independent export records.
    for failure in result.get("provider_errors", []):
        rows.append({"provider":"BLACKTHORN", "record_type":"provider diagnostic",
                     "title":"Provider request failed", "evidence":str(failure),
                     "identity_verified":False})
    for provider in result.get("providers_attempted", []):
        rows.append({"provider":"BLACKTHORN", "record_type":"provider diagnostic",
                     "title":"Provider attempted", "evidence":str(provider)})

    # BLACKTHORN VEILMAIL STRUCTURED DNS EXPORT v1
    # Public DNS evidence is distinct from mailbox verification.
    dns_records = result.get("records", {})
    if result.get("module") == 3 and isinstance(dns_records, dict):
        dns_source = str(result.get("source", ""))
        dns_provider = str(result.get("provider", "PUBLIC DNS"))
        domain = str(result.get("email_domain", ""))
        for kind in ("MX", "SPF", "DMARC"):
            values = dns_records.get(kind, [])
            if not isinstance(values, list):
                continue
            for value in values:
                if not isinstance(value, str) or not value.strip():
                    continue
                rows.append({
                    "provider": dns_provider,
                    "record_type": "public mail DNS " + kind,
                    "title": domain if kind != "DMARC" else "_dmarc." + domain,
                    "url": dns_source,
                    "relevance_label": "public DNS observation; mailbox unverified",
                    "evidence": value,
                    "identity_verified": False
                })

    # Preserve other module outputs when no structured rows exist.
    if not rows:
        for key, value in result.items():
            if key in ("retrieved_candidates", "sources"):
                continue
            rows.append({
                "provider": "BLACKTHORN MODULE",
                "record_type": "local module result",
                "title": str(key),
                "evidence": json.dumps(
                    value, ensure_ascii=False, default=str
                )
            })

    return rows


def write_dump(module, query, result, out):
    folder = Path(out).expanduser()
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)

    stamp = (
        dt.datetime.now(dt.timezone.utc)
        .strftime("%Y%m%dT%H%M%S%f")
        + "-" + uuid.uuid4().hex[:6]
    )

    files = [
        folder / ("BLACKTHORN-" + stamp + ext)
        for ext in (".json", ".jsonl", ".csv")
    ]

    rows = make_rows(result)

    def secure(path):
        fd = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600
        )
        return os.fdopen(
            fd, "w", encoding="utf-8", newline=""
        )

    # Full original result preserved.
    with secure(files[0]) as f:
        json.dump(
            {"query": query, "module": module, "results": result},
            f, indent=2, ensure_ascii=False
        )

    # Structured JSON Lines.
    with secure(files[1]) as f:
        for row in rows:
            f.write(json.dumps(
                row, ensure_ascii=False, default=str
            ) + "\n")

    # Spreadsheet-safe CSV.
    with secure(files[2]) as f:
        writer = csv.DictWriter(
            f, fieldnames=FIELDS, extrasaction="ignore"
        )
        writer.writeheader()

        for row in rows:
            safe = {}
            for key in FIELDS:
                value = row.get(key, "")
                if value is None:
                    value = ""
                if isinstance(value, (list, dict)):
                    value = json.dumps(value, ensure_ascii=False)
                value = str(value)
                if value.lstrip().startswith(("=", "+", "-", "@")):
                    value = "'" + value
                safe[key] = value
            writer.writerow(safe)

    return files
