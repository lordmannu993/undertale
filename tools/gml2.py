"""GameMaker Studio 2 front-end helpers.

The original compiler in :mod:`tools.gml` intentionally models the small GML
1.x dialect emitted by the GMX decompiler.  Yellow's source is GMS2: every
script is wrapped in a named function, enum declarations are left in the
source, and loop declarations/array literals use the newer grammar.  This
module keeps the source-shape work separate from the shared Pratt parser while
using ``tools.gml`` for the actual AST and Lua emission.

It is deliberately a source reader, not a permissive regex converter.  Strings
and comments are masked before structure is located, matching the strict JSON
reader used by the asset front end.  A malformed declaration raises
``CompileError`` with its source name rather than producing plausible-looking
but wrong Lua.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

try:  # imported as ``tools.gml2`` from the repository root
    from .gml import CompileError, Emitter, Parser, emit_module, quote
except ImportError:  # loaded by the standalone conversion scripts
    from gml import CompileError, Emitter, Parser, emit_module, quote


@dataclass(frozen=True)
class GMS2Function:
    """One named function declaration from a GMS2 script file."""

    name: str
    parameters: tuple[tuple[str, str | None], ...]
    body: str
    constructor: bool = False


def mask_source(text: str) -> str:
    """Blank strings/comments while preserving offsets and line breaks."""
    out = list(text)
    i, n, quote_char = 0, len(text), None
    while i < n:
        if quote_char:
            if text[i] == "\\":
                out[i] = " "
                if i + 1 < n and text[i + 1] != "\n":
                    out[i + 1] = " "
                i += 2
            elif text[i] == quote_char:
                out[i] = " "
                quote_char = None
                i += 1
            else:
                if text[i] != "\n":
                    out[i] = " "
                i += 1
            continue
        if text[i] in "\"'":
            quote_char = text[i]
            out[i] = " "
            i += 1
            continue
        if text.startswith("//", i):
            out[i] = out[i + 1] = " "
            i += 2
            while i < n and text[i] != "\n":
                out[i] = " "
                i += 1
            continue
        if text.startswith("/*", i):
            out[i] = out[i + 1] = " "
            i += 2
            while i < n:
                if text.startswith("*/", i):
                    out[i] = out[i + 1] = " "
                    i += 2
                    break
                if text[i] != "\n":
                    out[i] = " "
                i += 1
            continue
        i += 1
    return "".join(out)


def _matching(mask: str, opening: int, left: str, right: str) -> int:
    depth = 0
    for i in range(opening, len(mask)):
        if mask[i] == left:
            depth += 1
        elif mask[i] == right:
            depth -= 1
            if depth == 0:
                return i
    raise CompileError(f"unterminated GMS2 {left}{right} block")


def _split_top_level(text: str, separator: str = ",") -> list[str]:
    """Split a parameter/enum list without splitting nested expressions."""
    result, start, stack, masked = [], 0, [], mask_source(text)
    pairs = {"(": ")", "[": "]", "{": "}"}
    for i, char in enumerate(masked):
        if char in pairs:
            stack.append(pairs[char])
        elif stack and char == stack[-1]:
            stack.pop()
        elif not stack and char == separator:
            result.append(text[start:i].strip())
            start = i + 1
    tail = text[start:].strip()
    if tail:
        result.append(tail)
    return result


def _top_level_index(text: str, separator: str) -> int:
    """Return the first un-nested separator in a parameter/enum item."""
    masked = mask_source(text)
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack = []
    for index, char in enumerate(masked):
        if char in pairs:
            stack.append(pairs[char])
        elif stack and char == stack[-1]:
            stack.pop()
        elif not stack and char == separator:
            return index
    return -1


def _parse_parameters(text: str) -> tuple[tuple[str, str | None], ...]:
    parameters = []
    for raw in _split_top_level(text):
        if not raw:
            continue
        equal = _top_level_index(raw, "=")
        if equal >= 0:
            name, default = raw[:equal].strip(), raw[equal + 1:].strip()
        else:
            name, default = raw.strip(), None
        if not re.fullmatch(r"[A-Za-z_]\w*", name):
            raise CompileError(f"invalid GMS2 function parameter {raw!r}")
        parameters.append((name, default))
    return tuple(parameters)


def extract_functions(text: str, source: str = "GMS2") -> tuple[list[GMS2Function], str]:
    """Extract named ``function name(args) { ... }`` blocks.

    Returns the declarations and the source with those declarations blanked.
    The latter is useful for the rare file that contains global initialization
    outside its function declarations.
    """
    mask = mask_source(text)
    pattern = re.compile(r"\bfunction\s+([A-Za-z_]\w*)\s*\(")
    found: list[tuple[GMS2Function, int, int]] = []
    for match in pattern.finditer(mask):
        open_paren = mask.find("(", match.start(), match.end())
        close_paren = _matching(mask, open_paren, "(", ")")
        cursor = close_paren + 1
        while cursor < len(mask) and mask[cursor].isspace():
            cursor += 1
        constructor = False
        if mask.startswith("constructor", cursor):
            constructor = True
            cursor += len("constructor")
            while cursor < len(mask) and mask[cursor].isspace():
                cursor += 1
        if cursor >= len(mask) or mask[cursor] != "{":
            line = text.count("\n", 0, match.start()) + 1
            raise CompileError(f"{source}:{line}: function {match.group(1)} has no body")
        close_brace = _matching(mask, cursor, "{", "}")
        params = _parse_parameters(text[open_paren + 1:close_paren])
        found.append((GMS2Function(match.group(1), params, text[cursor + 1:close_brace], constructor),
                     match.start(), close_brace + 1))
    blanked = list(text)
    for _, start, end in found:
        for i in range(start, end):
            if blanked[i] != "\n":
                blanked[i] = " "
    return [item[0] for item in found], "".join(blanked)


def _numeric_value(raw: str, current: int, values: dict[str, int]) -> int:
    raw = raw.strip()
    if not raw:
        return current
    try:
        if raw.startswith("$"):
            return int(raw[1:], 16)
        return int(raw, 0)
    except ValueError:
        if raw in values:
            return values[raw]
    raise CompileError(f"GMS2 enum value is not a recoverable integer: {raw!r}")


def strip_enums(text: str, source: str = "GMS2") -> tuple[str, dict[str, int]]:
    """Remove enum declarations and replace ``Enum.Member`` uses by integers."""
    mask = mask_source(text)
    enum_pattern = re.compile(r"\benum\s+([A-Za-z_]\w*)\s*\{")
    replacements: list[tuple[int, int, str]] = []
    values: dict[str, int] = {}
    for match in enum_pattern.finditer(mask):
        opening = mask.find("{", match.start(), match.end())
        closing = _matching(mask, opening, "{", "}")
        enum_name = match.group(1)
        current = 0
        for entry in _split_top_level(text[opening + 1:closing]):
            equal = _top_level_index(entry, "=")
            member = entry[:equal].strip() if equal >= 0 else entry.strip()
            if not member:
                continue
            raw_value = entry[equal + 1:] if equal >= 0 else ""
            current = _numeric_value(raw_value, current, values)
            values[f"{enum_name}.{member}"] = current
            current += 1
        replacements.append((match.start(), closing + 1, ""))
    if replacements:
        chars = list(text)
        for start, end, replacement in replacements:
            chars[start:end] = [replacement] + [" "] * (end - start - len(replacement))
        text = "".join(chars)
    if not values:
        return text, values
    mask = mask_source(text)
    member_pattern = re.compile(r"\b([A-Za-z_]\w*)\.([A-Za-z_]\w*)\b")
    replacements = []
    for match in member_pattern.finditer(mask):
        value = values.get(f"{match.group(1)}.{match.group(2)}")
        if value is not None:
            replacements.append((match.start(), match.end(), str(value)))
    if replacements:
        chars = list(text)
        for start, end, replacement in reversed(replacements):
            chars[start:end] = replacement
        text = "".join(chars)
    return text, values


def _parameter_prefix(parameters: tuple[tuple[str, str | None], ...]) -> str:
    lines = []
    for index, (name, default) in enumerate(parameters):
        # Parameters are locals in GMS2.  Declaring them through the shared
        # emitter keeps later assignments inside E._locals rather than turning
        # a script-with-no-instance into a room variable.
        lines.append(f"var {name}=argument{index};")
        if default is not None:
            lines.append(f"if(argument_count < {index + 1}) {name}={default};")
    return "\n".join(lines) + ("\n" if lines else "")


def compile_gml2(text: str, source: str = "GMS2", resolver=None) -> tuple[str, tuple]:
    """Compile a GMS2 file containing exactly one named function.

    The function header is removed and its named parameters are bound to the
    runtime's GameMaker-compatible ``argument0`` scope.  Files with multiple
    functions should use :func:`compile_gml2_functions` so each export remains
    addressable by name.
    """
    text, _ = strip_enums(text, source)
    functions, outside = extract_functions(text, source)
    if len(functions) > 1:
        raise CompileError(f"{source}: contains {len(functions)} named functions; use compile_gml2_functions")
    if functions and functions[0].constructor:
        raise CompileError(f"{source}: constructor functions are unsupported outside the explicit GMLive stop")
    if functions:
        body = _parameter_prefix(functions[0].parameters) + functions[0].body
    else:
        body = outside
    ast = Parser(body).program()
    emitter = Emitter(resolver=resolver)
    compiled = emitter.function(ast, source)
    return compiled, ast


def compile_gml2_functions(text: str, source: str = "GMS2", resolver=None) -> tuple[list[tuple[str, str, tuple]], dict]:
    """Compile every named function in one GMS2 file.

    The result contains ``(name, Lua function expression, AST)`` records and a
    small report dictionary.  A function-free file is represented as a single
    ``__main__`` export, which lets initialization scripts use the same module
    format as ordinary scripts.
    """
    text, enums = strip_enums(text, source)
    functions, outside = extract_functions(text, source)
    if not functions:
        code, ast = compile_gml2(outside, source, resolver)
        return [("__main__", code, ast)], {"enums": enums, "function_count": 0, "global_source": outside}
    constructors = [function.name for function in functions if function.constructor]
    if constructors:
        raise CompileError(f"{source}: constructor functions are unsupported: {constructors}")
    records = []
    for function in functions:
        body = _parameter_prefix(function.parameters) + function.body
        ast = Parser(body).program()
        records.append((function.name, Emitter(resolver=resolver).function(ast, f"{source}::{function.name}"), ast))
    return records, {"enums": enums, "function_count": len(functions), "global_source": outside}


def function_expression(module: str) -> str:
    """The function expression of a generated module, without its ``return``.

    Object events and multi-export scripts are embedded in a larger module, so
    the header comment and the ``return`` keyword have to come off again.  One
    implementation, used by both front ends.
    """
    marker = "return function"
    position = module.find(marker)
    if position < 0:
        raise CompileError("the emitter did not return a function")
    return module[position + len("return "):].strip()


def compile_gml2_event(text: str, source: str = "GMS2", resolver=None) -> tuple[str, tuple, list[str]]:
    """Compile one object event body, which is bare statements rather than a script.

    Studio 2 lets an event declare its own functions.  They are *not* project
    scripts, so lifting them into the script namespace would let one object's
    ``state_switch`` shadow another's.  Each declaration is emitted into the
    event's own GML scope (``E._locals``) instead, and ``Runtime:call`` resolves
    a scope-local function before any builtin or script of the same name.

    Returns the Lua module text, the body AST and the declared local names.
    """
    text, _ = strip_enums(text, source)
    functions, outside = extract_functions(text, source)
    constructors = [function.name for function in functions if function.constructor]
    if constructors:
        raise CompileError(f"{source}: constructor functions are unsupported: {constructors}")
    prologue = []
    for function in functions:
        body = _parameter_prefix(function.parameters) + function.body
        expression = Emitter(resolver=resolver).function_expression(
            Parser(body).program(), f"{source}::{function.name}")
        prologue.append(f"E._locals[{quote(function.name)}] = {expression}")
    ast = Parser(outside).program()
    return emit_module(ast, source, resolver=resolver, prologue=prologue), ast, [f.name for f in functions]


# Spellings used by callers and hidden tooling; keep one implementation.
compile_gms2 = compile_gml2
compile_gms2_functions = compile_gml2_functions
compile_gms2_event = compile_gml2_event
