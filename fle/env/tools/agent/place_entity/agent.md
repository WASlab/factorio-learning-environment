# place_entity

`place_entity(Prototype.X, direction=Direction.UP, position=Position(x,y), exact=True)`
places one inventory entity at the requested position and direction, after
approaching within build reach. It returns the placed Entity.

The canonical action profile requires exact placement, including offshore pumps.
An engine manual-build rejection returns structured diagnostics: requested
position, rotated footprint, overlapping entities with positions, colliding tiles,
and truncation metadata. These describe local collision evidence; engine-specific
rules may also reject placement. The failure does not create ghosts, relocate the
build, or consume its inventory item. Inspect terrain and choose the next build.

```python
furnace = place_entity(Prototype.StoneFurnace, position=Position(x=10,y=4))
pump = place_entity(Prototype.OffshorePump, direction=Direction.UP,
                    position=Position(x=20.5,y=10.5))
```

Generic `exact=False` searches belong only to the explicit planner-assisted
ablation profile. They are unavailable in the canonical benchmark.
