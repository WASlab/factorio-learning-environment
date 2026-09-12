# trace_belt

Follow a transport-belt line downstream from any belt tile and report lane
contents plus the first place items cannot advance. Use it whenever a belt
"should" be carrying items but nothing arrives.

## Usage

```python
# Trace from the first tile of the line.
result = trace_belt(Position(x=29, y=-80), max_tiles=128)
for tile in result['tiles']:
    print(tile['position'], tile['direction'], tile['lanes'])
print('blocker:', result['blocker'])
```

`blocker.reason` is one of:

- `end_of_line`: the next tile has no belt (missing segment or a wrong turn).
- `blocked_by_entity`: a non-belt entity (pole, rock, chest, machine) occupies
  the next tile; `blocker.entity` names it.
- `max_tiles_reached`: the line kept going past `max_tiles`.

## Practical guidance

- Empty `lanes` everywhere plus `end_of_line` means the feed itself is empty,
  not a jam: trace back to the source (drill output) instead.
- A tile whose direction does not continue the previous tile's flow is the
  usual head-on/rotated-belt bug; replace that belt.
- Pair with `get_tile_map` to see the whole area around the blocker.
