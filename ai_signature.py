"""Extract function/class signatures and docstrings from a Python project.

Usage:
    python3 extract_signatures.py /path/to/project > signatures.txt
"""

import ast
import sys
from pathlib import Path

SKIP_DIRS = {"venv", ".venv", "__pycache__", ".git", "node_modules", "build", "dist"}
SKIP_FILES = {"ai_signature.py", "uv.lock", "app.prod.db", "app.staging.db", "app.test.db", "dpytest_0.day", "signature.txt"}


def iter_py_files(root: Path):
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        yield path


def build_tree(root: Path) -> str:
    lines = [f"{root.name}/"]

    def walk(dir_path: Path, prefix: str):
        entries = sorted(
            [
                p
                for p in dir_path.iterdir()
                if not (p.is_dir() and p.name in SKIP_DIRS) and not (p.is_file() and p.name in SKIP_FILES) and not p.name.startswith(".")
            ],
            key=lambda p: (p.is_file(), p.name.lower()),
        )
        for i, entry in enumerate(entries):
            connector = "└── " if i == len(entries) - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir():
                extension = "    " if i == len(entries) - 1 else "│   "
                walk(entry, prefix + extension)

    walk(root, "")
    return "\n".join(lines)


def format_docstring(doc: str, pad: str):
    """Return properly indented lines for a docstring block, pad is the indent of the def/class."""
    inner_pad = pad + "    "
    doc_lines = doc.splitlines()
    if len(doc_lines) == 1:
        return [f'{inner_pad}"""{doc_lines[0]}"""']
    lines = [f'{inner_pad}"""{doc_lines[0]}']
    for dl in doc_lines[1:]:
        lines.append(f"{inner_pad}{dl}" if dl.strip() else "")
    lines.append(f'{inner_pad}"""')
    return lines


def format_node(node, indent=0):
    pad = "    " * indent
    lines = []

    if isinstance(node, ast.ClassDef):
        for dec in node.decorator_list:
            lines.append(f"{pad}@{ast.unparse(dec)}")
        bases = ", ".join(ast.unparse(b) for b in node.bases)
        header = f"{pad}class {node.name}({bases}):" if bases else f"{pad}class {node.name}:"
        lines.append(header)
        doc = ast.get_docstring(node)
        if doc:
            lines.extend(format_docstring(doc, pad))

        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lines.extend(format_node(child, indent + 1))
        lines.append("")

    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        for dec in node.decorator_list:
            lines.append(f"{pad}@{ast.unparse(dec)}")
        prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        args = ast.unparse(node.args)
        ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
        lines.append(f"{pad}{prefix} {node.name}({args}){ret}:")
        doc = ast.get_docstring(node)
        if doc:
            lines.extend(format_docstring(doc, pad))
        lines.append("")

    return lines


def process_file(path: Path, root: Path):
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (SyntaxError, UnicodeDecodeError) as e:
        return [f"# SKIPPED {path.relative_to(root)}: {e}", ""]

    out = [f"# === {path.relative_to(root)} ===", ""]
    module_doc = ast.get_docstring(tree)
    if module_doc:
        out.extend(format_docstring(module_doc, ""))
        out.append("")
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.extend(format_node(node))
    out.append("")
    return out


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 extract_signatures.py /path/to/project", file=sys.stderr)
        sys.exit(1)

    root = Path(sys.argv[1]).resolve()
    if not root.exists():
        print(f"Path not found: {root}", file=sys.stderr)
        sys.exit(1)

    all_lines = ["# === Project structure ===", "", build_tree(root), "", ""]
    for path in sorted(iter_py_files(root)):
        all_lines.extend(process_file(path, root))

    with open("signatures.txt", "w") as f:
        f.write("\n".join(all_lines))


if __name__ == "__main__":
    main()
