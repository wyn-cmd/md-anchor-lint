# Tests for the Markdown link and anchor checker.

import os
import tempfile
import unittest

from md_anchor_lint import lint
from md_anchor_lint.cli import main


def write_tree(root, files):
    # writes a small fixture tree into a temporary directory
    for name, text in files.items():
        path = os.path.join(root, name)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)


class Fixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = self.directory.name

    def tearDown(self):
        self.directory.cleanup()

    def build(self, files):
        write_tree(self.root, files)

    def run_linter(self, **kwargs):
        linter = lint.Linter(**kwargs)
        linter.run([self.root])
        return linter


class SlugTests(unittest.TestCase):
    def test_punctuation_is_dropped(self):
        self.assertEqual(lint.slugify("Hello, World!"), "hello-world")

    def test_markdown_markup_is_unwrapped(self):
        self.assertEqual(lint.slugify("The `config` file"), "the-config-file")
        self.assertEqual(lint.slugify("[Setup](setup.md) guide"), "setup-guide")

    def test_underscores_and_hyphens_survive(self):
        self.assertEqual(lint.slugify("my_var-name"), "my_var-name")

    def test_plain_text_is_lowercased(self):
        self.assertEqual(lint.slugify("Quick Start"), "quick-start")


class AnchorTests(Fixture):
    def test_repeated_headings_get_suffixes(self):
        self.build({"a.md": "# Notes\n\n## Notes\n\n### Notes\n"})
        document = lint.Document(os.path.join(self.root, "a.md"))
        self.assertEqual(document.anchors, {"notes", "notes-1", "notes-2"})

    def test_html_ids_count_as_anchors(self):
        self.build({"a.md": 'Title\n\n<a name="legacy-anchor"></a>\n'})
        document = lint.Document(os.path.join(self.root, "a.md"))
        self.assertIn("legacy-anchor", document.anchors)


class LinkTests(Fixture):
    def test_working_relative_link_is_clean(self):
        self.build({"README.md": "See [the guide](docs/guide.md).\n", "docs/guide.md": "# Guide\n"})
        linter = self.run_linter()
        self.assertEqual(linter.problems, [])
        self.assertEqual(linter.link_count, 1)

    def test_missing_relative_link_is_reported(self):
        self.build({"README.md": "See [the guide](docs/guide.md).\n"})
        linter = self.run_linter()
        self.assertEqual(len(linter.problems), 1)
        self.assertEqual(linter.problems[0]["kind"], "missing-file")
        self.assertEqual(linter.problems[0]["line"], 1)

    def test_cross_file_anchor_is_checked(self):
        self.build(
            {
                "README.md": "See [install](docs/guide.md#installation).\n",
                "docs/guide.md": "# Guide\n\n## Installation\n",
            }
        )
        self.assertEqual(self.run_linter().problems, [])

    def test_missing_anchor_is_reported(self):
        self.build(
            {
                "README.md": "See [install](docs/guide.md#setup).\n",
                "docs/guide.md": "# Guide\n\n## Installation\n",
            }
        )
        linter = self.run_linter()
        self.assertEqual(len(linter.problems), 1)
        self.assertEqual(linter.problems[0]["kind"], "missing-anchor")

    def test_same_file_anchor_is_checked(self):
        self.build({"README.md": "# Title\n\nJump to [usage](#usage).\n"})
        self.assertEqual(self.run_linter().problems[0]["kind"], "missing-anchor")

    def test_links_inside_fences_are_ignored(self):
        self.build({"README.md": "```md\n[gone](missing.md)\n```\n"})
        linter = self.run_linter()
        self.assertEqual(linter.problems, [])
        self.assertEqual(linter.link_count, 0)

    def test_external_links_are_skipped(self):
        self.build({"README.md": "[site](https://example.com) and [mail](mailto:a@b.c)\n"})
        self.assertEqual(self.run_linter().problems, [])

    def test_reference_links_are_resolved(self):
        self.build(
            {
                "README.md": "Read the [guide][g].\n\n[g]: docs/guide.md\n",
                "docs/guide.md": "# Guide\n",
            }
        )
        self.assertEqual(self.run_linter().problems, [])

    def test_missing_reference_target_is_reported(self):
        self.build({"README.md": "Read the [guide][g].\n\n[g]: docs/nope.md\n"})
        self.assertEqual(self.run_linter().problems[0]["kind"], "missing-file")

    def test_case_mismatch_is_only_a_warning(self):
        self.build({"README.md": "See [guide](Docs/Guide.md).\n", "docs/guide.md": "# Guide\n"})
        linter = self.run_linter()
        self.assertEqual(linter.problems, [])
        self.assertEqual(linter.warnings[0]["kind"], "case-mismatch")

    def test_images_can_be_skipped(self):
        self.build({"README.md": "![logo](logo.png)\n"})
        self.assertEqual(len(self.run_linter().problems), 1)
        self.assertEqual(self.run_linter(check_images=False).problems, [])

    def test_exclude_glob_skips_files(self):
        self.build({"README.md": "See [x](missing.md).\n", "draft/notes.md": "See [y](gone.md).\n"})
        linter = self.run_linter(excludes=["draft/*"])
        self.assertEqual(len(linter.problems), 1)
        self.assertEqual(linter.file_count, 1)


class CliTests(Fixture):
    def test_clean_tree_exits_zero(self):
        self.build({"README.md": "# Title\n"})
        self.assertEqual(main([self.root]), 0)

    def test_broken_tree_exits_one(self):
        self.build({"README.md": "See [x](missing.md).\n"})
        self.assertEqual(main([self.root]), 1)

    def test_missing_path_exits_two(self):
        self.assertEqual(main([os.path.join(self.root, "nowhere")]), 2)


if __name__ == "__main__":
    unittest.main()
