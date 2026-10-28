# md-anchor-lint

A small checker for Markdown documentation trees that finds the two link problems which rot silently: relative links pointing at files that no longer exist, and `#fragment` links pointing at headings that were renamed. Fragment matching follows GitHub's own slug rules, so a link that passes here resolves on github.com.

## Why

Renaming a heading breaks every deep link into it and nothing in a normal build or test run notices. GitHub renders a broken anchor as a jump to the top of the page, which looks close enough to working that nobody reports it. This tool reads the files locally, builds the anchor table each document actually offers, and compares every link against it. No network access, no dependencies outside the standard library.

## Install

The package is plain Python with no dependencies, so running it from a checkout is enough:

```
git clone https://github.com/wyn-cmd/md-anchor-lint.git
cd md-anchor-lint
python3 -m md_anchor_lint .
```

`pip install .` also works if you want the `md-anchor-lint` command on your PATH.

## Usage

```
python3 -m md_anchor_lint [paths...] [--json] [--no-images] [--exclude GLOB]
```

- `paths` are files or directories, and the default is the current directory.
- `--json` prints the findings as JSON for a CI step to parse.
- `--no-images` skips image targets when only documentation links matter.
- `--exclude` skips paths matching a glob and can be repeated, for example `--exclude 'vendor/*'`.

Example output:

```
docs/setup.md
  line 12  missing file  ../scripts/install.sh
  line 20  missing anchor  api.md#instal
checked 3 files and 41 links: 2 problems, 1 warnings
```

Exit codes: `0` clean, `1` at least one broken link, `2` a path given on the command line does not exist.

## What is checked

- Relative links to other files in the tree, including percent encoded paths and targets wrapped in angle brackets.
- Anchors in the same file, anchors in other Markdown files, and anchors that point at a heading inside a linked document.
- Reference style links (`[text][label]` with a `[label]: target` definition anywhere in the file).
- HTML anchors, meaning `id="..."` and `<a name="...">`, count as valid fragment targets.
- Fenced code blocks and inline code spans are ignored, so a documented example link is not reported as broken.
- Images are checked as files unless `--no-images` is passed.

## What is not checked

- Remote URLs are never fetched. A dead external link is out of scope by design.
- Site absolute paths such as `/docs/setup` are skipped, because whether they resolve depends on where the site is published.
- Full CommonMark parsing is not implemented: link text containing nested brackets, indented code blocks and reference definitions inside list items are not handled. The parser is deliberately line oriented and predictable.

## Case handling

A path or fragment that differs from the real one only in capitalisation is reported as a warning instead of a failure. It still breaks on GitHub, which serves case sensitive paths, but it keeps the exit code green for trees that are checked out on case insensitive filesystems.

## Tests

```
python3 -m unittest discover -s tests -v
```

Twenty one tests cover slug generation, heading de-duplication, fenced blocks, reference links, cross file anchors, case mismatches, image skipping, glob exclusion and the three exit codes.

## Layout

- `md_anchor_lint/lint.py` holds the parser, the anchor builder and the link resolver.
- `md_anchor_lint/cli.py` holds argument parsing and report formatting.
- `tests/test_lint.py` holds the fixtures and the test cases.

## License

MIT, see [LICENSE](LICENSE).
