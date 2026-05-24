"""Tests for tool_output_format."""

from __future__ import annotations

import pytest

from tool_output_format import (
    OutputFormatter,
    format_for_llm,
    render_dict,
    render_list,
    render_table,
    truncate,
)


# ---- scalar rendering ---------------------------------------------------


def test_format_scalar_string():
    assert format_for_llm("hello") == "hello"


def test_format_scalar_int():
    assert format_for_llm(42) == "42"


def test_format_scalar_float():
    assert format_for_llm(3.14) == "3.14"


def test_format_scalar_bool():
    assert format_for_llm(True) == "true"
    assert format_for_llm(False) == "false"


def test_format_scalar_none_is_empty_string():
    assert format_for_llm(None) == ""


# ---- dict rendering -----------------------------------------------------


def test_format_dict_simple():
    out = format_for_llm({"name": "Alice", "age": 30})
    assert "**name**" in out
    assert "Alice" in out
    assert "**age**" in out
    assert "30" in out


def test_format_dict_empty():
    assert format_for_llm({}) == "*(empty)*"


def test_render_dict_with_nested_dict():
    out = render_dict({"outer": {"inner": "value"}})
    assert "**outer**" in out
    assert "**inner**" in out


def test_render_dict_with_inline_list():
    out = render_dict({"tags": ["a", "b", "c"]})
    assert "tags" in out
    assert "a, b, c" in out


def test_render_dict_with_list_of_dicts_uses_table():
    out = render_dict({
        "users": [{"name": "Alice"}, {"name": "Bob"}],
    })
    assert "| name |" in out
    assert "Alice" in out
    assert "Bob" in out


# ---- list rendering -----------------------------------------------------


def test_format_list_of_scalars():
    out = format_for_llm(["a", "b", "c"])
    assert out == "a, b, c"


def test_format_list_empty():
    assert format_for_llm([]) == "*(empty)*"


def test_format_list_of_dicts_as_table():
    out = format_for_llm([
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
    ])
    assert "| name | age |" in out
    assert "Alice" in out


def test_render_table_missing_cells_are_empty():
    out = render_table([
        {"a": 1, "b": 2},
        {"a": 3},  # missing b
    ])
    lines = out.splitlines()
    # last row should have empty b cell
    assert lines[-1].count("|") == 3  # 4 columns including padding
    assert "3" in lines[-1]


def test_render_table_column_order_first_appearance():
    out = render_table([{"a": 1, "b": 2}, {"c": 3, "a": 4}])
    header = out.splitlines()[0]
    # 'a' and 'b' from row 1, then 'c' from row 2
    assert "| a | b | c |" in header


def test_render_list_empty():
    assert render_list([]) == "*(empty)*"


# ---- scalar handling inside cells --------------------------------------


def test_table_cell_escapes_pipe():
    out = render_table([{"name": "a|b"}])
    assert "a\\|b" in out


def test_table_cell_collapses_newlines():
    out = render_table([{"text": "line1\nline2"}])
    assert "line1 line2" in out


def test_scalar_dict_in_cell_flattened():
    out = render_table([{"meta": {"k": "v", "n": 1}}])
    assert "k=v" in out
    assert "n=1" in out


# ---- truncate ---------------------------------------------------------


def test_truncate_under_limit_returns_unchanged():
    assert truncate("abc", 100) == "abc"


def test_truncate_over_limit_adds_trailer():
    out = truncate("a" * 1000, 200)
    assert len(out) <= 200
    assert "…truncated" in out
    assert "omitted" in out


def test_truncate_max_chars_must_be_positive():
    with pytest.raises(ValueError):
        truncate("x", 0)


def test_format_for_llm_with_max_chars():
    big = {"text": "x" * 5000}
    out = format_for_llm(big, max_chars=200)
    assert len(out) <= 200
    assert "…truncated" in out


# ---- OutputFormatter --------------------------------------------------


def test_formatter_default_falls_back_to_format_for_llm():
    fmt = OutputFormatter()
    out = fmt.format("unknown", {"a": 1})
    assert "**a**" in out and "1" in out


def test_formatter_custom_per_tool():
    fmt = OutputFormatter()
    fmt.register("search", lambda r: "\n".join(f"- {x}" for x in r))
    out = fmt.format("search", ["one", "two"])
    assert out == "- one\n- two"


def test_formatter_unregister():
    fmt = OutputFormatter()
    fmt.register("search", lambda r: "custom")
    assert fmt.unregister("search") is True
    assert fmt.unregister("search") is False
    # falls back to default after unregister
    assert fmt.format("search", "x") == "x"


def test_formatter_has_returns_bool():
    fmt = OutputFormatter()
    fmt.register("a", lambda r: "")
    assert fmt.has("a") is True
    assert fmt.has("b") is False


def test_formatter_coerces_non_string_return():
    fmt = OutputFormatter()
    fmt.register("a", lambda r: 42)  # returns int
    out = fmt.format("a", "ignored")
    assert out == "42"


def test_formatter_max_chars_applied():
    fmt = OutputFormatter()
    fmt.register("big", lambda r: "x" * 10000)
    out = fmt.format("big", None, max_chars=200)
    assert len(out) <= 200


def test_formatter_rejects_non_callable_registration():
    fmt = OutputFormatter()
    with pytest.raises(TypeError):
        fmt.register("a", "not callable")  # type: ignore[arg-type]


def test_formatter_tool_names_sorted():
    fmt = OutputFormatter()
    fmt.register("zebra", lambda r: "")
    fmt.register("alpha", lambda r: "")
    assert fmt.tool_names() == ["alpha", "zebra"]
