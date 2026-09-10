"""Tests that print() statements inside agent-defined functions are captured in STDOUT.

These tests verify that when an agent defines a function and calls it, any print()
calls within that function appear in the result output returned by instance.eval().
"""

import pytest

PRINT_CAPTURE_CASES = [
    pytest.param(
        'def foo():\n    print("hello from foo")\n\nfoo()',
        ["hello from foo"],
        id="simple-function",
    ),
    pytest.param(
        'def count():\n    for i in range(3):\n        print(f"item {i}")\n\ncount()',
        ["item 0", "item 1", "item 2"],
        id="loop",
    ),
    pytest.param(
        'def check():\n    x = 5\n    if x > 3:\n        print("big")\n    else:\n        print("small")\n\ncheck()',
        ["big"],
        id="conditional",
    ),
    pytest.param(
        'def steps():\n    print("step 1")\n    print("step 2")\n    print("step 3")\n\nsteps()',
        ["step 1", "step 2", "step 3"],
        id="multiple-prints",
    ),
    pytest.param(
        "def outer():\n"
        "    def inner():\n"
        '        print("from inner")\n'
        "    inner()\n"
        '    print("from outer")\n'
        "\n"
        "outer()",
        ["from inner", "from outer"],
        id="inner-function",
    ),
    pytest.param(
        "def my_task():\n"
        "    def log(msg):\n"
        "        print(str(msg))\n"
        '    log("starting task")\n'
        '    log("task complete")\n'
        "\n"
        "my_task()",
        ["starting task", "task complete"],
        id="helper-wrapper",
    ),
    pytest.param(
        "def safe_op():\n"
        "    try:\n"
        '        print("in try")\n'
        "    except Exception as e:\n"
        '        print(f"error: {e}")\n'
        "\n"
        "safe_op()",
        ["in try"],
        id="try-block",
    ),
    pytest.param(
        "def safe_op():\n"
        "    try:\n"
        "        x = 1 / 0\n"
        "    except Exception as e:\n"
        '        print(f"caught: {e}")\n'
        "\n"
        "safe_op()",
        ["caught:"],
        id="except-block",
    ),
    pytest.param(
        "def do_work():\n"
        "    def log(msg):\n"
        "        print(str(msg))\n"
        "\n"
        "    def safe(fn, *args, name=None, default=None, **kwargs):\n"
        "        try:\n"
        "            return fn(*args, **kwargs)\n"
        "        except Exception as e:\n"
        '            log(f"ERROR {name}: {e}")\n'
        "            return default\n"
        "\n"
        '    log("=== START ===")\n'
        '    inv = safe(inspect_inventory, name="inspect_inventory", default={})\n'
        '    log(f"Inventory: {inv}")\n'
        '    log("=== DONE ===")\n'
        "\n"
        "do_work()",
        ["=== START ===", "Inventory:", "=== DONE ==="],
        id="safe-pattern",
    ),
    pytest.param(
        "def do_work():\n"
        "    def log(msg):\n"
        "        print(str(msg))\n"
        "\n"
        "    def safe(fn, *args, name=None, default=None, **kwargs):\n"
        "        try:\n"
        "            return fn(*args, **kwargs)\n"
        "        except Exception as e:\n"
        '            log(f"ERROR calling {name}: {e}")\n'
        "            return default\n"
        "\n"
        '    log("start")\n'
        '    result = safe(lambda: 1/0, name="divide", default=None)\n'
        '    log(f"result={result}")\n'
        "\n"
        "do_work()",
        ["start", "ERROR calling divide", "result=None"],
        id="safe-pattern-with-error",
    ),
    pytest.param(
        'def greet(name):\n    print(f"hello {name}")\n\ngreet("alice")\ngreet("bob")',
        ["hello alice", "hello bob"],
        id="called-twice",
    ),
]


@pytest.mark.parametrize("code,expected", PRINT_CAPTURE_CASES)
def test_print_in_function_captured(instance, code, expected):
    """Prints inside agent-defined functions appear in the eval() result."""
    _, _, result = instance.eval(code)
    for substring in expected:
        assert substring in result


def test_persistent_function_across_evals(instance):
    """Function defined in one eval, called in the next, should still capture prints."""
    instance.eval('def say(x):\n    print(f"saying: {x}")')
    _, _, result = instance.eval('say("works")')
    assert "saying: works" in result
