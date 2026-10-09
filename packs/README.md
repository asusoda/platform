# Packs

A pack is content for one campus or topic that any org can use: public pages crawled into knowledge, live queries that agents run, alert feeds, and the school's Canvas URL. A pack holds content and settings, not new behavior. It adds no tables, routes or dashboard pages. Use a [module](../docs/writing-a-module.md) for a feature.

| Pack | Content |
| --- | --- |
| [asu](asu/README.md) | Arizona State University: library hours, events, courses, dining, scholarships, news, shuttles, jobs, sports; the ASU Canvas URL |
| [careers](careers/__init__.py) | Alert feeds for software internships, new grad roles and hackathons |

## Write a pack

1. Make a folder `packs/<name>/`. The name is lowercase letters, digits and underscores. The pack owns the org's knowledge sources with keys that start with `<name>/`.
2. In `packs/<name>/__init__.py`, set `PACK`:

   ```python
   from modules.packs.types import Pack, QueryParam, QuerySource, Source

   PACK = Pack(
       name="example",
       title="Example University",
       description="Public pages of Example University: library hours and events.",
       sources=(
           Source(key="library_hours", url="https://lib.example.edu/hours", category="library", fetch_every_hours=24),
       ),
       queries=(
           QuerySource(
               key="events",
               description="Campus events that match keywords.",
               params=(QueryParam("keywords", "Words to search for."),),
               to_url=lambda p: "https://events.example.edu/search?q=" + p.get("keywords", ""),
           ),
       ),
   )
   ```

3. Optional parts of a `Pack`:
   - `feeds`: alert feeds that officers pick under **New feed** > **Start from** on the Alerts page. Each `Feed` has a key (lowercase letters, digits and dashes), a title, a description, and the `kind` and `config` that the [alerts module](../docs/modules/alerts.md) takes.
   - `canvas_url`: the school's Canvas, like `https://canvas.example.edu`. Member sign-in to Canvas uses it when `ACCOUNTS_CANVAS_URL` is not set and only one pack sets it.
4. Optional: give a `Source` or `QuerySource` an `extractor` that turns the fetched page into one line for each record. Helpers are in `modules/packs/text.py`. A query that calls an API sets `answer` instead of `to_url`. Add `modules.packs.web.QUERY` to `queries` for web search.
5. Add a `README.md` that lists the pages and the queries, and add the pack to the table above.
6. Add tests in `tests/contract/` with saved pages in a fixtures folder. Do not fetch live pages in tests.

Rules:

- Public pages only. Do not add pages that need a sign-in.
- A pack imports only `modules.packs` and the standard library. It does not import Flask.
- Do not change a source key after orgs use it. A new key makes a new source, and the old one is turned off on the next sync.

Platform loads every folder in `packs/` on start. Officers add a pack's pages on the Knowledge page and its feeds on the Alerts page of the dashboard.
