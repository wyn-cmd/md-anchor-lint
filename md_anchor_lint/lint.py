# Markdown link and anchor checking that follows the way GitHub turns
# headings into fragment identifiers.

import fnmatch
import os
import re
from urllib.parse import unquote

# directories that never hold documentation worth checking
SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
    "site-packages",
}

MARKDOWN_SUFFIXES = (".md", ".markdown", ".mdown", ".mkd")

FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^ {0,3}#{1,6}[ \t]+(.*)$")
DEFINITION_RE = re.compile(r"^ {0,3}\[([^\[\]]+)\]:\s*(<[^>]*>|\S+)")
INLINE_LINK_RE = re.compile(
    r"(!?)\[([^\[\]]*)\]\(\s*(<[^>]*>|[^()\s]+)(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^()]*\)))?\s*\)"
)
REFERENCE_LINK_RE = re.compile(r"(!?)\[([^\[\]]*)\]\[([^\[\]]*)\]")
HTML_ID_RE = re.compile(
    r"<(?:a|span|div|p|h[1-6]|section)\b[^>]*?\b(?:id|name)\s*=\s*[\"']([^\"']+)[\"']",
    re.IGNORECASE,
)
INLINE_CODE_RE = re.compile(r"(`+)(.+?)\1", re.DOTALL)
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def is_markdown(path):
    # suffix test used both for walking directories and for anchor lookups
    return path.lower().endswith(MARKDOWN_SUFFIXES)


def strip_inline_code(text):
    # links written inside `backticks` are examples, not real links
    return INLINE_CODE_RE.sub("", text)


def slugify(text):
    # GitHub drops HTML, keeps link text, lowercases and drops punctuation
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]*)\]\[[^\]]*\]", r"\1", text)
    text = text.replace("`", "")
    chars = []
    for char in text.lower():
        if char.isalnum() or char in "-_":
            chars.append(char)
        elif char.isspace():
            chars.append("-")
    return "".join(chars)


def iter_visible_lines(lines):
    # yields (line_number, line) for every line outside a fenced code block
    fence_char = None
    fence_length = 0
    for number, line in enumerate(lines, start=1):
        match = FENCE_RE.match(line)
        if fence_char is None:
            if match:
                fence_char = match.group(1)[0]
                fence_length = len(match.group(1))
                continue
            yield number, line
            continue
        if match and match.group(1)[0] == fence_char and len(match.group(1)) >= fence_length:
            fence_char = None
            fence_length = 0


class Document:
    # parsed view of one Markdown file: headings, anchors, links and definitions
    def __init__(self, path):
        self.path = path
        self.headings = []
        self.html_ids = set()
        self.links = []
        self.definitions = {}
        self.anchors = set()
        self._parse()

    def _parse(self):
        with open(self.path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
        # reference definitions can appear anywhere in the file, so collect them first
        for _, line in iter_visible_lines(lines):
            definition = DEFINITION_RE.match(line)
            if definition:
                label = definition.group(1).strip().lower()
                self.definitions.setdefault(label, definition.group(2))
        for number, line in iter_visible_lines(lines):
            heading = HEADING_RE.match(line)
            if heading:
                text = heading.group(1).strip()
                text = re.sub(r"\s*#+\s*$", "", text)
                self.headings.append((number, text))
                continue
            for match in HTML_ID_RE.finditer(line):
                self.html_ids.add(match.group(1))
            visible = strip_inline_code(line)
            for match in INLINE_LINK_RE.finditer(visible):
                self.links.append((number, match.group(3), bool(match.group(1))))
            for match in REFERENCE_LINK_RE.finditer(visible):
                label = (match.group(3) or match.group(2)).strip().lower()
                target = self.definitions.get(label)
                if target:
                    self.links.append((number, target, bool(match.group(1))))
        self.anchors = self._build_anchors()

    def _build_anchors(self):
        # repeated headings get -1, -2 suffixes exactly like GitHub does
        anchors = set()
        counts = {}
        for _, text in self.headings:
            base = slugify(text)
            if not base:
                continue
            count = counts.get(base, 0)
            anchors.add(base if count == 0 else "%s-%d" % (base, count))
            counts[base] = count + 1
        anchors.update(self.html_ids)
        return anchors


class Linter:
    # walks a set of paths and records every broken link it finds
    def __init__(self, check_images=True, excludes=()):
        self.check_images = check_images
        self.excludes = tuple(excludes)
        self._documents = {}
        self.problems = []
        self.warnings = []
        self.link_count = 0
        self.file_count = 0

    def document(self, path):
        key = os.path.normpath(os.path.abspath(path))
        if key not in self._documents:
            self._documents[key] = Document(key)
        return self._documents[key]

    def anchors_for(self, path):
        return self.document(path).anchors

    def excluded(self, path, target):
        relative = os.path.relpath(path, target) if os.path.isdir(target) else os.path.basename(path)
        name = os.path.basename(path)
        for pattern in self.excludes:
            if fnmatch.fnmatch(relative, pattern) or fnmatch.fnmatch(name, pattern):
                return True
        return False

    def discover(self, targets):
        files = []
        for target in targets:
            if os.path.isdir(target):
                for root, dirnames, filenames in os.walk(target):
                    dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
                    for name in sorted(filenames):
                        if not is_markdown(name):
                            continue
                        path = os.path.join(root, name)
                        if self.excluded(path, target):
                            continue
                        files.append(path)
            elif os.path.isfile(target):
                files.append(target)
            else:
                raise FileNotFoundError(target)
        return files

    def run(self, targets):
        for path in self.discover(targets):
            self.check_file(path)
        return self

    def check_file(self, path):
        document = self.document(path)
        self.file_count += 1
        for number, target, is_image in document.links:
            if is_image and not self.check_images:
                continue
            self.link_count += 1
            self.resolve(path, target, number)

    def resolve(self, source, raw_target, line):
        target = raw_target.strip()
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        if not target:
            return
        # anything with a scheme points somewhere this tool cannot inspect
        if SCHEME_RE.match(target) or target.startswith("//"):
            return
        # site absolute links depend on where the site is published
        if target.startswith("/"):
            return
        path_part, _, fragment = target.partition("#")
        path_part = path_part.split("?", 1)[0]
        path_part = unquote(path_part)
        fragment = unquote(fragment)
        if not path_part:
            self.check_fragment(source, source, fragment, raw_target, line)
            return
        base = os.path.dirname(os.path.abspath(source))
        candidate = os.path.normpath(os.path.join(base, path_part))
        if not os.path.exists(candidate):
            alternative = self.case_alternative(candidate)
            if alternative:
                self.warnings.append(
                    {
                        "file": source,
                        "line": line,
                        "kind": "case-mismatch",
                        "detail": raw_target,
                        "hint": os.path.basename(alternative),
                    }
                )
                return
            self.problems.append(
                {"file": source, "line": line, "kind": "missing-file", "detail": raw_target}
            )
            return
        if fragment and is_markdown(candidate):
            self.check_fragment(source, candidate, fragment, raw_target, line)

    def check_fragment(self, source, document_path, fragment, raw_target, line):
        if not fragment:
            return
        try:
            anchors = self.anchors_for(document_path)
        except OSError:
            return
        if fragment in anchors:
            return
        # a fragment that differs only in case is probably a typo, not a dead link
        if fragment.lower() in {anchor.lower() for anchor in anchors}:
            self.warnings.append(
                {
                    "file": source,
                    "line": line,
                    "kind": "case-mismatch-anchor",
                    "detail": raw_target,
                }
            )
            return
        self.problems.append(
            {"file": source, "line": line, "kind": "missing-anchor", "detail": raw_target}
        )

    def case_alternative(self, path):
        # walk down from the nearest existing directory, matching every
        # remaining segment case-insensitively, so a wrong capitalised
        # directory name is reported as a case mismatch rather than a miss
        head, tail = os.path.split(path)
        parts = [tail]
        while head and not os.path.isdir(head):
            head, rest = os.path.split(head)
            if not rest:
                return None
            parts.insert(0, rest)
        if not os.path.isdir(head):
            return None
        current = head
        for part in parts:
            if not part:
                continue
            try:
                entries = os.listdir(current)
            except OSError:
                return None
            match = None
            for entry in entries:
                if entry.lower() == part.lower():
                    match = entry
                    break
            if match is None:
                return None
            current = os.path.join(current, match)
        return current
