# move_to

`move_to(position, stop_distance=0)` walks to the requested position and returns
the actual final Position. The default goal remains exact (within the engine's
small arrival tolerance). Occupied destinations are not silently replaced.

```python
coal_pos = nearest(Resource.Coal)
move_to(coal_pos)  # Open resource ground is walkable.
move_to(furnace.position, stop_distance=3)  # Explicit approach radius.
```

Interaction actions auto-approach within their own reach, so separate movement
is normally unnecessary before harvesting, inserting, or building. Avoid walking
onto a planned building footprint before placing it.

Failed path searches report the requested goal, radius, and bounded collision
context at the start and goal. Water tiles and overlapping entities are local
evidence; the path may also be obstructed farther away. Failures do not move the
character or return unverified reachable alternatives. Choose another destination
or an explicit `stop_distance` after inspecting the failure.
