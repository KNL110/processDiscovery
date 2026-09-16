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

## Day 3

- added feature-extraction helpers to `utils.py` (BrowserTab, AppOrProcessName, ExtractedText, ActionTaken, EventSignature, AppContext) for use in segmentation

## Day 4

- deep dive on the segmentation approach: micro-unit aggregation from L2/L3 events (collapse keystroke/click runs into one action), an OS-thread-style model for deinterleaving concurrent work, and an isContinuation-style compatibility check (case-ID match > element-anchor match > graded app/time/text score)
- built `analysis/groundTruth.py` (using copilot) to ground hyperparameters in real data: execution duration distribution, resume gaps, noise_block types/durations, split task counts
- built `analysis/apps.py`(using copilot): inventories every distinct app across all sessions in both datasets (22 in A, 12 in B, 9 shared) -- useful for auditing which apps should count as noise

