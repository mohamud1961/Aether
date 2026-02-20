import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from aether.evals.utils.hashes import canonical_json_dumps
from aether.evals.frugal_evals.chop_shop_patch import build_t1_patch_tasks, score_patch_predictions
from aether.evals.frugal_evals.cli import main as frugal_cli_main


class TestFrugalChopShopPatch(unittest.TestCase):

    def test_score_patch_predictions_is_deterministic_with_tier_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tasks_path = root / "tasks.jsonl"
            predictions_path = root / "predictions.jsonl"
            report1 = root / "report1.json"
            report2 = root / "report2.json"

            tasks = [
                {
                    "task_id": "patch_t1",
                    "source_tier": "T1",
                    "prompt": "Create a file",
                    "repo_map": {
                        "format": "file_list.v1",
                        "root": "/tmp/repo",
                        "files": ["a.txt"],
                        "truncation": {
                            "policy": "max_files",
                            "max_files": 2000,
                            "total_files": 1,
                            "truncated": False,
                        },
                    },
                    "allowed_edit_targets": ["a.txt"],
                    "gold_patch_targets": ["a.txt"],
                    "gold_patch_content": "diff --git a/a.txt b/a.txt\n--- /dev/null\n+++ b/a.txt\n@@ -0,0 +1 @@\n+hello\n",
                    "preimage_hashes": {
                        "a.txt": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                    },
                    "preimage_contents": {"a.txt": ""},
                },
                {
                    "task_id": "patch_t2",
                    "source_tier": "T2",
                    "prompt": "Create b.txt",
                    "repo_map": {
                        "format": "file_list.v1",
                        "root": "/tmp/repo",
                        "files": ["b.txt"],
                        "truncation": {
                            "policy": "max_files",
                            "max_files": 2000,
                            "total_files": 1,
                            "truncated": False,
                        },
                    },
                    "allowed_edit_targets": ["b.txt"],
                    "gold_patch_targets": ["b.txt"],
                    "gold_patch_content": "diff --git a/b.txt b/b.txt\n--- /dev/null\n+++ b/b.txt\n@@ -0,0 +1 @@\n+world\n",
                    "preimage_hashes": {
                        "b.txt": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                    },
                    "preimage_contents": {"b.txt": ""},
                },
            ]
            tasks_path.write_text(
                "\n".join(canonical_json_dumps(item) for item in tasks) + "\n",
                encoding="utf-8",
            )

            predictions = [
                {
                    "task_id": "patch_t1",
                    "predicted_patch_targets": ["a.txt"],
                    "predicted_patch_content": "diff --git a/a.txt b/a.txt\n--- /dev/null\n+++ b/a.txt\n@@ -0,0 +1 @@\n+hello\n",
                    "assumed_preimage_hashes": {
                        "a.txt": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                    },
                },
                {
                    "task_id": "patch_t2",
                    "predicted_patch_targets": ["x.txt"],
                    "predicted_patch_content": "",
                    "assumed_preimage_hashes": {"b.txt": "0000"},
                },
            ]
            predictions_path.write_text(
                "\n".join(canonical_json_dumps(item) for item in predictions) + "\n",
                encoding="utf-8",
            )

            score_patch_predictions(
                predictions_path=predictions_path,
                tasks_path=tasks_path,
                report_path=report1,
                model_id="mock-zombie-v1",
            )
            score_patch_predictions(
                predictions_path=predictions_path,
                tasks_path=tasks_path,
                report_path=report2,
                model_id="mock-zombie-v1",
            )

            self.assertEqual(
                hashlib.sha256(report1.read_bytes()).hexdigest(),
                hashlib.sha256(report2.read_bytes()).hexdigest(),
            )

            report = json.loads(report1.read_text(encoding="utf-8"))
            self.assertIn("patch_only", report)
            self.assertIn("search_only", report)
            self.assertIn("tier_reports", report)
            self.assertIn("T1", report["tier_reports"])
            self.assertIn("T2", report["tier_reports"])
            self.assertIn("file_target_hit_rate", report["patch_only"])
            self.assertIn("patch_applies_cleanly_rate", report["patch_only"])
            self.assertIn("preimage_hash_match_rate", report["patch_only"])
            self.assertIn("content_similarity_mean", report["patch_only"])
            self.assertIn("exact_match_rate", report["patch_only"])

    def test_cli_chop_shop_patch_includes_integrated_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            tasks_path = root / "tasks.jsonl"
            search_report_path = root / "search_report.json"
            report_path = root / "patch_report.json"

            tasks = [
                {
                    "task_id": "patch_t1",
                    "source_tier": "T1",
                    "prompt": "Create service config",
                    "repo_map": {
                        "format": "file_list.v1",
                        "root": "/tmp/repo",
                        "files": ["service.yml"],
                        "truncation": {
                            "policy": "max_files",
                            "max_files": 2000,
                            "total_files": 1,
                            "truncated": False,
                        },
                    },
                    "allowed_edit_targets": ["service.yml"],
                    "gold_patch_targets": ["service.yml"],
                    "gold_patch_content": "diff --git a/service.yml b/service.yml\n--- /dev/null\n+++ b/service.yml\n@@ -0,0 +1 @@\n+ok: true\n",
                    "preimage_hashes": {
                        "service.yml": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
                    },
                    "preimage_contents": {"service.yml": ""},
                }
            ]
            tasks_path.write_text(
                "\n".join(canonical_json_dumps(item) for item in tasks) + "\n",
                encoding="utf-8",
            )

            search_report = {
                "all_tiers_combined_labeled": {
                    "mean_metrics": {
                        "by_k": {"5": {"recall_at_k_mean": 0.8}},
                        "mrr": 0.75,
                    }
                },
                "tier_reports": {
                    "T1": {
                        "mean_metrics": {
                            "by_k": {"5": {"recall_at_k_mean": 0.8}},
                            "mrr": 0.75,
                        }
                    },
                    "T2": {
                        "mean_metrics": {
                            "by_k": {"5": {"recall_at_k_mean": 0.0}},
                            "mrr": 0.0,
                        }
                    },
                },
            }
            search_report_path.write_text(canonical_json_dumps(search_report) + "\n", encoding="utf-8")

            exit_code = frugal_cli_main(
                [
                    "chop-shop-patch",
                    "--tasks",
                    tasks_path.as_posix(),
                    "--model-id",
                    "mock-zombie-v1",
                    "--out",
                    report_path.as_posix(),
                    "--search-report",
                    search_report_path.as_posix(),
                ]
            )
            self.assertEqual(exit_code, 0)

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertIn("search_only", report)
            self.assertIn("patch_only", report)
            self.assertIn("tier_reports", report)
            self.assertIn("T1", report["tier_reports"])
            self.assertIn("T2", report["tier_reports"])
            self.assertIn("component_notice", report)


if __name__ == "__main__":
    unittest.main()
