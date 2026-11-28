# feeds.hackathons

Upcoming hackathons from Hack Club, Euro-Hackathons and Hackalist. It is shared: one preset for every org.

## Files

| File | Holds |
| --- | --- |
| `__init__.py` | `SUBMODULE` (`shared=True`) and `FEEDS`: the `hackathons` preset |

## Surface

- Switch: `feeds.hackathons`. Feeds of kind `hackathons` run only while it is on, and its preset shows on the Hackathons page. Turning it on writes the org's `submodule_subscriptions` row.
- Migration `c5e7a9b1d3f4` turned it on for each org that subscribed to `careers` or had a `hackathons` feed.

The kind's code is `modules/feeds/hackathons.py`.
