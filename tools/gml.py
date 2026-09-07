"""A small, strict GML 1.x -> Lua 5.1 compiler for this GMX checkout.

This is a tokenizer/Pratt parser, not a regex substitution of source code.
Unsupported syntax is a build error; an event is never silently discarded.
Generated functions receive a compatibility runtime R and a GML scope E.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re


class CompileError(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int


LEXER = re.compile(
    r"(?P<space>\s+)|(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)"
    r"|(?P<string>\"(?:\\[\s\S]|[^\"\\])*\"|'(?:\\[\s\S]|[^'\\])*')"
    r"|(?P<number>\$[\da-fA-F]+|0[xX][\da-fA-F]+|(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?)"
    r"|(?P<name>[a-zA-Z_][a-zA-Z_0-9]*)"
    r"|(?P<op>\+\+|--|\+=|-=|\*=|/=|%=|==|!=|<>|<=|>=|&&|\|\||\^\^|<<|>>|[{}()\[\],;:.?+*/%<>=!~&|^\-])"
)


def tokenize(text: str) -> list[Token]:
    tokens = []
    pos, line, column = 0, 1, 1
    while pos < len(text):
        m = LEXER.match(text, pos)
        if not m:
            raise CompileError(f"{line}:{column}: unexpected character {text[pos:pos+25]!r}")
        raw = m.group()
        if m.lastgroup not in ("space", "comment"):
            tokens.append(Token(m.lastgroup, raw, line, column))
        count = raw.count("\n")
        column = len(raw.rsplit("\n", 1)[-1]) + 1 if count else column + len(raw)
        line += count
        pos = m.end()
    tokens.append(Token("eof", "<eof>", line, column))
    return tokens


def decode_string(raw: str) -> str:
    # The decompiler emits C-style escapes, including \' inside double quotes.
    s, out, i = raw[1:-1], [], 0
    escapes = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"', "'": "'", "0": "\0"}
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            i += 1
            out.append(escapes.get(s[i], "\\" + s[i]))
        else:
            out.append(s[i])
        i += 1
    return "".join(out)


def quote(s: str) -> str:
    # JSON \u escapes are not Lua 5.1 escapes. Write UTF-8 characters literally.
    result = json.dumps(s, ensure_ascii=False)
    return re.sub(r"\\u00([0-9a-f]{2})", lambda m: "\\%03d" % int(m[1], 16), result)


# AST nodes are tuples, kept intentionally simple so the audit can walk them.
PRECEDENCE = {"or": 1, "||": 1, "xor": 2, "^^": 2, "and": 3, "&&": 3,
              "|": 4, "^": 5, "&": 6, "=": 7, "==": 7, "!=": 7, "<>": 7,
              "<": 8, "<=": 8, ">": 8, ">=": 8, "<<": 9, ">>": 9,
              "+": 10, "-": 10, "*": 11, "/": 11, "%": 11, "div": 11, "mod": 11}
ASSIGN = {"=", "+=", "-=", "*=", "/=", "%="}


class Parser:
    def __init__(self, text: str):
        self.tokens = tokenize(text)
        self.i = 0

    @property
    def t(self):
        return self.tokens[self.i]

    def pop(self):
        t = self.t
        self.i += 1
        return t

    def accept(self, value):
        if self.t.value == value:
            self.i += 1
            return True
        return False

    def expect(self, value):
        if not self.accept(value):
            self.fail(f"expected {value!r}, found {self.t.value!r}")

    def fail(self, message):
        raise CompileError(f"{self.t.line}:{self.t.column}: {message}")

    def program(self):
        nodes = []
        while self.t.kind != "eof":
            nodes.append(self.statement())
        return ("block", nodes)

    def block(self):
        nodes = []
        close = "end" if self.accept("begin") else "}"
        if close == "}":
            self.expect("{")
        while self.t.value != close:
            if self.t.kind == "eof":
                self.fail(f"unterminated block (expected {close})")
            nodes.append(self.statement())
        self.pop()
        return ("block", nodes)

    def condition(self):
        # GML 1.x permits both `if (x == 1)` and `if x = 1 { ... }`.
        return self.expr(equal=True)

    def statement(self):
        v = self.t.value
        if v in ("{", "begin"):
            return self.block()
        if self.accept(";"):
            return ("empty",)
        if self.accept("if"):
            test = self.condition()
            self.accept("then")
            yes = self.statement()
            no = self.statement() if self.accept("else") else None
            return ("if", test, yes, no)
        if self.accept("while"):
            return ("while", self.condition(), self.statement())
        if self.accept("repeat"):
            return ("repeat", self.expr(), self.statement())
        if self.accept("with"):
            return ("with", self.expr(), self.statement())
        if self.accept("for"):
            self.expect("(")
            init = self.simple() if self.t.value != ";" else ("empty",)
            self.expect(";")
            test = self.expr(equal=True) if self.t.value != ";" else ("number", "1")
            self.expect(";")
            inc = self.simple() if self.t.value != ")" else ("empty",)
            self.expect(")")
            return ("for", init, test, inc, self.statement())
        if self.accept("do"):
            body = self.statement()
            self.expect("until")
            cond = self.condition()
            self.accept(";")
            return ("until", body, cond)
        if self.accept("switch"):
            test = self.condition()
            self.expect("{")
            cases = []
            while not self.accept("}"):
                if self.accept("case"):
                    case = self.expr()
                elif self.accept("default"):
                    case = None
                else:
                    self.fail("expected case or default")
                self.expect(":")
                body = []
                while self.t.value not in ("case", "default", "}", "<eof>"):
                    body.append(self.statement())
                cases.append((case, ("block", body)))
            return ("switch", test, cases)
        if v in ("exit", "break", "continue"):
            self.pop()
            self.accept(";")
            return (v,)
        if self.accept("return"):
            val = self.expr() if self.t.value not in (";", "}", "<eof>") else ("number", "0")
            self.accept(";")
            return ("return", val)
        if v in ("var", "globalvar"):
            self.pop()
            declarations = []
            while True:
                name = self.pop()
                if name.kind != "name":
                    self.fail("expected variable name")
                value = self.expr() if self.accept("=") else ("number", "0")
                declarations.append((name.value, value))
                if not self.accept(","):
                    break
            self.accept(";")
            return (v, declarations)
        node = self.simple()
        self.accept(";")
        return node

    def simple(self):
        left = self.expr()
        if self.t.value in ASSIGN:
            op = self.pop().value
            if left[0] not in ("name", "member", "index"):
                self.fail("invalid assignment target")
            return ("assign", op, left, self.expr())
        if left[0] in ("call", "post", "pre"):
            return ("expression", left)
        self.fail(f"expected assignment or call after {left!r}")

    def expr(self, min_prec=0, equal=False):
        tok = self.pop()
        if tok.value in ("-", "+", "!", "not", "~", "++", "--"):
            node = ("pre" if tok.value in ("++", "--") else "unary", tok.value, self.expr(12, equal))
        elif tok.value == "(":
            node = self.expr(equal=equal)
            self.expect(")")
        elif tok.kind == "number":
            node = ("number", tok.value)
        elif tok.kind == "string":
            node = ("string", decode_string(tok.value))
        elif tok.kind == "name":
            node = ("name", tok.value)
        else:
            self.i -= 1
            self.fail(f"expected expression, found {tok.value!r}")
        while True:
            op = self.t.value
            if op == "(":
                self.pop()
                args = []
                if self.t.value != ")":
                    while True:
                        args.append(self.expr(equal=equal))
                        if not self.accept(","):
                            break
                self.expect(")")
                node = ("call", node, args)
            elif op == ".":
                self.pop()
                name = self.pop()
                if name.kind != "name":
                    self.fail("expected member name")
                node = ("member", node, name.value)
            elif op == "[":
                self.pop()
                indices = [self.expr(equal=equal)]
                if self.accept(","):
                    indices.append(self.expr(equal=equal))
                self.expect("]")
                node = ("index", node, indices)
            elif op in ("++", "--"):
                self.pop()
                node = ("post", op, node)
            elif op in PRECEDENCE and (op != "=" or equal) and PRECEDENCE[op] >= min_prec:
                self.pop()
                node = ("binary", op, node, self.expr(PRECEDENCE[op] + 1, equal))
            elif op == "?" and min_prec == 0:
                self.pop()
                yes = self.expr(equal=equal)
                self.expect(":")
                node = ("ternary", node, yes, self.expr(equal=equal))
            else:
                break
        return node


def walk(node):
    if not isinstance(node, (tuple, list)):
        return
    if node and isinstance(node[0], str):
        yield node
    for child in node:
        if isinstance(child, (tuple, list)):
            yield from walk(child)


class Emitter:
    def __init__(self):
        self.lines = []
        self.indent = 1
        self.counter = 0
        self.loops = []

    def line(self, text):
        self.lines.append("    " * self.indent + text)

    def unique(self):
        self.counter += 1
        return f"__v{self.counter}"

    def binary(self, op, a, b):
        if op == "+":
            return f"R.add({a}, {b})"
        if op in ("&&", "and", "||", "or"):
            logical = "and" if op in ("&&", "and") else "or"
            return f"R.num(R.truth({a}) {logical} R.truth({b}))"
        if op in ("^^", "xor"):
            return f"R.num(R.truth({a}) ~= R.truth({b}))"
        if op in ("=", "==", "!=", "<>", "<", ">", "<=", ">="):
            op = {"=": "==", "!=": "~=", "<>": "~="}.get(op, op)
            return f"R.num({a} {op} {b})"
        if op in ("%", "mod"):
            return f"R.mod({a}, {b})"
        if op == "div":
            return f"R.div({a}, {b})"
        if op in ("&", "|", "^", "<<", ">>"):
            return f"R.bit.{ {'&':'band','|':'bor','^':'bxor','<<':'lshift','>>':'rshift'}[op]}({a}, {b})"
        return f"({a} {op} {b})"

    def reference(self, n):
        if n[0] == "name":
            return "E", quote(n[1])
        if n[0] == "member":
            return self.expr(n[1]), quote(n[2])
        if n[0] == "index":
            owner, key = self.reference(n[1])
            indices = [self.expr(i) for i in n[2]]
            if len(indices) == 1:
                return f"R:array({owner}, {key}, E)", indices[0]
            return f"R:arrayRow({owner}, {key}, {indices[0]}, E)", indices[1]
        raise CompileError(f"unsupported lvalue: {n}")

    def expr(self, n):
        k = n[0]
        if k == "number":
            return str(int(n[1][1:], 16)) if n[1].startswith("$") else n[1]
        if k == "string":
            return quote(n[1])
        if k == "name":
            return f"E[{quote(n[1])}]"
        if k in ("member", "index"):
            owner, key = self.reference(n)
            return f"R:get({owner}, {key}, E)"
        if k == "binary":
            return self.binary(n[1], self.expr(n[2]), self.expr(n[3]))
        if k == "unary":
            a = self.expr(n[2])
            if n[1] in ("not", "!"):
                return f"R.num(not R.truth({a}))"
            if n[1] == "~":
                return f"R.bit.bnot({a})"
            return f"({n[1]}{a})" if n[1] != "+" else a
        if k in ("pre", "post"):
            owner, key = self.reference(n[2])
            return f"R:increment({owner}, {key}, {1 if n[1] == '++' else -1}, {str(k == 'post').lower()}, E)"
        if k == "ternary":
            # Lua's a and b or c is incorrect if b is false; use lazy closures.
            return f"R.ternary({self.expr(n[1])}, function() return {self.expr(n[2])} end, function() return {self.expr(n[3])} end)"
        if k == "call":
            if n[1][0] != "name":
                raise CompileError("GML 1.x function calls must name a script or builtin")
            args = "".join(", " + self.expr(a) for a in n[2])
            return f"R:call({quote(n[1][1])}, E{args})"
        raise CompileError(f"unsupported expression: {n}")

    def loopbody(self, body, increment=None):
        # Lua 5.1 has no continue. An inner repeat supplies it; __break carries
        # a real break to the enclosing loop without skipping a for increment.
        brk = self.unique()
        self.line(f"local {brk} = false")
        self.line("repeat")
        self.indent += 1
        self.loops.append(("loop", brk))
        self.stmt(body)
        self.loops.pop()
        self.indent -= 1
        self.line("until true")
        self.line(f"if {brk} then break end")
        if increment:
            self.stmt(increment)

    def stmt(self, n):
        k = n[0]
        if k in ("empty",):
            return
        if k == "block":
            for s in n[1]:
                self.stmt(s)
        elif k == "assign":
            owner, key = self.reference(n[2])
            # Resolve selectors/array indices once, including a[i++] += x.
            o, q = self.unique(), self.unique()
            self.line("do")
            self.indent += 1
            self.line(f"local {o}, {q} = {owner}, {key}")
            rhs = self.expr(n[3])
            if n[1] != "=":
                rhs = self.binary(n[1][0], f"R:get({o}, {q}, E)", rhs)
            self.line(f"R:set({o}, {q}, {rhs}, E)")
            self.indent -= 1
            self.line("end")
        elif k == "expression":
            self.line(self.expr(n[1]))
        elif k == "if":
            self.line(f"if R.truth({self.expr(n[1])}) then")
            self.indent += 1
            self.stmt(n[2])
            self.indent -= 1
            if n[3]:
                self.line("else")
                self.indent += 1
                self.stmt(n[3])
                self.indent -= 1
            self.line("end")
        elif k in ("while", "repeat", "until", "for", "with"):
            if k == "for":
                self.stmt(n[1])
                self.line(f"while R.truth({self.expr(n[2])}) do")
                body = n[4]
            elif k == "while":
                self.line(f"while R.truth({self.expr(n[1])}) do")
                body = n[2]
            elif k == "repeat":
                i = self.unique()
                self.line(f"for {i} = 1, R.count({self.expr(n[1])}) do")
                body = n[2]
            elif k == "with":
                i = self.unique()
                self.line(f"for _, {i} in ipairs(R:select({self.expr(n[1])}, E)) do")
                body = n[2]
            else:
                self.line("repeat")
                body = n[1]
            self.indent += 1
            self.line("R:guard()")
            if k == "with":
                self.line(f"local E = R:withScope({i}, E)")
            self.loopbody(body, n[3] if k == "for" else None)
            self.indent -= 1
            self.line(f"until R.truth({self.expr(n[2])})" if k == "until" else "end")
        elif k == "switch":
            value, case = self.unique(), self.unique()
            self.line("repeat")
            self.indent += 1
            self.line(f"local {value} = {self.expr(n[1])}")
            default = next((i for i, (v, _) in enumerate(n[2], 1) if v is None), len(n[2]) + 1)
            self.line(f"local {case} = {default}")
            first = True
            for i, (v, _) in enumerate(n[2], 1):
                if v is not None:
                    self.line(f"{'if' if first else 'elseif'} {value} == {self.expr(v)} then {case} = {i}")
                    first = False
            if not first:
                self.line("end")
            self.loops.append(("switch", None))
            for i, (_, body) in enumerate(n[2], 1):
                self.line(f"if {case} <= {i} then")
                self.indent += 1
                self.stmt(body)
                self.indent -= 1
                self.line("end")
            self.loops.pop()
            self.indent -= 1
            self.line("until true")
        elif k == "break":
            if not self.loops:
                raise CompileError("break outside loop/switch")
            kind, name = self.loops[-1]
            if kind == "dispatch":
                self.line("do return R.SWITCH_BREAK end")
            else:
                self.line(f"do {name} = true; break end" if kind == "loop" else "do break end")
        elif k == "continue":
            if not self.loops or self.loops[-1][0] != "loop":
                raise CompileError("continue across a switch is not supported")
            self.line("do break end")
        elif k == "exit":
            self.line("do return 0 end")
        elif k == "return":
            self.line(f"do return {self.expr(n[1])} end")
        elif k in ("var", "globalvar"):
            for name, value in n[1]:
                self.line(f"R:declare(E, {quote(name)}, {self.expr(value)}, {str(k == 'globalvar').lower()})")
        else:
            raise CompileError(f"unsupported statement: {n}")

    def function(self, ast, source="GML"):
        self.stmt(ast)
        # Fall-through/exit have numeric zero return, as the original project's
        # option_variableerrors=false and keyboard_multicheck scripts require.
        self.line("return 0")
        return f"-- Generated from {source}; edit the GMX/GML source or compiler.\nreturn function(R, E)\n" + "\n".join(self.lines) + "\nend\n"


def compile_gml(text: str, source="GML") -> tuple[str, tuple]:
    ast = Parser(text).program()
    compiled = Emitter().function(ast, source)
    statements = [s for s in ast[1] if s[0] != "empty"]
    if len(compiled) > 200000 and len(statements) == 1 and statements[0][0] == "switch":
        # LuaJIT has a signed 16-bit jump limit. SCR_TEXT's large dispatch
        # exceeds it even though every case is individually small. Partition
        # whole cases (not arbitrary lines), preserving fall-through/return.
        switch = statements[0]
        out = [f"-- Generated, partitioned switch from {source}.", "local handlers, labels = {}, {}"]
        default = "nil"
        for i, (label, body) in enumerate(switch[2], 1):
            if label is None:
                default = str(i)
            elif label[0] not in ("number", "string"):
                raise CompileError("large switch labels must be constants")
            else:
                out.append(f"labels[{Emitter().expr(label)}] = {i}")
            emitter = Emitter()
            emitter.loops.append(("dispatch", None))
            emitter.stmt(body)
            out.append(f"handlers[{i}] = function(R, E)\n" + "\n".join(emitter.lines) + "\nend")
        out.append("return function(R, E)\n    return R:dispatchSwitch(E, " + Emitter().expr(switch[1]) + f", labels, handlers, {default})\nend\n")
        compiled = "\n".join(out)
    return compiled, ast
