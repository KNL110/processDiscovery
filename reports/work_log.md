# Work Log

## Day 1

- Created the project scaffold
- add session loading, event loading and intigirty check
- found negetive ms_since last second
- found negative ms_since_last_event is strongly associated with screenshot_smart, but it is not exclusively a screenshot phenomenon because a few mouse_scroll events also have negative values

## Day 2

- understand the data more thoroughly
- brainstorm on the ideas to implement segmentation of units of work
- simplified integrity check: dropped per-event issue tracking in favor of a single set of issue types, added validation for required fields, duplicate event_id, and duplicate sequence_number
- integrity check now also collects raw values for timestamp_ms backward jumps and negative ms_since_last_event so they can be pooled across sessions and summarized (min/q1/median/q3/max)
