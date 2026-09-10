import unittest

from fle.commons.cluster_ips import get_local_container_ips
from fle.env import FactorioInstance

embedded_function = """
def inspect_inventory_wrapper():
   return inspect_inventory()

print(inspect_inventory_wrapper())
"""

expected_result = "{'iron-chest': 2, 'transport-belt': 50, 'burner-inserter': 32, 'small-electric-pole': 10, 'pipe': 15, 'boiler': 1, 'steam-engine': 1, 'burner-mining-drill': 3, 'electric-mining-drill': 1, 'stone-furnace': 9, 'assembling-machine-1': 1, 'coal': 50, 'iron-plate': 50, 'copper-plate': 50}"
#
# inventory = {
#    'iron-plate': 50,
#    'coal': 50,
#    'copper-plate': 50,
#    'iron-chest': 2,
#    'burner-mining-drill': 3,
#    'electric-mining-drill': 1,
#    'assembling-machine-1': 1,
#    'stone-furnace': 9,
#    'transport-belt': 50,
#    'boiler': 1,
#    'burner-inserter': 32,
#    'pipe': 15,
#    'steam-engine': 1,
#    'small-electric-pole': 10
# }
# instance = FactorioInstance(address='localhost',
#                            bounding_box=200,
#                            tcp_port=27015,
#                            fast=True,
#                            inventory=inventory)


def test_nested_functions():
    ips, udp_ports, tcp_ports = get_local_container_ips()
    instance = FactorioInstance(
        address="localhost",
        bounding_box=200,
        tcp_port=tcp_ports[-1],
        fast=True,
        # cache_scripts=False,
        inventory={},
    )

    score, goal, result = instance.eval_with_error("print(inspect_inventory())")

    # Accept both Inventory() and Inventory({}) as valid representations
    assert result[3:] in ("(Inventory({}),)", "(Inventory(),)")

    score, goal, result = instance.eval_with_error(embedded_function)

    # Accept both Inventory() and Inventory({}) as valid representations
    assert result[3:] in ("(Inventory({}),)", "(Inventory(),)")


def test_builtin_functions():
    instance = FactorioInstance(
        address="localhost",
        bounding_box=200,
        tcp_port=27000,
        fast=True,
        # cache_scripts=False,
        inventory={},
    )

    score, goal, result = instance.eval_with_error("print(len('hello'))")

    assert result[4:-2] == "5"

    score, goal, result = instance.eval_with_error("print(len([1,2,3,4,5]))")

    assert result[4:-2] == "5"

    score, goal, result = instance.eval_with_error(
        "print(len({'a': 1, 'b': 2, 'c': 3}))"
    )

    assert result[4:-2] == "3"

    score, goal, result = instance.eval_with_error("print(len((1,2,3,4,5)))")

    assert result[4:-2] == "5"

    score, goal, result = instance.eval_with_error("print(len({1,2,3,4,5}))")

    assert result[4:-2] == "5"


def test_math():
    instance = FactorioInstance(
        address="localhost",
        bounding_box=200,
        tcp_port=27000,
        fast=True,
        # cache_scripts=False,
        inventory={},
    )

    score, goal, result = instance.eval_with_error("print(sqrt(100))", timeout=60)
    assert "10" in result


def test_loop_print():
    instance = FactorioInstance(
        address="localhost",
        bounding_box=200,
        tcp_port=27000,
        fast=True,
        # cache_scripts=False,
        inventory={},
    )

    score, goal, result = instance.eval_with_error(
        "for i in range(3):\n\tprint(i)", timeout=60
    )
    assert "2: (0,)\n2: (1,)\n2: (2,)" in result


def test_name_error():
    instance = FactorioInstance(
        address="localhost",
        bounding_box=200,
        tcp_port=27000,
        fast=True,
        # cache_scripts=False,
        inventory={},
    )

    score, goal, result = instance.eval_with_error(
        "an_existing_variable=10\nprint(none_existing_variable)", timeout=60
    )
    assert "an_existing_variable" in result


def test_sleep():
    instance = FactorioInstance(
        address="localhost",
        bounding_box=200,
        tcp_port=27000,
        fast=True,
        # cache_scripts=False,
        inventory={},
    )

    score, goal, result = instance.eval_with_error("time.sleep(10)", timeout=60)
    assert "10" in result


def test_prototype_attribute_error():
    instance = FactorioInstance(
        address="localhost",
        bounding_box=200,
        tcp_port=27000,
        fast=True,
        # cache_scripts=False,
        inventory={},
    )

    score, goal, result = instance.eval_with_error(
        "print(Prototype.AssemblingMachine)", timeout=60
    )
    assert "AssemblingMachine1" in result


if __name__ == "__main__":
    unittest.main()
