# get_tile_map

Render a compact tile/entity map around any point. This is the "step back and
look at the target" primitive: use it before placing a build and immediately
after a placement or belt path stops short.

## Usage

```python
tile_map = get_tile_map(Position(x=29, y=-82), radius=12)
for row in tile_map['rows']:
    print(row)
for entity in tile_map['entities']:
    print(entity['name'], entity['position'], entity.get('direction'))
```

Rows are top (north) to bottom, left (west) to right; each character is one
tile. Belts draw their flow direction (`^>v<`), `P` is an electric pole, `*`
an ore tile, `~` water, `#` blocked terrain, and machines use their initial
(`A` assembler, `F` furnace, `D` drill, `L` lab, `B` boiler, `G` engine,
`p` pump, `C` chest, `I`/`i` inserter, `|` pipe).

## Practical guidance

- When a `place_path`/`place_entity` call reports a blocker, render the map
  around `blocker.position` to see the whole obstruction in context.
- `entities` carries exact positions, directions and statuses for anything the
  glyphs compress; prefer it when alignment matters.
- The structured list is capped at 128 entities and `entities_truncated` marks
  the cap; shrink `radius` if you need certainty.
