import json
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "curating-skills" / "scripts" / "review-upstreams.py"


class ReviewUpstreamsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.work = self.root / "work"
        self.remote = self.root / "upstream.git"
        self.cache = self.root / "cache"
        self.manifest = self.root / "sources.json"
        self.output = self.root / "review.md"
        self.git("init", "-b", "main", str(self.work), cwd=self.root)
        self.git("config", "user.name", "Fixture Author", cwd=self.work)
        self.git("config", "user.email", "fixture@example.test", cwd=self.work)

        self.write("skills/changed/SKILL.md", "before\n")
        self.write("skills/removed/SKILL.md", "remove me\n")
        self.write("skills/renamed-old/SKILL.md", "rename me\n")
        self.git("add", ".", cwd=self.work)
        self.git("commit", "-m", "reviewed baseline", cwd=self.work)
        self.reviewed = self.git("rev-parse", "HEAD", cwd=self.work).stdout.strip()

        self.write("skills/changed/SKILL.md", "after\n")
        self.write("skills/added/SKILL.md", "new idea\n")
        self.git("mv", "skills/renamed-old", "skills/renamed-new", cwd=self.work)
        self.git("rm", "skills/removed/SKILL.md", cwd=self.work)
        self.git("add", ".", cwd=self.work)
        self.git("commit", "-m", "evolve upstream skills", cwd=self.work)
        self.current = self.git("rev-parse", "HEAD", cwd=self.work).stdout.strip()
        self.git("clone", "--bare", str(self.work), str(self.remote), cwd=self.root)
        self.write_manifest(str(self.remote), self.reviewed)

    def git(self, *args, cwd):
        return subprocess.run(
            ["git", *args], cwd=cwd, text=True, capture_output=True, check=True,
        )

    def write(self, relative, content):
        target = self.work / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def manifest_value(self, url, reviewed):
        return {
            "version": 1,
            "sources": [{
                "name": "fixture-source",
                "url": url,
                "branch": "main",
                "reviewedCommit": reviewed,
                "license": "MIT",
                "mappings": [
                    {
                        "localSkill": "clarifying-work",
                        "upstreamPaths": ["skills/changed", "skills/renamed-old"],
                    },
                    {
                        "localSkill": "planning-work",
                        "upstreamPaths": ["skills/added", "skills/removed"],
                    },
                ],
            }],
        }

    def write_manifest(self, url, reviewed):
        self.manifest.write_text(json.dumps(self.manifest_value(url, reviewed), indent=2) + "\n")

    def run_review(self, output=None, manifest=None):
        return subprocess.run(
            [
                "python3", str(SCRIPT),
                "--manifest", str(manifest or self.manifest),
                "--output", str(output or self.output),
                "--cache-dir", str(self.cache),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_bundle_covers_commits_inventory_mappings_and_manual_decisions(self):
        result = self.run_review()
        self.assertEqual(0, result.returncode, result.stderr)
        report = self.output.read_text()
        for heading in [
            "# Upstream Skill Review", "## fixture-source", "### Commits",
            "### Inventory Changes", "### Affected Local Skills", "### Mapped Diffs",
            "### Manual Review Checklist",
        ]:
            self.assertIn(heading, report)
        self.assertIn(f"`{self.current}` evolve upstream skills", report)
        self.assertRegex(report, r"(?m)^- `A` `skills/added/SKILL.md`$")
        self.assertRegex(report, r"(?m)^- `M` `skills/changed/SKILL.md`$")
        self.assertRegex(
            report,
            r"(?m)^- `R\d+` `skills/renamed-old/SKILL.md` → `skills/renamed-new/SKILL.md`$",
        )
        self.assertRegex(report, r"(?m)^- `D` `skills/removed/SKILL.md`$")
        self.assertIn("`clarifying-work`", report)
        self.assertIn("`planning-work`", report)
        self.assertIn("```diff", report)
        self.assertIn("compare current local behavior", report.lower())
        self.assertIn("accept or reject", report.lower())
        self.assertIn("does not update `reviewedCommit`", report)

    def test_output_is_deterministic_and_manifest_is_unchanged(self):
        before = self.manifest.read_bytes()
        first = self.root / "first.md"
        second = self.root / "second.md"
        self.assertEqual(0, self.run_review(first).returncode)
        self.assertEqual(0, self.run_review(second).returncode)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(before, self.manifest.read_bytes())

    def test_missing_reviewed_commit_fails_without_mutating_manifest(self):
        self.write_manifest(str(self.remote), "f" * 40)
        before = self.manifest.read_bytes()
        result = self.run_review()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("reviewed commit", result.stderr.lower())
        self.assertEqual(before, self.manifest.read_bytes())

    def test_divergent_reviewed_commit_fails_without_writing_report(self):
        self.git("checkout", "--orphan", "replacement", cwd=self.work)
        self.git("rm", "-rf", ".", cwd=self.work)
        self.write("skills/changed/SKILL.md", "replacement history\n")
        self.git("add", ".", cwd=self.work)
        self.git("commit", "-m", "replace upstream history", cwd=self.work)
        replacement = self.git("rev-parse", "HEAD", cwd=self.work).stdout.strip()
        self.git("push", "--force", str(self.remote), "replacement:main", cwd=self.work)

        before = self.manifest.read_bytes()
        result = self.run_review()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("not an ancestor", result.stderr.lower())
        self.assertFalse(self.output.exists())
        self.assertEqual(before, self.manifest.read_bytes())

    def test_fetch_failure_is_nonzero_and_preserves_manifest(self):
        self.write_manifest(str(self.root / "missing.git"), self.reviewed)
        before = self.manifest.read_bytes()
        result = self.run_review()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("fixture-source", result.stderr)
        self.assertEqual(before, self.manifest.read_bytes())

    def test_malformed_manifest_is_nonzero_and_unchanged(self):
        self.manifest.write_text("{not json\n")
        before = self.manifest.read_bytes()
        result = self.run_review()
        self.assertNotEqual(0, result.returncode)
        self.assertIn("manifest", result.stderr.lower())
        self.assertEqual(before, self.manifest.read_bytes())

    def test_checked_in_provenance_and_notices_preserve_sources(self):
        manifest = json.loads((ROOT / "config" / "sources.yaml").read_text())
        expected = {"matt-pocock-skills", "spec-kitty", "superpowers", "humanizer"}
        sources = {source["name"]: source for source in manifest["sources"]}
        self.assertEqual(expected, set(sources))
        for name in expected:
            source = sources[name]
            self.assertRegex(source["reviewedCommit"], r"^[0-9a-f]{40}$")
            self.assertEqual("MIT", source["license"])
            self.assertTrue(source["url"].startswith("https://github.com/"))
            self.assertTrue(source["branch"])
            self.assertTrue(source["mappings"])
            for mapping in source["mappings"]:
                self.assertTrue(mapping["localSkill"])
                self.assertTrue(mapping["upstreamPaths"])
                self.assertTrue(
                    (ROOT / "skills" / mapping["localSkill"] / "SKILL.md").is_file(),
                    mapping["localSkill"],
                )
        mapped = {
            (source["name"], mapping["localSkill"], upstream_path)
            for source in manifest["sources"]
            for mapping in source["mappings"]
            for upstream_path in mapping["upstreamPaths"]
        }
        self.assertIn(
            ("matt-pocock-skills", "adversarial-refinement", "skills/productivity/grilling"),
            mapped,
        )
        self.assertIn(
            ("superpowers", "adversarial-refinement", "skills/brainstorming"), mapped,
        )
        local = {item["name"]: item for item in manifest["localProvenance"]}
        self.assertEqual({"mk-clarify", "mk-write-plan", "mk-pr"}, set(local))
        original_root = Path(
            "/Users/mike/Library/Mobile Documents/iCloud~md~obsidian/Documents/Exocortex/Agents/skills",
        )
        for name, item in local.items():
            self.assertEqual(str(original_root / name), item["originalPath"])
            self.assertIs(item["fetchable"], False)
        notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
        for url in (source["url"] for source in sources.values()):
            self.assertIn(url, notices)
        self.assertGreaterEqual(notices.count("MIT License"), 3)
        self.assertIn("Permission is hereby granted", notices)

        ledger = json.loads((ROOT / "config" / "curation-decisions.json").read_text())
        self.assertEqual(1, ledger["version"])
        self.assertTrue(ledger["decisions"])
        for decision in ledger["decisions"]:
            self.assertEqual(
                {"source", "fromCommit", "toCommit", "decision", "disposition", "localSkills", "summary", "rationale", "validation"},
                set(decision),
            )
            self.assertIn(decision["source"], sources)
            self.assertRegex(decision["fromCommit"], r"^[0-9a-f]{40}$")
            self.assertRegex(decision["toCommit"], r"^[0-9a-f]{40}$")
            self.assertIn(decision["decision"], {"accept", "reject"})
            self.assertIn(decision["disposition"], {"adapted", "no-local-change", "rejected"})
            self.assertTrue(decision["summary"] and decision["rationale"] and decision["validation"])
            for skill in decision["localSkills"]:
                self.assertTrue((ROOT / "skills" / skill / "SKILL.md").is_file())

        approved = next(item for item in ledger["decisions"] if item["source"] == "matt-pocock-skills")
        self.assertEqual("9603c1cc8118d08bc1b3bf34cf714f62178dea3b", approved["fromCommit"])
        self.assertEqual(sources["matt-pocock-skills"]["reviewedCommit"], approved["toCommit"])

    def test_curation_skill_requires_conceptual_merge_not_automatic_copy(self):
        skill = (ROOT / "skills" / "curating-skills" / "SKILL.md").read_text()
        for concept in [
            "current local behavior", "recorded upstream commit", "current upstream behavior",
            "accept", "reject", "validate", "reviewedCommit",
        ]:
            self.assertIn(concept.lower(), skill.lower())
        self.assertRegex(skill, r"(?i)never auto(?:matically)?[- ]copy")
        self.assertRegex(skill, r"(?i)never .*push")
        self.assertRegex(skill, r"(?is)advance.*reviewedCommit.*after.*decision")
        self.assertIn('python3 "<skill-base-dir>/scripts/review-upstreams.py"', skill)
        self.assertIn('$REPO_ROOT/config/sources.yaml', skill)
        self.assertNotIn('python3 skills/curating-skills/scripts/', skill)


if __name__ == "__main__":
    unittest.main()
