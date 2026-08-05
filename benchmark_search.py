#!/usr/bin/env python3
"""Benchmark the DataLad registry search endpoint over HTTP.

Hits the live /api/v2/dataset-urls?search= endpoint and measures response times.

Usage:
  python benchmark_search.py
  python benchmark_search.py --url https://registry.datalad.org
  python benchmark_search.py --iterations 50
  python benchmark_search.py --query "datalad"
"""

import argparse
import datetime
import os
import statistics
import time
import urllib.parse
import urllib.request
import json
from io import StringIO
from textwrap import dedent

DEFAULT_REGISTRY_URL = "https://registry.datalad.org"

BENCHMARK_QUERIES = [
    ("simple_word", "datalad"),
    ("field_url", "url:example"),
    ("field_ds_id", "ds_id:844c"),
    ("or_two_words", "datalad OR handbook"),
    ("and_two_words", "datalad AND handbook"),
    ("implicit_and", "datalad handbook"),
    ("not_expr", "NOT url:handbook"),
    ("complex_bool", "datalad AND NOT url:handbook"),
    ("parenthesized", "datalad AND (NOT handbook)"),
    ("metadata_word", "meta1value"),
    ("metadata_field", 'metadata:"value"'),
    ("metadata_extractor", 'metadata[metalad_core]:"value"'),
    ("complex_combined", "(url:handbook OR metadata[metalad_core]:value) AND ds_id:844c"),
    ("long_substring", "www.example.com"),
    ("uuid_substring", "2a0b7b7b-a984"),
    ("empty_search", ""),
]


def fetch(url):
    """Fetch a URL and return (status_code, parsed_json, elapsed_seconds)."""
    start = time.perf_counter()
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read())
            elapsed = time.perf_counter() - start
            return resp.status, body, elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - start
        return e.code, None, elapsed
    except Exception:
        elapsed = time.perf_counter() - start
        return 0, None, elapsed


def benchmark(base_url, iterations, queries, log):
    def out(s=""):
        print(s)
        log.write(s + "\n")

    out(f"\n=== Search Endpoint Benchmark: {base_url} ===")
    out(f"    Iterations per query: {iterations}\n")
    out(f"  {'Name':<30s} {'Mean':>10s} {'Median':>10s} {'p95':>10s} {'Min':>10s} {'Max':>10s} {'Status':>7s} {'Rows':>6s}")
    out("  " + "-" * 101)

    api_url = base_url.rstrip("/") + "/api/v2/dataset-urls"

    for name, query in queries:
        params = {"per_page": "20"}
        if query:
            params["search"] = query
        url = api_url + "?" + urllib.parse.urlencode(params)

        # Warmup
        for _ in range(2):
            fetch(url)

        times = []
        last_status = 0
        last_rows = 0
        for _ in range(iterations):
            status, body, elapsed = fetch(url)
            times.append(elapsed)
            last_status = status
            if body:
                last_rows = len(body.get("dataset_urls", []))

        times.sort()
        mean = statistics.mean(times) * 1000
        median = statistics.median(times) * 1000
        p95 = times[int(len(times) * 0.95)] * 1000
        mn = times[0] * 1000
        mx = times[-1] * 1000

        out(f"  {name:<30s} {mean:>8.1f}ms {median:>8.1f}ms {p95:>8.1f}ms {mn:>8.1f}ms {mx:>8.1f}ms {last_status:>7d} {last_rows:>6d}")


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark the DataLad registry search endpoint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent("""\
            Examples:
              python benchmark_search.py
              python benchmark_search.py --url https://registry.datalad.org
              python benchmark_search.py --iterations 50
              python benchmark_search.py --query "datalad handbook"
        """),
    )
    parser.add_argument(
        "--url", default=DEFAULT_REGISTRY_URL,
        help=f"Registry base URL (default: {DEFAULT_REGISTRY_URL})",
    )
    parser.add_argument(
        "--iterations", "--iter", type=int, default=20,
        help="Number of iterations per query (default: 20)",
    )
    parser.add_argument(
        "--query", type=str, default=None,
        help="Run a single query instead of the full suite",
    )
    args = parser.parse_args()

    log = StringIO()
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def out(s=""):
        print(s)
        log.write(s + "\n")

    out(f"Benchmark run: {timestamp}")
    out(f"Registry: {args.url}")
    out(f"Iterations: {args.iterations}")

    if args.query:
        queries = [("custom", args.query)]
    else:
        queries = BENCHMARK_QUERIES

    benchmark(args.url, args.iterations, queries, log)

    out("\nDone.")

    # Write log file
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "benchmark-logs")
    os.makedirs(log_dir, exist_ok=True)
    log_filename = datetime.datetime.now().strftime("benchmark_%Y%m%d_%H%M%S.log")
    log_path = os.path.join(log_dir, log_filename)
    with open(log_path, "w") as f:
        f.write(log.getvalue())
    print(f"\nResults written to: {log_path}")


if __name__ == "__main__":
    main()
