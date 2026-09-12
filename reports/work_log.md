# Work Log

## Day 1

- Created the project scaffold
- add session loading, event loading and intigirty check
- found negetive ms_since last second
- found negative ms_since_last_event is strongly associated with screenshot_smart, but it is not exclusively a screenshot phenomenon because a few mouse_scroll events also have negative values
- removed screenshot_smart event since not needed
- Total sessions with structural integrity issues: 63
- Total structural integrity issues: {'negative source ms_since_last_event', 'raw timestamp went backwards'}
- Normalization issues: {'raw timestamp went backwards': 5984, 'timestamp clamped': 6361, 'negative source ms_since_last_event': 8}
