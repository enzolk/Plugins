# cqf_safe.py
# "Safe" evaluator/executor for Custom Quick Favorites
#
# Goals:
# - safe_eval(expr): allow ONLY simple Blender context/data-path expressions used by this addon
#   (attributes on bpy / bpy.context, conditional if-expr, boolean ops, comparisons),
#   plus a tiny whitelist of safe builtins (hasattr/getattr).
# - safe_exec(code): allow ONLY a bpy.ops.* call (as a single expression statement).
#
# This prevents arbitrary Python execution while keeping the addon functional.

import ast
import bpy


# -----------------------------------------------------------------------------
# Shared helpers
# -----------------------------------------------------------------------------

_ALLOWED_ROOT_NAMES = {"bpy", "C", "context"}

# Only these "builtins" are exposed (and only by name).
_ALLOWED_FUNCS = {"hasattr", "getattr"}

# For safety: forbid any attribute with dunder or private-ish patterns.
def _is_forbidden_attr(name: str) -> bool:
    if not name:
        return True
    if name.startswith("__") or name.endswith("__"):
        return True
    # also block common escape hatches
    if name in {"__class__", "__dict__", "__mro__", "__subclasses__", "__globals__", "__getattribute__"}:
        return True
    return False


def _safe_globals():
    # Provide only basic constants; no real builtins.
    return {"__builtins__": {}, "True": True, "False": False, "None": None}


def _safe_locals():
    # Expose bpy and context aliases + safe functions
    return {
        "bpy": bpy,
        "C": bpy.context,
        "context": bpy.context,
        "hasattr": hasattr,
        "getattr": getattr,
    }


# -----------------------------------------------------------------------------
# AST validation
# -----------------------------------------------------------------------------

class _SafeEvalValidator(ast.NodeVisitor):
    """
    Whitelist-based validator for expressions used as 'owner_expr' etc.
    Allowed:
      - Names: bpy / C / context
      - Attribute chains: bpy.context.scene.tool_settings ...
      - Constants: str/int/float/bool/None
      - Bool ops: and/or
      - Unary: not, +, -
      - Compare: == != < <= > >=, is/is not, in/not in (rare, but safe)
      - IfExp: a if cond else b  (used in your candidates)
      - Calls: hasattr(obj, "prop"), getattr(obj, "prop", default)
    Disallowed:
      - Any statement nodes
      - Subscripting: x[0]
      - Comprehensions, lambdas, f-strings, joins, etc.
      - Access to dunder/private attributes
    """

    _ALLOWED_COMPARE_OPS = (
        ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
        ast.Is, ast.IsNot, ast.In, ast.NotIn,
    )

    _ALLOWED_BOOL_OPS = (ast.And, ast.Or)
    _ALLOWED_UNARY_OPS = (ast.Not, ast.UAdd, ast.USub)

    def generic_visit(self, node):
        raise ValueError(f"Unsafe expression node: {type(node).__name__}")

    def visit_Expression(self, node: ast.Expression):
        self.visit(node.body)

    def visit_Name(self, node: ast.Name):
        if node.id not in _ALLOWED_ROOT_NAMES and node.id not in _ALLOWED_FUNCS and node.id not in {"True", "False", "None"}:
            raise ValueError(f"Unsafe name: {node.id}")

    def visit_Constant(self, node: ast.Constant):
        # constants are ok
        return

    def visit_Attribute(self, node: ast.Attribute):
        if _is_forbidden_attr(node.attr):
            raise ValueError(f"Forbidden attribute: {node.attr}")
        self.visit(node.value)

    def visit_BoolOp(self, node: ast.BoolOp):
        if not isinstance(node.op, self._ALLOWED_BOOL_OPS):
            raise ValueError("Unsafe boolean operator")
        for v in node.values:
            self.visit(v)

    def visit_UnaryOp(self, node: ast.UnaryOp):
        if not isinstance(node.op, self._ALLOWED_UNARY_OPS):
            raise ValueError("Unsafe unary operator")
        self.visit(node.operand)

    def visit_Compare(self, node: ast.Compare):
        self.visit(node.left)
        for op in node.ops:
            if not isinstance(op, self._ALLOWED_COMPARE_OPS):
                raise ValueError("Unsafe comparison operator")
        for c in node.comparators:
            self.visit(c)

    def visit_IfExp(self, node: ast.IfExp):
        self.visit(node.test)
        self.visit(node.body)
        self.visit(node.orelse)

    def visit_Call(self, node: ast.Call):
        # Only allow hasattr/getattr by bare name
        if not isinstance(node.func, ast.Name) or node.func.id not in _ALLOWED_FUNCS:
            raise ValueError("Only hasattr/getattr calls are allowed in safe_eval")

        # Validate args/keywords
        for a in node.args:
            self.visit(a)
        for kw in node.keywords:
            # block **kwargs
            if kw.arg is None:
                raise ValueError("**kwargs not allowed")
            self.visit(kw.value)

    # Explicitly allow these node types to be rejected by generic_visit:
    # (We keep them here just for clarity; generic_visit already blocks others.)
    def visit_Subscript(self, node: ast.Subscript):
        raise ValueError("Subscript is not allowed (no x[0])")

    def visit_Lambda(self, node: ast.Lambda):
        raise ValueError("Lambda is not allowed")

    def visit_ListComp(self, node: ast.ListComp):
        raise ValueError("Comprehensions are not allowed")

    def visit_DictComp(self, node: ast.DictComp):
        raise ValueError("Comprehensions are not allowed")

    def visit_GeneratorExp(self, node: ast.GeneratorExp):
        raise ValueError("Comprehensions are not allowed")

    def visit_JoinedStr(self, node: ast.JoinedStr):
        raise ValueError("f-strings are not allowed")


class _SafeExecValidator(ast.NodeVisitor):
    """
    Whitelist validator for code executed as op_expr.
    Allowed:
      - exactly one statement: an expression statement
      - which must be a call to bpy.ops.<module>.<op>(...) (any args/keywords allowed if safe literals)
    Disallowed:
      - multiple statements
      - assignments, imports, attribute mutations, etc.
    """

    def generic_visit(self, node):
        raise ValueError(f"Unsafe code node: {type(node).__name__}")

    def visit_Module(self, node: ast.Module):
        if len(node.body) != 1:
            raise ValueError("Only one expression statement is allowed")
        self.visit(node.body[0])

    def visit_Expr(self, node: ast.Expr):
        self.visit(node.value)

    def visit_Call(self, node: ast.Call):
        # Must be bpy.ops.xxx.yyy(...)
        if not self._is_bpy_ops_call(node.func):
            raise ValueError("Only bpy.ops.* operator calls are allowed in safe_exec")

        # Validate args/kwargs as safe literals/containers
        for a in node.args:
            self._visit_value(a)
        for kw in node.keywords:
            if kw.arg is None:
                raise ValueError("**kwargs not allowed")
            self._visit_value(kw.value)

    def _is_bpy_ops_call(self, fn) -> bool:
        # Expect Attribute(Attribute(Attribute(Name('bpy'), 'ops'), mod), op)
        # but Blender ops can be nested only 2 levels: bpy.ops.mod.op
        try:
            if not isinstance(fn, ast.Attribute):
                return False
            if _is_forbidden_attr(fn.attr):
                return False

            mod = fn.value
            if not isinstance(mod, ast.Attribute):
                return False
            if _is_forbidden_attr(mod.attr):
                return False

            ops = mod.value
            if not isinstance(ops, ast.Attribute):
                return False
            if ops.attr != "ops":
                return False

            root = ops.value
            if not isinstance(root, ast.Name) or root.id != "bpy":
                return False

            return True
        except Exception:
            return False

    def _visit_value(self, node):
        # Allowed literals and simple containers:
        # Constant (str/int/float/bool/None), List/Tuple/Dict of allowed values, Unary +/- on numbers.
        if isinstance(node, ast.Constant):
            return
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            if isinstance(node.operand, ast.Constant) and isinstance(node.operand.value, (int, float)):
                return
            raise ValueError("Unsafe unary value")
        if isinstance(node, (ast.Tuple, ast.List)):
            for e in node.elts:
                self._visit_value(e)
            return
        if isinstance(node, ast.Dict):
            for k in node.keys:
                if k is not None:
                    self._visit_value(k)
            for v in node.values:
                self._visit_value(v)
            return

        # Block everything else (names, attributes, calls, subscripts, etc.)
        raise ValueError(f"Unsafe value in operator call: {type(node).__name__}")


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def safe_eval(expr: str):
    """
    Safe evaluation for owner_expr-like expressions.
    """
    s = (expr or "").strip()
    if not s:
        return None

    tree = ast.parse(s, mode="eval")
    _SafeEvalValidator().visit(tree)

    return eval(compile(tree, filename="<cqf_safe_eval>", mode="eval"), _safe_globals(), _safe_locals())


def safe_exec(code: str):
    """
    Safe execution for operator expressions.
    Only allows a single bpy.ops.* call expression statement.
    """
    s = (code or "").strip()
    if not s:
        return None

    tree = ast.parse(s, mode="exec")
    _SafeExecValidator().visit(tree)

    return exec(compile(tree, filename="<cqf_safe_exec>", mode="exec"), _safe_globals(), _safe_locals())