# get_production_statistics

Read public native production and consumption totals and rates, like the player's
production statistics window. This includes manual production and does not expose
benchmark scoring or hidden verifier measurements.

`get_production_statistics(items=None, window_seconds=60, category='item', limit=32)`

Select up to 64 item names/Prototypes, or omit items for the most active products
ranked by lifetime production plus consumption. `category` is `item` or `fluid`;
native windows are 5, 60, 600, or 3600 seconds. Output is bounded by `limit` (1–64)
and includes truncation metadata, absolute engine tick, and force/surface scope.
Rates are per minute; totals are since the engine statistics were initialized.

```python
print(get_production_statistics([Prototype.IronPlate], window_seconds=60))
print(get_production_statistics(category='fluid', window_seconds=600))
```
