# launch_rocket

```python
launch_rocket(silo: Position | RocketSilo) -> RocketSilo
```

Request a launch from the player-owned silo at the supplied position. The silo
must have a rocket ready, and Factorio must accept the request. The tool raises
an error for absent, unready, or rejected launches and returns the refreshed
silo after an accepted request.

Use `get_prototype_recipe` to inspect the installed game's rocket-part recipe;
component requirements vary by Factorio version. Supply power and ingredients,
then inspect the silo as construction progresses:

```python
silo = get_entity(Prototype.RocketSilo, silo.position)
silo = launch_rocket(silo)
```

An accepted request starts the launch sequence. It does not itself count as a
completed rocket launch; benchmark verification uses the engine's launch count.
