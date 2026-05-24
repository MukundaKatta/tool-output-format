# tool-output-format

[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/tool-output-format.svg)](https://pypi.org/project/tool-output-format/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Render raw tool output as LLM-friendly markdown.** Zero deps.

```python
from tool_output_format import format_for_llm

out = format_for_llm({"users": [
    {"name": "Alice", "age": 30},
    {"name": "Bob", "age": 25},
]})
# - **users**:
# | name | age |
# | --- | --- |
# | Alice | 30 |
# | Bob | 25 |
```

LLMs reason better over a compact markdown table than over a nested JSON object. `format_for_llm` walks the value and emits the right shape: scalars become plain text, dicts become key/value blocks, lists of dicts become tables, lists of scalars become comma-separated.

**Per-tool custom formatters** for the cases where the default isn't right:

```python
from tool_output_format import OutputFormatter

fmt = OutputFormatter()
fmt.register("search_web", lambda results: "\n".join(
    f"- [{r['title']}]({r['url']})" for r in results
))

fmt.format("search_web", search_results)
fmt.format("anything_else", value)        # falls back to default
```

**Optional truncation** — cap tool-result size before it lands in the LLM context:

```python
fmt.format("search_web", results, max_chars=2000)
# adds "…truncated, X chars omitted" trailer when needed
```

## Why

Half of LLM tools return JSON that the model then has to parse mentally before reasoning over. The other half return text shaped like "[INFO 2024-...] result1\n[INFO 2024-...] result2" that drowns useful content in framing. `tool-output-format` is the small step between "raw tool output" and "what the LLM sees" so the LLM spends its context on the actual answer.

## Install

```bash
pip install tool-output-format
```

## API

```python
from tool_output_format import (
    format_for_llm,        # top-level: any value → markdown string
    OutputFormatter,       # per-tool formatter registry
    render_dict,           # dict → markdown key/value block
    render_list,           # list of scalars → "a, b, c"
    render_table,          # list of dicts → markdown table
    truncate,              # truncate w/ "…truncated" trailer
)
```

Table rendering quirks: column order = union of keys ordered by first appearance; missing cells render as empty; cell newlines collapsed to spaces; pipes escaped.

## Companion libraries

- [`tool-output-truncate-py`](https://github.com/MukundaKatta/tool-output-truncate-py) — char/line-aware truncation with head/tail/middle strategies (more sophisticated than this lib's plain truncate).
- [`tool-secret-scrubber`](https://github.com/MukundaKatta/tool-secret-scrubber) — strip secrets before formatting.
- [`agentvet`](https://github.com/MukundaKatta/agentvet) — validate tool args before they're passed to the tool.

## License

MIT
