"""tool-output-format - render tool output as LLM-friendly markdown.

Raw JSON makes for bad tool-result content. The LLM is better at
reasoning over short markdown lists than over a nested object with
unsorted keys. `format_for_llm()` walks the value and emits a compact
markdown rendering: scalars become plain text, dicts become key/value
blocks, lists of dicts become tables, lists of scalars become bullets.

    from tool_output_format import format_for_llm

    out = format_for_llm({"users": [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
    ]})

    # ## users
    # | name  | age |
    # | ----- | --- |
    # | Alice | 30  |
    # | Bob   | 25  |

Per-tool custom formatters override the default for specific tools:

    fmt = OutputFormatter()
    fmt.register("search_web", lambda result: "\\n".join(
        f"- [{r['title']}]({r['url']})" for r in result
    ))
    text = fmt.format("search_web", search_results)

`max_chars` truncates with a "…truncated, X chars omitted" trailer so
you can cap tool-result size without paying for the LLM's confusion.
"""

from __future__ import annotations

from typing import Any, Callable

__version__ = "0.1.0"
__all__ = [
    "format_for_llm",
    "OutputFormatter",
    "render_dict",
    "render_list",
    "render_table",
    "truncate",
]


# ---- core renderers -------------------------------------------------------


def render_dict(d: dict[str, Any], *, level: int = 0) -> str:
    """Render a dict as a markdown key/value block. Nested dicts indent."""
    if not d:
        return "*(empty)*"
    lines: list[str] = []
    indent = "  " * level
    for k, v in d.items():
        key = f"**{k}**"
        if isinstance(v, dict):
            lines.append(f"{indent}- {key}:")
            sub = render_dict(v, level=level + 1)
            for sl in sub.splitlines():
                lines.append(f"{indent}{sl}" if not sl.startswith(indent) else sl)
        elif isinstance(v, list):
            if v and all(isinstance(item, dict) for item in v):
                lines.append(f"{indent}- {key}:")
                lines.append(render_table(v))
            else:
                lines.append(f"{indent}- {key}: {render_list(v)}")
        else:
            lines.append(f"{indent}- {key}: {_scalar(v)}")
    return "\n".join(lines)


def render_list(lst: list[Any]) -> str:
    """Render a list as inline comma-separated values."""
    if not lst:
        return "*(empty)*"
    return ", ".join(_scalar(item) for item in lst)


def render_table(rows: list[dict[str, Any]]) -> str:
    """Render a list-of-dicts as a markdown table.

    Columns are the union of keys, ordered by first appearance.
    Missing cells render as empty strings.
    """
    if not rows:
        return "*(empty)*"
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for k in row:
            if k not in seen:
                seen.add(k)
                columns.append(k)
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join("---" for _ in columns) + " |"
    out: list[str] = [header, sep]
    for row in rows:
        cells = [_scalar(row.get(c, "")) for c in columns]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)


def truncate(text: str, max_chars: int) -> str:
    """Truncate text to `max_chars`, adding a trailer summary."""
    if max_chars < 1:
        raise ValueError("max_chars must be >= 1")
    if len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    trailer = f"\n…truncated, {omitted} chars omitted"
    cap = max_chars - len(trailer)
    if cap < 1:
        return text[:max_chars]
    return text[:cap] + trailer


# ---- top-level format -----------------------------------------------------


def format_for_llm(value: Any, *, max_chars: int | None = None) -> str:
    """Render any value to a markdown string.

    Scalars become plain text. Dicts become key/value blocks. Lists of
    dicts become tables; other lists become comma-separated. If
    `max_chars` is set, the result is truncated to that length with a
    `…truncated` trailer.
    """
    text = _format_root(value)
    if max_chars is not None:
        text = truncate(text, max_chars)
    return text


def _format_root(value: Any) -> str:
    if isinstance(value, dict):
        return render_dict(value)
    if isinstance(value, list):
        if value and all(isinstance(item, dict) for item in value):
            return render_table(value)
        return render_list(value)
    return _scalar(value)


def _scalar(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        # collapse newlines so tables don't break
        return v.replace("\n", " ").replace("|", "\\|")
    if isinstance(v, dict):
        # nested dict in a cell — flatten to "k=v, k=v"
        return ", ".join(f"{k}={_scalar(val)}" for k, val in v.items())
    if isinstance(v, list):
        return "[" + ", ".join(_scalar(x) for x in v) + "]"
    return str(v)


# ---- OutputFormatter (per-tool registry) ---------------------------------


FormatterFn = Callable[[Any], str]


class OutputFormatter:
    """Per-tool formatter registry.

    Register a callable for each tool name; calling `format(tool_name, output)`
    runs that callable. Tools without a registered formatter fall back to the
    default `format_for_llm`.
    """

    def __init__(self) -> None:
        self._formatters: dict[str, FormatterFn] = {}

    def register(self, tool_name: str, fn: FormatterFn) -> None:
        if not callable(fn):
            raise TypeError("formatter must be callable")
        self._formatters[tool_name] = fn

    def unregister(self, tool_name: str) -> bool:
        return self._formatters.pop(tool_name, None) is not None

    def has(self, tool_name: str) -> bool:
        return tool_name in self._formatters

    def format(
        self,
        tool_name: str,
        output: Any,
        *,
        max_chars: int | None = None,
    ) -> str:
        fn = self._formatters.get(tool_name)
        if fn is not None:
            text = fn(output)
            if not isinstance(text, str):
                text = str(text)
        else:
            text = format_for_llm(output)
        if max_chars is not None:
            text = truncate(text, max_chars)
        return text

    def tool_names(self) -> list[str]:
        return sorted(self._formatters)
