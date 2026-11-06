# Design: each part answers an incident

| part | rule | the incident it comes from |
|---|---|---|
| Truth bound to an artefact digest | a label applies to one content digest only | reviewers' verdicts were joined to polygons by case id; 28 of 127 labels turned out to be about an earlier version of the polygon (2026-11-03) |
| Ranked sources, losers kept | client > person > check > batch > import; a later lower-rank value never overwrites | a pipeline rerun silently replaced a person's decision in a CSV; a mapping imported from a sheet overwrote a verified path |
| Benchmark frozen and versioned | read-only once frozen; a changed set is a new version; manifest digest checked on load | a case list edited in place made two gate runs incomparable |
| Dev / holdout split | the daily gate replays dev only; holdout is touched at release | the same 100 cases served as daily gate and final check for three weeks: every fix was tuned on them |
| Staleness check | a case whose artefact digest changed is reported before any gate result | a benchmark kept passing while the inputs it froze no longer matched the pipeline's outputs |
| Missed errors as the primary rule | wrong outputs accepted without a person may not rise; accuracy is not a rule | a release with higher overall agreement let two more client-failed cases through |
| Frozen actions | every case keeps its action unless the change is declared to move cases | lane flips between two runs of the same flow were all on right cases, but nobody could tell drift from change |
| Paired test, not two accuracies | McNemar on the same cases | 3/40 vs 7/40 was argued over for a day; on paired cases it was 4 discordant |
| Wilson intervals on every rate | | "88% correct" on 25 pages was quoted without its 69–96 interval |
| One JSON line per run | append-only log; the controller reads counts, not prose | gate results lived in a chat transcript |
