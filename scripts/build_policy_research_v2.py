"""Compile authored claims and canonical statistics; no website or index writes."""

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from policy_research_v2 import (
    ROOT, compile_artifact, input_fingerprints, load_news_index, load_profiles,
    load_topic_membership, read_json, read_markdown_metadata, snapshot_warnings,
    validate_artifact,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authored", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    temporary = None
    try:
        authored = read_json(args.authored)
        output = args.output.resolve()
        if not output.is_relative_to((ROOT / "03_政策研究/研究資料").resolve()):
            raise ValueError("Output must stay in the research artifact directory")
        if output.name != authored["research_id"] + ".v2.json":
            raise ValueError("Output name must match research_id.v2.json")
        markdown = (ROOT / authored["source_markdown"]).resolve()
        if not markdown.is_relative_to((ROOT / "03_政策研究/研究報告").resolve()):
            raise ValueError("Source Markdown must stay in the research report directory")
        paths = {
            "news_index": ROOT / "資料/moenv_news_index.jsonl",
            "membership": ROOT / "資料/moenv_news_keywords.csv",
            "profiles": ROOT / "資料/moenv_keyword_database.json",
            "manifest": ROOT / "資料/moenv_news_manifest.json",
            "source_markdown": markdown,
        }
        hashes = input_fingerprints(paths)
        inputs = {"news_index": load_news_index(paths["news_index"]), "membership": load_topic_membership(paths["membership"]), "profiles": load_profiles(paths["profiles"]), "manifest": read_json(paths["manifest"])}
        artifact = compile_artifact(authored, **inputs, markdown_metadata=read_markdown_metadata(markdown), generated_at=datetime.now(timezone.utc).isoformat(), input_sha256=hashes)
        issues = validate_artifact(artifact, **inputs) + snapshot_warnings(ROOT, inputs["news_index"])
        for issue in issues:
            print(f"{issue.severity.upper()} {issue.code} {issue.path}: {issue.message}")
        if any(i.severity == "error" for i in issues):
            print("FAIL: no artifact written")
            return 1
        if hashes != input_fingerprints(paths):
            raise ValueError("Inputs changed during compilation; retry with a stable snapshot")
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(artifact, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        temporary.replace(output)
        temporary = None
        print(f"PASS: wrote {output}; human acceptance pending")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR INPUT $: {exc}")
        return 2
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
