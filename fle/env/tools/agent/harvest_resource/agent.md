# harvest_resource

Harvest ores or wood through native character mining.

```python
harvest_resource(position: Position, quantity: int = 1, radius: int = 10) -> int
```

The action walks into mining range of the requested position. A separate
`move_to` call is optional. Mining and walking consume simulation time.

```python
harvested = harvest_resource(nearest(Resource.Coal), 10)
harvested = harvest_resource(nearest(Resource.Stone), 5)
harvested = harvest_resource(nearest(Resource.Wood), 5)
```

Use a positive integer quantity. The result is the actual inventory gain, which
can exceed the request when a tree yields several wood. If a tree is exhausted,
the action approaches another tree to finish the request. Ore remains selected
until the requested quantity has been mined.

Supported resource names include `Resource.Coal`, `Resource.IronOre`,
`Resource.CopperOre`, `Resource.Stone`, `Resource.UraniumOre`, and `Resource.Wood`.
The supplied position must identify the resource; `radius` does not extend the
character's mining reach.

A stalled action stops mining and reports its actual progress after 30 simulated
seconds without an inventory increase. Inspect the target, reach, and available
inventory space before retrying. Items gained before an error remain in inventory.
