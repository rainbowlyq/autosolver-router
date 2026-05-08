import argparse
import re
from collections import namedtuple
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_TEMPLATE_PATH = PROJECT_ROOT / "pack_template.py"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "dist" / "solver.py"
PACK_MARKER_RE = re.compile(r"^(?P<indent>\s*)# PACK:\s*(?P<path>.+?)\s*$")
NAMEDTUPLE_CLASS_RE = re.compile(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)\(NamedTuple\):\s*$")
FIELD_RE = re.compile(r"^    ([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$")
TYPE_ALIAS_RE = re.compile(
    r"^[A-Za-z_][A-Za-z0-9_]*\s*=\s*"
    r"(Callable|Dict|FrozenSet|Iterable|List|Optional|Tuple)(\[|\b)"
)

PackResult = namedtuple("PackResult", "output_path strip_hints_applied strip_hints_error")

VALIDATION_INPUT = "\n".join(
    [
        "task_id_list\tcourier_id\ttotal_score\twillingness",
        "T0001\tC001\t10.0\t0.5",
        "T0002\tC002\t11.0\t0.5",
        "T0001,T0002\tC003\t15.0\t0.9",
    ]
)


def pack_solver(output_path=None, template_path=None, strip_hints=True, project_root=None):
    root = Path(project_root or PROJECT_ROOT)
    template = Path(template_path or DEFAULT_TEMPLATE_PATH)
    output = Path(output_path or DEFAULT_OUTPUT_PATH)

    rendered = render_template(template, root)
    _validate_solver_code(rendered, str(output))

    final_code = rendered
    strip_hints_applied = False
    strip_hints_error = ""
    if strip_hints:
        try:
            stripped = strip_type_hints(rendered)
            stripped = drop_typing_imports(stripped)
            _validate_solver_code(stripped, str(output))
            final_code = stripped
            strip_hints_applied = True
        except Exception as exc:
            strip_hints_error = "%s: %s" % (type(exc).__name__, exc)

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="\n") as file:
        file.write(final_code)
    return PackResult(output, strip_hints_applied, strip_hints_error)


def render_template(template_path, project_root):
    template = Path(template_path).read_text(encoding="utf-8")
    rendered_lines = []

    for line in template.splitlines():
        rendered_lines.append(line)
        match = PACK_MARKER_RE.match(line)
        if not match:
            continue

        relative_path = match.group("path").strip().replace("/", "\\")
        source_path = Path(project_root) / relative_path
        source = source_path.read_text(encoding="utf-8")
        body = prepare_source_for_pack(source)
        if body:
            rendered_lines.append("")
            rendered_lines.extend(body.splitlines())
            rendered_lines.append("")

    return "\n".join(rendered_lines).rstrip() + "\n"


def prepare_source_for_pack(source):
    source = remove_top_level_imports(source)
    source = remove_type_only_aliases(source)
    source = rewrite_namedtuple_classes(source)
    return source.strip("\n")


def remove_top_level_imports(source):
    lines = source.splitlines()
    kept = []
    skipping = False
    paren_depth = 0

    for line in lines:
        if skipping:
            paren_depth += _paren_delta(line)
            if paren_depth <= 0 and not line.rstrip().endswith("\\"):
                skipping = False
            continue

        stripped = line.lstrip()
        is_top_level = stripped == line
        is_import = stripped.startswith("import ") or stripped.startswith("from ")
        if is_top_level and is_import:
            paren_depth = _paren_delta(line)
            if paren_depth > 0 or line.rstrip().endswith("\\"):
                skipping = True
            continue

        kept.append(line)

    return "\n".join(kept) + "\n"


def remove_type_only_aliases(source):
    kept = []
    for line in source.splitlines():
        if TYPE_ALIAS_RE.match(line.strip()):
            continue
        kept.append(line)
    return "\n".join(kept) + "\n"


def rewrite_namedtuple_classes(source):
    lines = source.splitlines()
    rewritten = []
    index = 0

    while index < len(lines):
        line = lines[index]
        match = NAMEDTUPLE_CLASS_RE.match(line)
        if not match:
            rewritten.append(line)
            index += 1
            continue

        class_name = match.group(1)
        block = []
        index += 1
        while index < len(lines):
            current = lines[index]
            if current.strip() and not current.startswith((" ", "\t")):
                break
            block.append(current)
            index += 1

        rewritten.extend(_rewrite_namedtuple_block(class_name, block))

    return "\n".join(rewritten) + "\n"


def _rewrite_namedtuple_block(class_name, block):
    fields = []
    defaults_by_field = {}
    remainder = []

    for line in block:
        field_match = FIELD_RE.match(line)
        if not field_match:
            remainder.append(line)
            continue

        field_name = field_match.group(1)
        type_text = field_match.group(2)
        _, default_text = _split_top_level_default(type_text)
        fields.append(field_name)
        if default_text is not None:
            defaults_by_field[field_name] = default_text.strip()

    if not fields:
        raise ValueError("NamedTuple class %s has no fields" % class_name)

    rewritten = [
        'class %s(namedtuple("%s", "%s")):' % (class_name, class_name, " ".join(fields)),
        "    __slots__ = ()",
    ]
    rewritten.extend(remainder)

    defaults = _namedtuple_defaults(fields, defaults_by_field)
    if defaults:
        rewritten.append("%s.__new__.__defaults__ = %s" % (class_name, _tuple_literal(defaults)))

    return rewritten


def _namedtuple_defaults(fields, defaults_by_field):
    if not defaults_by_field:
        return []

    first_default = None
    for index, field_name in enumerate(fields):
        if field_name in defaults_by_field:
            first_default = index
            break

    defaults = []
    for field_name in fields[first_default:]:
        if field_name not in defaults_by_field:
            raise ValueError("NamedTuple defaults must be trailing for %s" % field_name)
        defaults.append(defaults_by_field[field_name])
    return defaults


def _split_top_level_default(text):
    depth = 0
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    for index, char in enumerate(text):
        if char in "([{":
            stack.append(char)
            depth += 1
        elif char in ")]}":
            if stack and stack[-1] == pairs[char]:
                stack.pop()
            depth = max(0, depth - 1)
        elif char == "=" and depth == 0:
            return text[:index].rstrip(), text[index + 1 :].strip()
    return text.rstrip(), None


def _tuple_literal(values):
    if len(values) == 1:
        return "(%s,)" % values[0]
    return "(%s)" % ", ".join(values)


def _paren_delta(line):
    return line.count("(") + line.count("[") + line.count("{") - line.count(")") - line.count("]") - line.count("}")


def strip_type_hints(code):
    from strip_hints.strip_hints_main import strip_string_to_string

    return strip_string_to_string(code, to_empty=True, strip_nl=True)


def drop_typing_imports(code):
    kept = []
    for line in code.splitlines():
        if line.startswith("from typing import"):
            continue
        kept.append(line)
    return "\n".join(kept).rstrip() + "\n"


def _validate_solver_code(code, filename):
    namespace = {"__name__": "_packed_solver_validation"}
    compiled = compile(code, filename, "exec")
    exec(compiled, namespace)
    solve = namespace.get("solve")
    if solve is None:
        raise ValueError("packed solver does not define solve")
    output = solve(VALIDATION_INPUT)
    if not isinstance(output, list):
        raise ValueError("packed solve() returned %s, expected list" % type(output).__name__)


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Pack the AutoSolver project into one submit-ready Python file.")
    parser.add_argument("--template", default=str(DEFAULT_TEMPLATE_PATH), help="Template file with # PACK markers.")
    parser.add_argument("--output", "-o", default=str(DEFAULT_OUTPUT_PATH), help="Packed solver output path.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--strip-hints", dest="strip_hints", action="store_true", help="Try to strip type hints.")
    group.add_argument("--no-strip-hints", dest="strip_hints", action="store_false", help="Skip strip-hints.")
    parser.set_defaults(strip_hints=True)
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    result = pack_solver(
        output_path=args.output,
        template_path=args.template,
        strip_hints=args.strip_hints,
    )
    print("packed solver: %s" % result.output_path)
    if args.strip_hints and result.strip_hints_applied:
        print("strip-hints: applied")
    elif args.strip_hints:
        print("strip-hints: skipped (%s)" % result.strip_hints_error)
    else:
        print("strip-hints: disabled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
