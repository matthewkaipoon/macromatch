#!/usr/bin/env python3
"""Bounded USDA FoodData Central API suitability audit for MacroMatch.

Stdlib only. No retries, no secrets in artifacts or output.
Designed for Python 3.10+ and Windows PowerShell / macOS / Linux.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API_BASE = "https://api.nal.usda.gov/fdc/v1"
DATA_TYPES = ("Foundation", "SR Legacy")
QUERIES = (
    "chicken breast", "salmon", "egg", "tofu",
    "lentils", "chickpeas", "oats", "rice",
    "broccoli", "spinach", "banana", "apple",
    "almonds", "yogurt", "potato", "beans",
)
SECOND_PAGE_QUERIES = {"chicken breast", "rice"}
NUTRIENTS = {
    "protein_g": (1003,),
    "fat_g": (1004,),
    "carbs_g": (1005,),
    "fiber_g": (1079,),
    "energy_kcal": (2048, 2047, 1008),
}
ESSENTIAL = ("energy_kcal", "protein_g", "fat_g", "carbs_g")
ALL_METRICS = ESSENTIAL + ("fiber_g",)
VERSION = "1.0.0"


def json_write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def csv_write(path: Path, rows, fieldnames) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def safe_number(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) else None


def nutrient_record(n):
    """Normalize nutrient metadata from full-detail and search response structures."""
    nested = n.get("nutrient") if isinstance(n.get("nutrient"), dict) else {}
    raw_id = nested.get("id", n.get("nutrientId"))
    try:
        nutrient_id = int(raw_id)
    except (ValueError, TypeError):
        nutrient_id = None
    return {
        "id": nutrient_id,
        "amount": safe_number(n.get("amount", n.get("value"))),
        "unit": str(nested.get("unitName", n.get("unitName", ""))).strip().lower().replace("μ", "µ"),
        "name": str(nested.get("name", n.get("nutrientName", ""))),
        "schema": "nested" if nested else "flat",
    }


def converted_value(item, target):
    """Convert compatible unit denominations, leaving unsupported units missing."""
    value = item["amount"]
    unit = item["unit"]
    if value is None:
        return None
    if target == "energy_kcal":
        if unit in ("kcal", "kilocalorie", "kilocalories"):
            return value
        if unit in ("kj", "kilojoule", "kilojoules"):
            return value / 4.184
        return None
    if unit in ("g", "gram", "grams"):
        return value
    if unit in ("mg", "milligram", "milligrams"):
        return value / 1000
    if unit in ("µg", "ug", "mcg", "microgram", "micrograms"):
        return value / 1_000_000
    return None


def normalize_description(value):
    base = unicodedata.normalize("NFKD", str(value or ""))
    base = "".join(c for c in base if not unicodedata.combining(c))
    return " ".join(re.findall(r"[a-z0-9]+", base.lower()))


def extract_food(food):
    """Derive macro fields from full-detail food JSON. No zero imputation."""
    nutrients = food.get("foodNutrients", [])
    nutrients = nutrients if isinstance(nutrients, list) else []
    parsed = [nutrient_record(n) for n in nutrients if isinstance(n, dict)]
    by_id = defaultdict(list)
    for nutrient in parsed:
        if nutrient["id"] is not None:
            by_id[nutrient["id"]].append(nutrient)
    vals = {}
    chosen_ids = {}
    flags = []
    missing = []
    for metric, choices in NUTRIENTS.items():
        selected, selected_id = None, None
        for nid in choices:
            candidates = [converted_value(item, metric) for item in by_id[nid]]
            candidates = [x for x in candidates if x is not None]
            if candidates:
                selected, selected_id = candidates[0], nid
                if max(candidates) - min(candidates) > 0.01:
                    flags.append(f"conflicting_values_{nid}")
                break
        vals[metric] = selected
        chosen_ids[metric] = selected_id
        if selected is None:
            missing.append(metric)
    if len([x for x in (2048, 2047, 1008) if any(converted_value(i, "energy_kcal") is not None for i in by_id[x])]) > 1:
        flags.append("multiple_energy_definitions")  # NOT inherently an error
    for metric in ("protein_g", "fat_g", "carbs_g", "fiber_g"):
        n = vals[metric]
        if n is not None and (n < 0 or n > 105):
            flags.append("out_of_range_" + metric)
    energy = vals["energy_kcal"]
    if energy is not None and (energy < 0 or energy > 1000):
        flags.append("out_of_range_energy")
    if all(vals[k] is not None for k in ("protein_g", "fat_g", "carbs_g")):
        if sum(vals[k] for k in ("protein_g", "fat_g", "carbs_g")) > 105:
            flags.append("macro_sum_over_105g")
    if vals["fiber_g"] is not None and vals["carbs_g"] is not None:
        if vals["fiber_g"] > vals["carbs_g"] + 2:
            flags.append("fiber_exceeds_carbs_by_2g")
    for metric, ids in NUTRIENTS.items():
        for nid in ids:
            for item in by_id[nid]:
                if item["amount"] is not None and converted_value(item, metric) is None:
                    flags.append("unexpected_unit_" + metric)
    flags = sorted(set(flags))
    fdc_id = food.get("fdcId")
    description = str(food.get("description") or "")
    dtype = str(food.get("dataType") or "UNKNOWN")
    return {
        "fdc_id": fdc_id,
        "description": description,
        "normalised_name": normalize_description(description),
        "data_type": dtype,
        "food_category": (food.get("foodCategory") if isinstance(food.get("foodCategory"), str)
                          else (food.get("foodCategory") or {}).get("description", "") if isinstance(food.get("foodCategory"), dict) else ""),
        "published_date": str(food.get("publicationDate") or food.get("publishedDate") or ""),
        "nutrient_items": len(parsed),
        "schema_nested_count": sum(x["schema"] == "nested" for x in parsed),
        "schema_flat_count": sum(x["schema"] == "flat" for x in parsed),
        **vals,
        "energy_nutrient_id": chosen_ids["energy_kcal"],
        "complete_core": all(vals[k] is not None for k in ESSENTIAL),
        "complete_all": all(vals[k] is not None for k in ALL_METRICS),
        "has_flags": bool(flags),
        "usable_core": all(vals[k] is not None for k in ESSENTIAL) and not any(f.startswith(("out_of_range_", "macro_sum_over", "conflicting_values_")) for f in flags),
        "usable_all": all(vals[k] is not None for k in ALL_METRICS) and not any(f.startswith(("out_of_range_", "macro_sum_over", "conflicting_values_", "fiber_exceeds")) for f in flags),
        "missing_fields": ";".join(missing),
        "flags": ";".join(flags),
    }


class APIError(Exception):
    def __init__(self, status, detail=""):
        super().__init__("API request failed")
        self.status = status
        self.detail = detail


class FDCClient:
    def __init__(self, api_key, delay, timeout, max_requests):
        self.api_key = api_key
        self.delay = delay
        self.timeout = timeout
        self.max_requests = max_requests
        self.count = 0
        self.last_request_at = 0.0
        self.last_remaining = None
        self.request_log = []

    def post(self, path, payload, label):
        if self.count >= self.max_requests:
            raise APIError("LOCAL_LIMIT", "Local maximum request cap reached")
        since = time.monotonic() - self.last_request_at
        if self.count and since < self.delay:
            time.sleep(self.delay - since)
        # API key stays in a request URL only; URL is NEVER printed, logged or persisted.
        url = API_BASE + path + "?" + urlencode({"api_key": self.api_key})
        encoded = json.dumps(payload).encode("utf-8")
        req = Request(url, data=encoded, method="POST", headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "MacroMatch-USDA-Suitability-Audit/1.0"})
        self.count += 1
        self.last_request_at = time.monotonic()
        try:
            with urlopen(req, timeout=self.timeout) as response:
                body = response.read(25_000_000)
                status = response.status
                remaining = response.headers.get("X-RateLimit-Remaining")
        except HTTPError as e:
            # Do not print 'e': it might contain the URL and the secret query parameter.
            try:
                e.close()
            except Exception:
                pass
            self.request_log.append({"label": label, "http_status": e.code})
            raise APIError(e.code, "HTTP failure. Check key, limits, or service status.") from None
        except (URLError, TimeoutError, OSError) as e:
            self.request_log.append({"label": label, "http_status": "NETWORK_ERROR"})
            raise APIError("NETWORK", type(e).__name__) from None
        self.last_remaining = remaining
        self.request_log.append({"label": label, "http_status": status, "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()})
        try:
            return json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise APIError("BAD_JSON", "API response was not valid JSON") from None


def choose_samples(buckets, max_foods, per_bucket):
    """Round-robin across search-term/type buckets to reduce source skew."""
    ordered = {key: value[:per_bucket] for key, value in buckets.items()}
    selected_ids, provenance = [], defaultdict(list)
    seen = set()
    for hits in itertools.zip_longest(*ordered.values()):
        for key, hit in zip(ordered, hits):
            if hit is None:
                continue
            fdc_id = hit.get("fdcId")
            if isinstance(fdc_id, int) and fdc_id not in seen:
                seen.add(fdc_id)
                selected_ids.append(fdc_id)
                provenance[fdc_id].append(key)
            elif isinstance(fdc_id, int):
                provenance[fdc_id].append(key)
            if len(selected_ids) >= max_foods:
                return selected_ids, provenance
    return selected_ids, provenance


def pct(num, den):
    return round(100 * num / den, 1) if den else None


def summarise(foods, search_summary, search_errors, detail_errors, manifest, client):
    source_counts = Counter(f["data_type"] for f in foods)
    groups = {}
    for source in sorted(source_counts):
        subgroup = [f for f in foods if f["data_type"] == source]
        groups[source] = {
            "n": len(subgroup),
            "complete_core_pct": pct(sum(f["complete_core"] for f in subgroup), len(subgroup)),
            "complete_with_fiber_pct": pct(sum(f["complete_all"] for f in subgroup), len(subgroup)),
            "usable_with_fiber_pct": pct(sum(f["usable_all"] for f in subgroup), len(subgroup)),
            "nutrient_presence_pct": {k: pct(sum(f[k] is not None for f in subgroup), len(subgroup)) for k in ALL_METRICS},
            "energy_nutrient_id_counts": dict(Counter(str(f["energy_nutrient_id"]) for f in subgroup)),
            "median_nutrient_count": sorted(f["nutrient_items"] for f in subgroup)[len(subgroup)//2] if subgroup else None,
        }
    collisions = defaultdict(list)
    for food in foods:
        collisions[food["normalised_name"]].append(food)
    name_collisions = [v for k, v in collisions.items() if k and len(set(f["fdc_id"] for f in v)) > 1]
    name_collisions.sort(key=lambda v: (-len(v), v[0]["normalised_name"]))
    collisions_preview = [
        {"name": v[0]["normalised_name"], "records": [{"fdc_id": f["fdc_id"], "source": f["data_type"]} for f in v[:8]]}
        for v in name_collisions[:12]
    ]
    flag_counts = Counter(x for f in foods for x in f["flags"].split(";") if x)
    keywords = {k: [] for k in QUERIES}
    for f in foods:
        for term in QUERIES:
            if f.get("search_terms") and term in f["search_terms"].split(";"):
                keywords[term].append(f)
    coverage = {}
    for term, matches in keywords.items():
        coverage[term] = {
            "sampled": len(matches),
            "usable_core": sum(f["usable_core"] for f in matches),
            "usable_with_fiber": sum(f["usable_all"] for f in matches),
            "examples": [{"fdc_id": f["fdc_id"], "description": f["description"], "data_type": f["data_type"]} for f in matches if f["usable_all"]][:2],
        }
    by_source_shapes = {k: {
        "nested_nutrient_entries": sum(f["schema_nested_count"] for f in foods if f["data_type"] == k),
        "flat_nutrient_entries": sum(f["schema_flat_count"] for f in foods if f["data_type"] == k),
    } for k in sorted(source_counts)}
    usable_all = [f for f in foods if f["usable_all"]]
    enough = len(foods) >= 80 and len(usable_all) >= 60 and sum(1 for q in coverage.values() if q["usable_with_fiber"] >= 2) >= 8
    return {
        "audit_version": VERSION,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "sampling_limitations": [
            "Keyword-search sample, NOT a random representative sample of all USDA foods.",
            "Source types filtered to Foundation and SR Legacy.",
            "Search result ranking and query choice can bias coverage and collision counts.",
            "Exact/near-identical names are review candidates, NOT proven duplicates.",
            "Nutrient completeness is not proof of analytical accuracy.",
            "Per-100g comparisons need like-for-like preparation and edible portion.",
            "Nutrition relevance and scoring clinical validity are not established by this audit.",
            "Presence of 2047/2048 energy alternatives is not itself a data defect.",
        ],
        "sampling": manifest,
        "requests_made": client.count,
        "last_reported_rate_limit_remaining": client.last_remaining,
        "search_errors": search_errors,
        "detail_errors": detail_errors,
        "successful_searches": len(search_summary),
        "sampled_detail_records": len(foods),
        "unique_fdc_ids": len(set(f["fdc_id"] for f in foods)),
        "by_data_type": groups,
        "overall": {
            "complete_core_count": sum(f["complete_core"] for f in foods),
            "complete_core_pct": pct(sum(f["complete_core"] for f in foods), len(foods)),
            "complete_with_fiber_count": sum(f["complete_all"] for f in foods),
            "complete_with_fiber_pct": pct(sum(f["complete_all"] for f in foods), len(foods)),
            "usable_with_fiber_count": len(usable_all),
            "usable_with_fiber_pct": pct(len(usable_all), len(foods)),
            "missing_counts": {k: sum(f[k] is None for f in foods) for k in ALL_METRICS},
            "flag_counts": dict(flag_counts.most_common()),
            "name_collision_groups": len(name_collisions),
            "name_collision_groups_preview": collisions_preview,
            "nutrient_schema_by_source": by_source_shapes,
            "source_count": len(groups),
        },
        "query_coverage": coverage,
        "preliminary_gate": {
            "passed_exploratory_sample_threshold": enough,
            "criteria": "At least 80 sampled foods, 60 usable with fibre, and 8 queries with >=2 usable foods; arbitrary exploratory threshold, not proof of fitness for production.",
        },
    }


def render_text(summary):
    out = []
    def emit(x=""):
        out.append(str(x))
    emit("MACROMATCH — USDA FOODDATA CENTRAL API AUDIT")
    emit("=" * 57)
    emit("UTC: " + summary["timestamp_utc"])
    emit("Requests made: " + str(summary["requests_made"]))
    emit("Remaining reported quota: " + str(summary["last_reported_rate_limit_remaining"]))
    emit("Successful searches: " + str(summary["successful_searches"]))
    emit("Search/detail failures: %d/%d" % (len(summary["search_errors"]), len(summary["detail_errors"])))
    emit("Details returned: " + str(summary["sampled_detail_records"]))
    emit("Unique FDC IDs: " + str(summary["unique_fdc_ids"]))
    emit()
    emit("1. MACRO COVERAGE (using detailed /foods records)")
    for src, v in summary["by_data_type"].items():
        emit("  %-12s n=%3d  core=%5s%%  core+fibre=%5s%%  usable(all)=%5s%%" % (src, v["n"], v["complete_core_pct"], v["complete_with_fiber_pct"], v["usable_with_fiber_pct"]))
        emit("     nutrient presence %: " + ", ".join("%s=%s" % (k, x) for k, x in v["nutrient_presence_pct"].items()))
        emit("     chosen energy IDs: " + str(v["energy_nutrient_id_counts"]))
    overall = summary["overall"]
    emit("  OVERALL: n=%d, complete core=%s%%, complete with fibre=%s%%, usable with fibre=%s%%" % (
        summary["sampled_detail_records"], overall["complete_core_pct"], overall["complete_with_fiber_pct"], overall["usable_with_fiber_pct"]))
    emit("  Missing counts: " + str(overall["missing_counts"]))
    emit()
    emit("2. TRANSFORMATION / QUALITY EVIDENCE")
    emit("  Nutrient schema by source: " + str(overall["nutrient_schema_by_source"]))
    emit("  Flag counts (candidate issues, not all proven errors): " + str(overall["flag_counts"]))
    emit("  Identical normalised-name groups: " + str(overall["name_collision_groups"]))
    for item in overall["name_collision_groups_preview"][:5]:
        emit("   - %s: %s" % (item["name"], ", ".join(str(x["fdc_id"]) + "/" + str(x["source"]) for x in item["records"])))
    emit()
    emit("3. INGREDIENT TERM COVERAGE (sample-dependent)")
    for term, values in summary["query_coverage"].items():
        emit("  %-17s sampled=%-3d usable core=%-3d usable with fibre=%-3d" % (term, values["sampled"], values["usable_core"], values["usable_with_fiber"]))
    emit()
    emit("4. DECISION GATE")
    gate = summary["preliminary_gate"]
    emit("  Exploratory threshold met: " + ("YES" if gate["passed_exploratory_sample_threshold"] else "NO"))
    emit("  " + gate["criteria"])
    emit("  This is NOT a production or scientific suitability verdict.")
    emit()
    emit("5. LIMITATIONS")
    for caveat in summary["sampling_limitations"]:
        emit("  - " + caveat)
    emit()
    emit("SEND ME: audit_summary.txt (whole text), and optionally foods_audit.csv for detailed review.")
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="audit_output", help="Output directory; default ./audit_output")
    parser.add_argument("--max-foods", type=int, default=192, help="Hard cap on unique detailed foods (1..300)")
    parser.add_argument("--per-bucket", type=int, default=6, help="Foods per query and source before global cap (1..15)")
    parser.add_argument("--page-size", type=int, default=25, help="Search results per page (10..50)")
    parser.add_argument("--second-pages", action="store_true", help="Request page 2 for chicken breast and rice (adds 4 requests)")
    parser.add_argument("--probe", action="store_true", help="Exactly ONE small search request to check API access; no full audit")
    parser.add_argument("--max-requests", type=int, default=70, help="Hard request cap (1..100)")
    parser.add_argument("--delay", type=float, default=0.25, help="Minimum gap between requests, seconds (>=0.2)")
    parser.add_argument("--timeout", type=int, default=20, help="Timeout per request (5..60 seconds)")
    parser.add_argument("--skip-raw", action="store_true", help="Do not save raw API response JSON (not recommended for final project)")
    args = parser.parse_args(argv)
    if not (1 <= args.max_foods <= 300 and 1 <= args.per_bucket <= 15 and 10 <= args.page_size <= 50 and 1 <= args.max_requests <= 100 and args.delay >= 0.2 and 5 <= args.timeout <= 60):
        parser.error("Argument outside allowed bounds; see --help")
    api_key = os.environ.get("USDA_API_KEY", "").strip()
    if not api_key or api_key.upper() == "DEMO_KEY":
        print("ERROR: Set USDA_API_KEY to your own free data.gov key; DEMO_KEY is too rate-limited for this audit.", file=sys.stderr)
        return 2
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    client = FDCClient(api_key, args.delay, args.timeout, args.max_requests)
    if args.probe:
        try:
            response = client.post("/foods/search", {
                "query": "chicken breast", "dataType": ["SR Legacy"], "pageNumber": 1, "pageSize": 3
            }, "probe|chicken breast|SR Legacy|p1")
            if not isinstance(response, dict) or not isinstance(response.get("foods"), list):
                print("PROBE FAILED: response was JSON but not the expected search structure.")
                return 1
            result = {
                "status": "OK", "requests_made": client.count,
                "foods_returned": len(response["foods"]),
                "total_hits_reported": response.get("totalHits"),
                "sample_ids": [f.get("fdcId") for f in response["foods"] if isinstance(f, dict)],
                "remaining_quota_reported": client.last_remaining,
                "raw_response_sha256": client.request_log[0].get("sha256"),
            }
            json_write(out / "probe_result.json", result)
            print("PROBE SUCCEEDED — exactly one request; no API key was saved.")
            print(json.dumps(result, indent=2))
            print("Next step: run without --probe for the full data-quality audit.")
            return 0
        except APIError as e:
            print("PROBE FAILED — status:", e.status, "reason:", e.detail)
            print("No automatic retry attempted. The API key was not printed.")
            return 1
    buckets = {}
    search_summary = []
    search_errors = []
    detail_errors = []
    manifest = {
        "search_terms": list(QUERIES), "data_types": list(DATA_TYPES),
        "max_foods": args.max_foods, "per_bucket": args.per_bucket,
        "page_size": args.page_size, "second_pages": args.second_pages,
        "sample_strategy": "Round-robin unique FDC IDs drawn from keyword x data type searches, not random",
    }
    aborted = False
    print("Starting bounded searches (no retries; API key never written to disk)...", flush=True)
    for term in QUERIES:
        for source in DATA_TYPES:
            label = f"search|{term}|{source}|p1"
            hits = []
            for page in ([1, 2] if args.second_pages and term in SECOND_PAGE_QUERIES else [1]):
                label = f"search|{term}|{source}|p{page}"
                payload = {"query": term, "dataType": [source], "pageSize": args.page_size, "pageNumber": page}
                try:
                    result = client.post("/foods/search", payload, label)
                except APIError as e:
                    search_errors.append({"label": label, "status": e.status, "reason": e.detail})
                    print("  Stopping searches due to request failure:", label, "status:", e.status, flush=True)
                    aborted = True
                    break
                if not isinstance(result, dict) or not isinstance(result.get("foods"), list):
                    search_errors.append({"label": label, "status": "INVALID_RESPONSE_SHAPE"})
                    aborted = True
                    break
                batch = result["foods"]
                hits.extend(batch)
                search_summary.append({"query": term, "data_type_requested": source, "page": page,
                                       "total_hits_reported": result.get("totalHits"),
                                       "foods_returned": len(batch),
                                       "search_nutrient_schema_nested": sum(any(isinstance(n, dict) and isinstance(n.get("nutrient"), dict) for n in f.get("foodNutrients", [])) for f in batch),
                                       "search_nutrient_schema_flat": sum(any(isinstance(n, dict) and "nutrientId" in n for n in f.get("foodNutrients", [])) for f in batch)})
                if not args.skip_raw:
                    slug = normalize_description(term).replace(" ", "_")
                    json_write(out / "raw_api" / f"search_{slug}_{source.replace(' ', '_')}_p{page}.json", result)
            buckets[(term, source)] = hits
            if aborted:
                break
        if aborted:
            break
    selected, provenance = choose_samples(buckets, args.max_foods, args.per_bucket)
    print(f"Search calls completed: {len(search_summary)}; selected {len(selected)} distinct FDC IDs for full detail.", flush=True)
    foods = []
    raw_id_count = 0
    if not aborted:
        for part_no, start in enumerate(range(0, len(selected), 20), 1):
            ids = selected[start:start+20]
            label = f"detail_batch_{part_no}"
            try:
                result = client.post("/foods", {"fdcIds": ids, "format": "full"}, label)
            except APIError as e:
                detail_errors.append({"label": label, "status": e.status, "reason": e.detail})
                print("  Stopping details due to request failure:", label, "status:", e.status, flush=True)
                break
            if not isinstance(result, list):
                detail_errors.append({"label": label, "status": "INVALID_RESPONSE_SHAPE"})
                break
            if not args.skip_raw:
                json_write(out / "raw_api" / f"details_batch_{part_no:03}.json", result)
            for f in result:
                if not isinstance(f, dict):
                    continue
                extracted = extract_food(f)
                if not isinstance(extracted["fdc_id"], int):
                    continue
                raw_id_count += 1
                extracted["search_terms"] = ";".join(sorted(set(t for t, s in provenance.get(extracted["fdc_id"], []))))
                foods.append(extracted)
    summary = summarise(foods, search_summary, search_errors, detail_errors, manifest, client)
    summary["completion"] = "partial" if aborted or detail_errors or search_errors or raw_id_count < len(selected) else "complete"
    summary["selected_detail_ids"] = len(selected)
    json_write(out / "audit_summary.json", summary)
    (out / "audit_summary.txt").write_text(render_text(summary) + "\nCompletion status: " + summary["completion"] + "\n", encoding="utf-8")
    csv_write(out / "foods_audit.csv", foods, [
        "fdc_id", "description", "normalised_name", "data_type", "food_category", "published_date", "search_terms",
        "energy_kcal", "protein_g", "fat_g", "carbs_g", "fiber_g", "energy_nutrient_id", "nutrient_items",
        "schema_nested_count", "schema_flat_count", "complete_core", "complete_all", "usable_core", "usable_all",
        "missing_fields", "has_flags", "flags",
    ])
    csv_write(out / "search_audit.csv", search_summary, ["query", "data_type_requested", "page", "total_hits_reported", "foods_returned", "search_nutrient_schema_nested", "search_nutrient_schema_flat"])
    json_write(out / "request_manifest.json", {
        "audit_version": VERSION, "date_utc": summary["timestamp_utc"], "query_spec": manifest,
        "requests": client.request_log, "selected_fdc_ids": selected,
        "note": "No API key or request URL is stored; SHA-256 hashes refer to raw HTTP response bodies."
    })
    print("\n" + render_text(summary), flush=True)
    print("Completion status:", summary["completion"])
    print("Saved to:", out)
    print("Please paste audit_summary.txt here. Attach foods_audit.csv only if useful for investigating anomalies.")
    return 0 if summary["completion"] == "complete" and foods else 1


if __name__ == "__main__":
    sys.exit(main())
