"""Static guardrails for Python programs submitted through ``factorio-envd``.

FLE's native REPL is intentionally powerful and exposes normal Python imports
and several namespace internals. That is useful for trusted research scripts,
but it is too much authority for model-generated programs received over HTTP.
This module provides a conservative action-profile guard. It is defense in
depth, not a replacement for OS/container isolation in production.
"""

from __future__ import annotations

import ast

from fle.envd.errors import EnvironmentServiceError


class ProgramPolicyViolation(EnvironmentServiceError):
    """The submitted program exceeds the public ``fle-program-v1`` profile."""


MAX_PROGRAM_BYTES = 32_768
MAX_AST_NODES = 2_000
ALLOWED_IMPORT_ROOTS = {
    "collections",
    "functools",
    "itertools",
    "math",
    "statistics",
}
FORBIDDEN_NAMES = {
    "__builtins__",
    "breakpoint",
    "classmethod",
    "compile",
    "delattr",
    "dir",
    "eval",
    "exec",
    "exit",
    "getattr",
    "globals",
    "help",
    "input",
    "instance",
    "locals",
    "memoryview",
    "nonlocal",
    "object",
    "open",
    "persistent_vars",
    "property",
    "quit",
    "setattr",
    "staticmethod",
    "super",
    "tcp_port",
    "type",
    "vars",
}
FORBIDDEN_NODE_TYPES = (
    ast.ClassDef,
    ast.Delete,
    ast.Global,
    ast.Nonlocal,
)


PLANNER_ASSISTED_ACTIONS = {"connect_entities", "nearest_buildable"}


def validate_program(code: str, *, action_profile: str = "semantic-motor-v1") -> None:
    """Reject host access, reflection, and pathological program structure."""

    if len(code.encode("utf-8")) > MAX_PROGRAM_BYTES:
        raise ProgramPolicyViolation(
            f"program exceeds the {MAX_PROGRAM_BYTES}-byte action-profile limit"
        )
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        raise ProgramPolicyViolation(f"program is not valid Python: {exc.msg}") from exc

    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        raise ProgramPolicyViolation(
            f"program exceeds the {MAX_AST_NODES}-node action-profile limit"
        )

    semantic_aliases: dict[str, str] = {}
    if action_profile == "semantic-motor-v1":
        for node in nodes:
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Name)
                and node.value.id
                in {*PLANNER_ASSISTED_ACTIONS, "place_entity", "move_to"}
            ):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        semantic_aliases[target.id] = node.value.id

    for node in nodes:
        if isinstance(node, FORBIDDEN_NODE_TYPES):
            raise ProgramPolicyViolation(
                f"{type(node).__name__} is not available in fle-program-v1"
            )
        if isinstance(node, ast.Name) and (
            node.id in FORBIDDEN_NAMES or node.id.startswith("_")
        ):
            raise ProgramPolicyViolation(
                f"name {node.id!r} is not available in fle-program-v1"
            )
        if (
            action_profile == "semantic-motor-v1"
            and isinstance(node, ast.Name)
            and node.id in PLANNER_ASSISTED_ACTIONS
        ):
            raise ProgramPolicyViolation(
                f"{node.id} is available only in planner-assisted-v1"
            )
        if isinstance(node, ast.Attribute) and node.attr.startswith("_"):
            raise ProgramPolicyViolation(
                f"private attribute {node.attr!r} is not available in fle-program-v1"
            )
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if "__" in node.value:
                raise ProgramPolicyViolation(
                    "dunder attribute names are not available in fle-program-v1"
                )
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = (
                [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            roots = {module.split(".", 1)[0] for module in modules}
            unsupported = roots - ALLOWED_IMPORT_ROOTS
            if unsupported or (isinstance(node, ast.ImportFrom) and node.level):
                names = ", ".join(sorted(unsupported or roots))
                raise ProgramPolicyViolation(
                    f"imports are restricted by fle-program-v1; rejected: {names}"
                )
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called_name = semantic_aliases.get(node.func.id, node.func.id)
            if (
                action_profile == "semantic-motor-v1"
                and called_name in PLANNER_ASSISTED_ACTIONS
            ):
                raise ProgramPolicyViolation(
                    f"{called_name} is available only in planner-assisted-v1"
                )
            if action_profile == "semantic-motor-v1" and called_name == "move_to":
                if any(
                    keyword.arg in {"laying", "leading"} for keyword in node.keywords
                ):
                    raise ProgramPolicyViolation(
                        "move_to laying/leading is planner-assisted; use place_path"
                    )
            if action_profile == "semantic-motor-v1" and called_name == "place_entity":
                first_argument = node.args[0] if node.args else None
                if (
                    isinstance(first_argument, ast.Attribute)
                    and isinstance(first_argument.value, ast.Name)
                    and first_argument.value.id == "Prototype"
                    and first_argument.attr == "OffshorePump"
                ):
                    raise ProgramPolicyViolation(
                        "use place_offshore_pump for explicit shoreline snapping"
                    )
                exact_argument = None
                if len(node.args) >= 4:
                    exact_argument = node.args[3]
                for keyword in node.keywords:
                    if keyword.arg == "exact":
                        exact_argument = keyword.value
                if (
                    isinstance(exact_argument, ast.Constant)
                    and exact_argument.value is False
                ):
                    raise ProgramPolicyViolation(
                        "non-exact placement is planner-assisted; canonical placement is exact"
                    )
            if node.func.id != "set_entity_recipe":
                continue
            recipe_argument = node.args[1] if len(node.args) > 1 else None
            if recipe_argument is None:
                for keyword in node.keywords:
                    if keyword.arg in {"recipe", "prototype"}:
                        recipe_argument = keyword.value
                        break
            if (
                isinstance(recipe_argument, ast.Attribute)
                and isinstance(recipe_argument.value, ast.Name)
                and recipe_argument.value.id == "Prototype"
            ):
                raise ProgramPolicyViolation(
                    "set_entity_recipe requires RecipeName.X; Prototype is for "
                    "entities and items"
                )
