"""Read-only CLI for structural and semantic policy research validation."""

import argparse
import json
import sys
from pathlib import Path

from policy_research_v2 import ROOT, load_news_index, load_profiles, load_topic_membership, read_json, validate_artifact, validate_input_fingerprints, snapshot_warnings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--news-index", type=Path, default=ROOT / "資料/moenv_news_index.jsonl")
    parser.add_argument("--membership", type=Path, default=ROOT / "資料/moenv_news_keywords.csv")
    parser.add_argument("--profiles", type=Path, default=ROOT / "資料/moenv_keyword_database.json")
    parser.add_argument("--manifest", type=Path, default=ROOT / "資料/moenv_news_manifest.json")
    parser.add_argument("--fixture-mode", action="store_true", help="Use independent synthetic canonical fixtures; never a production gate")
    parser.add_argument("--publication", action="store_true", help="Require research_summary; automatic with real canonical inputs")
    args = parser.parse_args(argv)
    try:
        artifact = read_json(args.artifact)
        if args.fixture_mode:
            inputs = read_json(ROOT / "tests/fixtures/policy_research_v2.canonical.json")
            inputs["membership"] = {k: set(v) for k, v in inputs["membership"].items()}
            print("FIXTURE_MODE: synthetic canonical dataset, not production validation")
        else:
            inputs = {"news_index": load_news_index(args.news_index), "membership": load_topic_membership(args.membership), "profiles": load_profiles(args.profiles), "manifest": read_json(args.manifest)}
        issues = validate_artifact(artifact, **inputs, publication=args.publication or not args.fixture_mode)
        if not args.fixture_mode:
            markdown = (ROOT / artifact["meta"]["source_markdown"]).resolve()
            if not markdown.is_relative_to(ROOT.resolve()):
                raise ValueError("Source Markdown must stay within the vault")
            paths = {"news_index": args.news_index, "membership": args.membership, "profiles": args.profiles, "manifest": args.manifest, "source_markdown": markdown}
            issues.extend(validate_input_fingerprints(artifact, paths))
            issues.extend(snapshot_warnings(ROOT, inputs["news_index"]))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR INPUT $: {exc}")
        return 2
    for issue in issues:
        print(f"{issue.severity.upper()} {issue.code} {issue.path}: {issue.message}")
    errors = sum(i.severity == "error" for i in issues)
    warnings = sum(i.severity == "warning" for i in issues)
    print(f"{'FAIL' if errors else 'PASS'}: {errors} errors, {warnings} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
