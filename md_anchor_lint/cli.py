# Command line front end for the Markdown link checker.

import argparse
import json
import sys

from . import lint

LABELS = {
    "missing-file": "missing file",
    "missing-anchor": "missing anchor",
    "case-mismatch": "case mismatch",
    "case-mismatch-anchor": "anchor case mismatch",
}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="md-anchor-lint",
        description="Check Markdown files for broken relative links and broken heading anchors.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["."],
        help="files or directories to check, defaults to the current directory",
    )
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--no-images", action="store_true", help="skip image targets")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="GLOB",
        help="skip files whose path matches this glob, repeatable",
    )
    return parser


def human_report(linter):
    grouped = {}
    for item in linter.problems + linter.warnings:
        grouped.setdefault(item["file"], []).append(item)
    lines = []
    for path in sorted(grouped):
        lines.append(path)
        for item in sorted(grouped[path], key=lambda entry: (entry["line"], entry["kind"])):
            label = LABELS.get(item["kind"], item["kind"])
            lines.append("  line %d  %s  %s" % (item["line"], label, item["detail"]))
    lines.append(
        "checked %d files and %d links: %d problems, %d warnings"
        % (
            linter.file_count,
            linter.link_count,
            len(linter.problems),
            len(linter.warnings),
        )
    )
    return "\n".join(lines)


def main(argv=None):
    arguments = build_parser().parse_args(argv)
    targets = arguments.paths or ["."]
    linter = lint.Linter(check_images=not arguments.no_images, excludes=arguments.exclude)
    try:
        linter.run(targets)
    except FileNotFoundError as error:
        print("md-anchor-lint: no such file or directory: %s" % error, file=sys.stderr)
        return 2
    if arguments.json:
        print(
            json.dumps(
                {
                    "files": linter.file_count,
                    "links": linter.link_count,
                    "problems": linter.problems,
                    "warnings": linter.warnings,
                },
                indent=2,
            )
        )
    else:
        print(human_report(linter))
    # exit 1 only for real breakage, warnings keep the run green
    return 1 if linter.problems else 0
