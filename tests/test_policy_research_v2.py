import json
import copy
import importlib
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "policy_research_v2.schema.json"
FIXTURES = ROOT / "tests" / "fixtures"


def fixture():
    return json.loads((FIXTURES / "policy_research_v2.valid.json").read_text(encoding="utf-8"))


class PolicyResearchV2SchemaTests(unittest.TestCase):
    def test_schema_file_exists_and_is_draft_2020_12(self):
        self.assertTrue(SCHEMA.is_file(), "Research V2 schema is not implemented")
        data = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(data["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(data["properties"]["schema_version"]["const"], "2.0")

    def test_valid_fixture_and_strict_structure(self):
        from jsonschema import Draft202012Validator, FormatChecker
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        self.assertEqual(list(validator.iter_errors(fixture())), [])
        for field in schema["required"]:
            bad = fixture()
            del bad[field]
            self.assertFalse(validator.is_valid(bad), field)
        for mutate in (
            lambda a: a.update(unexpected=True),
            lambda a: a["key_metrics"][0].update(value="50"),
            lambda a: a["key_metrics"][0].update(source_ids=[]),
            lambda a: a["key_events"][0].update(date="2024-02-30"),
            lambda a: a["topic"].update(unexpected=True),
            lambda a: a["sources"][0].update(url="not a URL"),
        ):
            bad = fixture()
            mutate(bad)
            self.assertFalse(validator.is_valid(bad))


class CanonicalLoaderTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT / "scripts/policy_research_v2.py").is_file(), "Canonical helpers not implemented")
        self.module = importlib.import_module("scripts.policy_research_v2")
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / "tests")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "input"

    def test_load_news_index_preserves_string_news_id(self):
        self.path.write_text('{"news_id":"00123"}\n', encoding="utf-8")
        self.assertIn("00123", self.module.load_news_index(self.path))

    def test_duplicate_news_id_raises(self):
        self.path.write_text('{"news_id":"00123"}\n' * 2, encoding="utf-8")
        with self.assertRaises(ValueError):
            self.module.load_news_index(self.path)

    def test_numeric_news_id_is_rejected(self):
        self.path.write_text('{"news_id":123}\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.module.load_news_index(self.path)

    def test_membership_splits_slugs_and_preserves_empty_rows(self):
        self.path.write_text('news_id,keyword_slugs\n00123,a;b\n00124,\n', encoding="utf-8-sig")
        result = self.module.load_topic_membership(self.path)
        self.assertEqual(result, {"a": {"00123"}, "b": {"00123"}})
        self.assertEqual(result.news_ids, {"00123", "00124"})

    def test_duplicate_membership_rows_raise(self):
        self.path.write_text('news_id,keyword_slugs\n00123,a\n00123,a\n', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.module.load_topic_membership(self.path)

    def test_duplicate_profile_raises(self):
        self.path.write_text('{"profiles":[{"slug":"a"},{"slug":"a"}]}', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.module.load_profiles(self.path)

    def test_year_series_omits_missing_and_marks_cutoff_partial(self):
        points = self.module.build_year_series({"2024": 4, "2025": 5, "2026": 6}, "2026-09-12")
        self.assertEqual([p["period"] for p in points], ["2024", "2025", "2026"])
        self.assertEqual([p["period_status"] for p in points], ["observed", "observed", "partial"])

    def test_year_series_no_current_count_is_unknown_not_zero(self):
        points = self.module.build_year_series({"2024": 4}, "2026-09-12")
        self.assertEqual(points[-1], {"period": "2026", "value": None, "period_status": "unknown"})

    def test_year_series_complete_year_and_invalid_counts(self):
        self.assertEqual(self.module.build_year_series({"2026": 4}, "2026-12-31")[0]["period_status"], "observed")
        for counts in ({"2026": -1}, {"2027": 3}, {"unknown": 3}, {"2025": True}):
            with self.assertRaises(ValueError):
                self.module.build_year_series(counts, "2026-09-12")


class SemanticValidatorTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module("scripts.policy_research_v2")
        self.assertTrue(hasattr(self.module, "validate_artifact"), "Semantic validator not implemented")
        self.artifact = fixture()
        self.inputs = json.loads((FIXTURES / "policy_research_v2.canonical.json").read_text(encoding="utf-8"))
        self.inputs["membership"] = {k: set(v) for k, v in self.inputs["membership"].items()}

    def codes(self):
        return {i.code for i in self.module.validate_artifact(self.artifact, **self.inputs) if i.severity == "error"}

    def test_valid_artifact(self):
        self.assertEqual(self.codes(), set())

    def test_metric_event_insight_source_id_must_exist(self):
        for key in ("key_metrics", "key_events", "trend_insights"):
            with self.subTest(key=key):
                self.artifact = fixture()
                self.artifact[key][0]["source_ids"] = ["moenv-news:not-present"]
                self.assertIn("SOURCE_NOT_FOUND", self.codes())

    def test_moenv_external_id_must_exist_and_required_fields(self):
        self.artifact["sources"][0]["external_id"] = "absent"
        self.assertIn("NEWS_NOT_FOUND", self.codes())
        for key in ("external_id", "published_at"):
            self.artifact = fixture()
            del self.artifact["sources"][0][key]
            self.assertIn("MOENV_SOURCE_REQUIRED", self.codes())

    def test_news_source_provenance_must_match(self):
        for key in ("url", "published_at", "publisher", "title", "source_id"):
            self.artifact = fixture()
            self.artifact["sources"][0][key] = {"url": "https://example.invalid/wrong", "published_at": "2024-05-02"}.get(key, "wrong")
            self.assertIn("SOURCE_MISMATCH", self.codes(), key)

    def test_duplicate_ids_fail(self):
        for key in ("sources", "key_metrics", "key_events", "trend_insights", "trend_series"):
            self.artifact = fixture()
            self.artifact[key].append(copy.deepcopy(self.artifact[key][0]))
            self.assertIn("DUPLICATE_ID", self.codes(), key)

    def test_evidence_reference_must_exist(self):
        self.artifact["trend_insights"][0]["evidence_refs"] = ["event-absent"]
        self.assertIn("EVIDENCE_NOT_FOUND", self.codes())

    def test_coverage_cannot_exceed_dataset_cutoff(self):
        self.artifact["scope"]["date_to"] = "2026-09-13"
        self.assertIn("COVERAGE_EXCEEDS_DATASET", self.codes())

    def test_reversed_coverage_fails(self):
        self.artifact["scope"]["date_from"] = "2027-01-01"
        self.assertIn("COVERAGE_ORDER", self.codes())

    def test_current_incomplete_year_cannot_be_observed(self):
        self.artifact["trend_series"][0]["points"][-1]["period_status"] = "observed"
        self.assertIn("PARTIAL_YEAR_REQUIRED", self.codes())

    def test_membership_unknown_id_and_missing_rows(self):
        self.inputs["membership"]["fixture_topic"].add("not-in-main")
        self.assertIn("MEMBERSHIP_ID_NOT_FOUND", self.codes())
        membership = self.module.TopicMembership()
        membership.update({"fixture_topic": {"00123", "00124", "00125"}})
        membership.news_ids = {"00123", "00124"}
        self.inputs["membership"] = membership
        self.assertIn("MEMBERSHIP_COVERAGE", self.codes())

    def test_profile_total_and_year_counts_are_verified(self):
        self.inputs["profiles"]["fixture_topic"]["total"] = 4
        self.assertIn("PROFILE_TOTAL_MISMATCH", self.codes())
        self.inputs["profiles"]["fixture_topic"]["year_counts"]["2024"] = 2
        self.assertIn("PROFILE_YEARS_MISMATCH", self.codes())

    def test_artifact_counts_statistics_and_series_verified(self):
        self.artifact["scope"]["article_count"] = 4
        self.assertIn("ARTICLE_COUNT_MISMATCH", self.codes())
        self.artifact["statistics"]["latest_article_date"] = "2026-01-02"
        self.assertIn("STATISTICS_MISMATCH", self.codes())
        self.artifact["trend_series"][0]["points"][0]["value"] = 10
        self.assertIn("SERIES_MISMATCH", self.codes())

    def test_manifest_and_snapshot_date_verified(self):
        self.inputs["manifest"]["indexed_count"] = 4
        self.assertIn("MANIFEST_COUNT_MISMATCH", self.codes())
        self.artifact["meta"]["dataset_generated_at"] = "2026-09-11T12:35:00+08:00"
        self.assertIn("DATASET_VERSION_MISMATCH", self.codes())

    def test_zero_without_completeness_evidence_fails(self):
        self.artifact["trend_series"][0]["points"][0].update(value=0, period_status="zero")
        self.assertIn("ZERO_UNVERIFIED", self.codes())

    def test_duplicate_or_missing_period_fails(self):
        self.artifact["trend_series"][0]["points"].pop()
        self.assertIn("SERIES_MISMATCH", self.codes())

    def test_unknown_shape_is_reported_without_crash(self):
        self.artifact = {"schema_version": "2.0"}
        self.assertIn("SCHEMA", self.codes())

    def test_low_confidence_cannot_claim_passed(self):
        self.artifact["trend_insights"][0]["confidence"] = "low"
        self.assertIn("LOW_CONFIDENCE_REVIEW_REQUIRED", self.codes())

    def test_future_event_fails_but_target_year_is_allowed(self):
        self.artifact["key_events"][0]["date"] = "2027-01-01"
        self.assertIn("EVENT_OUTSIDE_SCOPE", self.codes())


class TrendSignalTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module("scripts.policy_research_v2")
        self.assertTrue(hasattr(self.module, "build_trend_signals"), "Trend signals not implemented")

    def points(self, values):
        return [{"period": str(2020 + i), "value": v, "period_status": "observed"} for i, v in enumerate(values)]

    def test_low_base_growth_not_inflated(self):
        self.assertEqual(self.module.build_trend_signals(self.points([1, 3])), [])

    def test_three_consecutive_periods_produce_sustained_growth(self):
        signals = self.module.build_trend_signals(self.points([10, 20, 30]))
        signal = next(s for s in signals if s["type"] == "sustained_growth")
        self.assertEqual(signal["baseline"], 10)
        self.assertEqual(signal["period"], "2022")
        self.assertTrue(signal["method"])

    def test_peak_uses_prior_three_year_baseline(self):
        signals = self.module.build_trend_signals(self.points([10, 10, 10, 40, 12]))
        peak = next(s for s in signals if s["type"] == "peak")
        self.assertEqual((peak["period"], peak["baseline"], peak["value"]), ("2023", 10, 40))

    def test_decline_is_supported_without_dividing_by_zero(self):
        signals = self.module.build_trend_signals(self.points([30, 20, 10, 0]))
        self.assertIn("sustained_decline", {s["type"] for s in signals})
        self.assertEqual(self.module.build_trend_signals(self.points([0, 0, 0])), [])

    def test_partial_unknown_and_missing_year_break_comparisons(self):
        for status in ("partial", "unknown"):
            points = self.points([10, 20, 90])
            points[-1]["period_status"] = status
            if status == "unknown":
                points[-1]["value"] = None
            self.assertFalse(any(s["period"] == "2022" for s in self.module.build_trend_signals(points)))
        points = self.points([10, 20, 30])
        points[-1]["period"] = "2023"
        self.assertFalse(any(s["type"] == "sustained_growth" for s in self.module.build_trend_signals(points)))

    def test_duplicate_or_unsorted_periods_rejected(self):
        points = self.points([10, 20])
        for bad in (list(reversed(points)), [points[0], points[0]]):
            with self.assertRaises(ValueError):
                self.module.build_trend_signals(bad)

    def test_fabricated_signal_does_not_validate(self):
        artifact = fixture()
        artifact["trend_signals"] = [{"signal_id": "invented", "type": "rapid_growth", "period": "2025", "series_id": "article_count_yearly", "value": 1, "baseline": 0, "strength": "high", "method": "invented", "description": "invented"}]
        inputs = json.loads((FIXTURES / "policy_research_v2.canonical.json").read_text(encoding="utf-8"))
        inputs["membership"] = {k: set(v) for k, v in inputs["membership"].items()}
        issues = self.module.validate_artifact(artifact, **inputs)
        self.assertIn("SIGNALS_MISMATCH", {i.code for i in issues})


class ArtifactCompilationTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module("scripts.policy_research_v2")
        self.assertTrue(hasattr(self.module, "compile_artifact"), "Artifact compiler not implemented")
        self.inputs = json.loads((FIXTURES / "policy_research_v2.canonical.json").read_text(encoding="utf-8"))
        self.inputs["membership"] = {k: set(v) for k, v in self.inputs["membership"].items()}
        original = fixture()
        self.authored = {k: original[k] for k in ("research_id", "key_metrics", "key_events", "trend_insights")}
        self.authored.update(topic_slug="fixture_topic", date_from="2024-01-01", source_news_ids=["00123"], source_markdown="fixture.md", accessed_at="2026-09-12", warnings=[])
        self.metadata = {"updated": "2026-09-12", "coverage_end": "2026-09-12"}

    def compile(self):
        return self.module.compile_artifact(self.authored, **self.inputs, markdown_metadata=self.metadata, generated_at="2026-09-13T00:00:00+08:00", input_sha256={"test": "a" * 64})

    def test_compiler_derives_counts_and_preserves_authored_claims(self):
        result = self.compile()
        self.assertEqual(result["statistics"], fixture()["statistics"])
        self.assertEqual(result["trend_series"], fixture()["trend_series"])
        self.assertEqual(result["key_metrics"], fixture()["key_metrics"])
        self.assertEqual(result["research_id"], "fixture-topic")
        self.assertEqual(result["quality"]["status"], "needs_review")
        self.assertFalse([i for i in self.module.validate_artifact(result, **self.inputs) if i.severity == "error"])

    def test_compiler_emits_missing_metadata_without_inventing_counts(self):
        self.authored["date_from"] = "2021-01-01"
        result = self.compile()
        self.assertEqual(result["scope"]["missing_years"], ["2021", "2022", "2023"])
        self.assertEqual(result["trend_series"][0]["points"][0]["period"], "2024")

    def test_compiler_keeps_narrative_cutoff_and_event_date_separate(self):
        self.metadata["coverage_end"] = "2026-07-08"
        self.authored["key_events"][0]["date"] = "2024-04-30"
        result = self.compile()
        self.assertEqual(result["scope"]["date_to"], "2026-09-12")
        self.assertEqual(result["meta"]["narrative_coverage_end"], "2026-07-08")
        self.assertEqual(result["sources"][0]["published_at"], "2024-05-01")
        self.assertEqual(result["key_events"][0]["date"], "2024-04-30")

    def test_fingerprint_changes_with_input_and_mismatch_fails(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            path = Path(temp) / "input.json"
            path.write_text('{}', encoding="utf-8")
            hashes = self.module.input_fingerprints({"news_index": path})
            path.write_text('{"changed":true}', encoding="utf-8")
            now = self.module.input_fingerprints({"news_index": path})
            self.assertNotEqual(hashes, now)
            artifact = self.compile()
            artifact["meta"]["input_sha256"] = hashes
            issues = self.module.validate_input_fingerprints(artifact, {"news_index": path})
            self.assertIn("INPUT_FINGERPRINT_MISMATCH", {i.code for i in issues})

    def test_nonfinite_json_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            path = Path(temp) / "invalid.json"
            for value in ("NaN", "Infinity", "-Infinity"):
                path.write_text('{"value":' + value + '}', encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.module.read_json(path)

    def test_markdown_metadata_uses_yaml_and_real_dates(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            path = Path(temp) / "note.md"
            path.write_text('---\nupdated: 2026-09-13\ncoverage_end: "2026-07-08"\n---\n# Note', encoding="utf-8")
            result = self.module.read_markdown_metadata(path)
            self.assertEqual(str(result["updated"]), "2026-09-13")
            self.assertEqual(str(result["coverage_end"]), "2026-07-08")

    def test_legacy_snapshot_discrepancy_is_warning(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            root = Path(temp)
            (root / "資料").mkdir()
            (root / "資料/moenv_news_index.csv").write_text("news_id\n00123\n", encoding="utf-8")
            (root / "資料/moenv_news_keywords.jsonl").write_text('{"news_id":"00123"}\n', encoding="utf-8")
            issues = self.module.snapshot_warnings(root, self.inputs["news_index"])
            self.assertEqual(len(issues), 2)
            self.assertTrue(all(i.severity == "warning" and i.code == "LEGACY_SNAPSHOT_MISMATCH" for i in issues))


class GeneralizedSeriesTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module("scripts.policy_research_v2")
        self.artifact = fixture()
        self.inputs = json.loads((FIXTURES / "policy_research_v2.canonical.json").read_text(encoding="utf-8"))
        self.inputs["membership"] = {k: set(v) for k, v in self.inputs["membership"].items()}
        self.series = json.loads((FIXTURES / "policy_research_v2.non_news_series.json").read_text(encoding="utf-8"))
        self.artifact["trend_series"].append(self.series)

    def errors(self):
        return [i for i in self.module.validate_artifact(self.artifact, **self.inputs) if i.severity == "error"]

    def test_non_news_decimal_series_passes_schema_and_semantics(self):
        self.assertEqual(self.errors(), [])

    def test_year_quarter_month_and_metric_types(self):
        for frequency, period in (("year", "2025"), ("quarter", "2025-Q1"), ("month", "2025-01")):
            for metric in ("count", "percentage", "amount", "emissions", "reduction", "capacity", "other"):
                with self.subTest(frequency=frequency, metric=metric):
                    self.series.update(frequency=frequency, metric_type=metric)
                    self.series["points"] = [{"period": period, "value": 5, "period_status": "observed"}]
                    self.assertEqual(self.errors(), [])

    def test_generic_series_does_not_change_news_signal_baseline(self):
        self.artifact["trend_series"].reverse()
        self.artifact["trend_signals"] = []
        self.assertEqual(self.errors(), [])

    def test_period_must_match_frequency_and_calendar(self):
        for frequency, period in (("year", "2025-01"), ("month", "2025-13"), ("quarter", "2025-Q5"), ("month", "0000-01")):
            with self.subTest(period=period):
                self.series.update(frequency=frequency)
                self.series["points"] = [{"period": period, "value": 1, "period_status": "observed"}]
                self.assertIn("SERIES_PERIOD_INVALID", {i.code for i in self.errors()})

    def test_generic_period_order_and_duplicates_rejected(self):
        self.series["points"].reverse()
        self.assertIn("SERIES_PERIOD_ORDER", {i.code for i in self.errors()})
        self.series["points"] = [self.series["points"][0]] * 2
        self.assertIn("SERIES_PERIOD_ORDER", {i.code for i in self.errors()})

    def test_generic_series_source_required_and_resolvable(self):
        self.series["source_ids"] = ["not-present"]
        self.assertIn("SOURCE_NOT_FOUND", {i.code for i in self.errors()})
        self.series.pop("source_ids")
        self.assertIn("SERIES_SOURCE_REQUIRED", {i.code for i in self.errors()})

    def test_news_contract_stays_strict(self):
        self.artifact["trend_series"].pop()
        self.artifact["trend_series"][0]["frequency"] = "month"
        self.assertIn("NEWS_SERIES_CONTRACT", {i.code for i in self.errors()})

    def test_count_rejects_fractional_values_and_unknown_requires_null(self):
        self.series["metric_type"] = "count"
        self.assertTrue(self.errors())
        self.series["metric_type"] = "emissions"
        self.series["points"][0]["period_status"] = "unknown"
        self.assertTrue(self.errors())


class EventPrecisionTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module("scripts.policy_research_v2")
        self.artifact = fixture()
        self.inputs = json.loads((FIXTURES / "policy_research_v2.canonical.json").read_text(encoding="utf-8"))
        self.inputs["membership"] = {k: set(v) for k, v in self.inputs["membership"].items()}

    def issues(self, value, precision):
        self.artifact["key_events"][0].update(date=value, date_precision=precision)
        return self.module.validate_artifact(self.artifact, **self.inputs)

    def test_month_and_year_keep_original_precision(self):
        for value, precision in (("2025-11", "month"), ("2025", "year"), ("2024-02-29", "day")):
            with self.subTest(value=value):
                self.assertEqual([i for i in self.issues(value, precision) if i.severity == "error"], [])
                self.assertEqual(self.artifact["key_events"][0]["date"], value)

    def test_precision_mismatch_and_invalid_calendar_rejected(self):
        for value, precision in (("2025", "day"), ("2025-11-01", "month"), ("2025-11", "year"), ("2025-13", "month"), ("0000", "year"), ("2025-02-29", "day")):
            with self.subTest(value=value, precision=precision):
                self.assertTrue([i for i in self.issues(value, precision) if i.severity == "error"])

    def test_imprecise_period_entirely_outside_scope_fails(self):
        for value, precision in (("2023", "year"), ("2026-10", "month")):
            self.assertIn("EVENT_OUTSIDE_SCOPE", {i.code for i in self.issues(value, precision)})

    def test_imprecise_period_overlapping_cutoff_warns_without_inventing_date(self):
        for value, precision in (("2026", "year"), ("2026-09", "month")):
            issues = self.issues(value, precision)
            self.assertFalse([i for i in issues if i.severity == "error"])
            self.assertIn("EVENT_SCOPE_UNCERTAIN", {i.code for i in issues if i.severity == "warning"})
            self.assertEqual(self.artifact["key_events"][0]["date"], value)


class PublicationSummaryTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module("scripts.policy_research_v2")
        self.artifact = fixture()
        self.inputs = json.loads((FIXTURES / "policy_research_v2.canonical.json").read_text(encoding="utf-8"))
        self.inputs["membership"] = {k: set(v) for k, v in self.inputs["membership"].items()}
        self.summary = {"headline": "Synthetic headline", "summary": "Synthetic summary", "source_ids": ["moenv-news:00123"]}

    def publication_issues(self):
        self.assertIn("publication", self.module.validate_artifact.__kwdefaults__ or {}, "Publication-level validation not implemented")
        return self.module.validate_artifact(self.artifact, **self.inputs, publication=True)

    def test_base_summary_optional_but_publication_requires_it(self):
        self.assertFalse([i for i in self.module.validate_artifact(self.artifact, **self.inputs) if i.severity == "error"])
        self.assertIn("SUMMARY_REQUIRED", {i.code for i in self.publication_issues()})

    def test_publication_summary_validates_sources(self):
        self.artifact["research_summary"] = self.summary
        self.assertFalse([i for i in self.publication_issues() if i.severity == "error"])
        self.summary["source_ids"] = ["missing-source"]
        self.assertIn("SOURCE_NOT_FOUND", {i.code for i in self.publication_issues()})

    def test_publication_cli_missing_summary_fails_and_valid_summary_passes(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            path = Path(temp) / "publication.json"
            for include_summary, expected in ((False, 1), (True, 0)):
                if include_summary:
                    self.artifact["research_summary"] = self.summary
                path.write_text(json.dumps(self.artifact), encoding="utf-8")
                result = subprocess.run([sys.executable, str(ROOT / "scripts/validate_policy_research_v2.py"), "--artifact", str(path), "--fixture-mode", "--publication"], capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                if not include_summary:
                    self.assertIn("SUMMARY_REQUIRED", result.stdout)

    def test_pilot_contains_authored_summary_without_automatic_acceptance(self):
        pilot = self.module.read_json(ROOT / "03_政策研究/研究資料/net-zero-transition.v2.json")
        authored = self.module.read_json(ROOT / "03_政策研究/研究資料/作者輸入/net-zero-transition.json")
        self.assertIn("research_summary", pilot)
        self.assertEqual(pilot["research_summary"], authored["research_summary"])
        self.assertEqual(pilot["quality"]["status"], "needs_review")


class ValidatorCLITests(unittest.TestCase):
    def test_builder_cli_rejects_missing_input_without_creating_output(self):
        cli = ROOT / "scripts/build_policy_research_v2.py"
        self.assertTrue(cli.is_file(), "Builder CLI not implemented")
        with tempfile.TemporaryDirectory(dir=ROOT / "tests") as temp:
            output = Path(temp) / "must-not-exist.json"
            result = subprocess.run([sys.executable, str(cli), "--authored", str(Path(temp) / "missing.json"), "--output", str(output)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertFalse(output.exists())

    def test_valid_and_invalid_fixture_cli(self):
        cli = ROOT / "scripts/validate_policy_research_v2.py"
        self.assertTrue(cli.is_file(), "Validation CLI not implemented")
        for name, status in (("valid", 0), ("invalid_missing_source", 1)):
            result = subprocess.run([sys.executable, str(cli), "--artifact", str(FIXTURES / f"policy_research_v2.{name}.json"), "--fixture-mode"], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, status, result.stdout + result.stderr)
            if status:
                self.assertIn("SOURCE_NOT_FOUND", result.stdout)


if __name__ == "__main__":
    unittest.main()
