# blueprint

The blueprint library stores reusable factory fragments (captured from the
world as Factorio exchange strings) so they can be placed again by name in the
same lease, or across a training generation when the task provisions a
blueprint scope. Blueprints are macros over the normal build rules: placement
bills every entity against your inventory and obeys the same material checks
as manual construction.

## Commands

```python
# Capture force-owned entities around a center point.
blueprint('save', name='iron-pair', x=5, y=-64, radius=16)
# -> {'saved': 'iron-pair', 'name': 'iron-pair', 'entity_count': 6, ...}

# Place a saved fragment by name at a center position.
blueprint('place', 'iron-pair', 40, -60)
# -> {'placed': 6, 'requested': 6, 'source': 'library', ...}

# Inline exchange strings also work (program size limit is 32 KiB, so prefer
# library names for anything nontrivial).
blueprint('place', '0eNq...', 40, -60)

# Discover and inspect the library.
blueprint('list')          # -> {'blueprints': [{'name', 'entity_count', ...}]}
blueprint('get', 'iron-pair')  # -> {'name', 'content', 'entity_count'}
```

Method syntax (`blueprint.save(...)`, `blueprint.place(...)`) is equivalent to
the command form and records the same tool call.

## When to use it

- Rebuilding a proven fragment for a new ore patch or power plant.
- Duplicating a working production line instead of re-placing every entity.
- Moving a saved design between leases in lineage-scoped training runs.

## Practical guidance

- Capture only complete, self-contained fragments; the world around the
  capture area is not included.
- Check the returned `placed` vs `requested` counts: placement charges the
  full material bill, then refunds (and clears) any ghost that fails to
  revive, so the net debit matches what actually appeared in the world.
- Confirm the target area is clear; collision failures are refunded but the
  fragment will be incomplete.
- Query `blueprint('list')` before saving to reuse or update an existing
  name instead of growing the library.
