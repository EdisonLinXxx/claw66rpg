# 2026-07-02 Visual Regression Notes

## Screenshot Artifacts

- Debug visual sheet: `C:\tmp\claw_visual_regression_round_20260702\comparison_sheet.png`
- Debug screenshots: `C:\tmp\claw_visual_regression_round_20260702`
- Main button 0 full-route screenshot: `C:\tmp\claw_main_button0_after_code214_index_20260702\main_button_00_kitchen.png`
- Main buttons 5 and 7 full-route screenshots: `C:\tmp\claw_main_buttons_5_7_after_code214_finish_20260702`
- Main buttons 8 to 10 full-route screenshots: `C:\tmp\claw_main_buttons_8_10_after_code214_finish_20260702`
- Save/load verification screenshots: `C:\tmp\claw_save_load_after_code214_finish_20260702`

## Verification Summary

- Save/load: passed. `save_load_summary.json` reports `status: ok`, `restoredMatchesSaved: true`, and `restoreMatch.ok: true`.
- Initial full route: advanced past the newbie chest choice and initial continue buttons to story `44`.
- Main button 0 / kitchen: passed, no local 404.
- Main button 5 / room: route passed, but one local resource is missing: `f1c5bc6ca25540e0dc9dc8fb94ef9a0d`.
- Main button 7 / sell: click did not leave the main inn screen; current status remains `unchanged`.
- Main button 8: full-route validation still blocks on random-event Code214 state sync while the canvas is already showing the cooking/customer UI.
- Main button 9 / appearance: click did not leave the main inn screen; current status remains `unchanged`.
- Main button 10 / outing: passed, no local 404.

## Current Difference List

- `debugJumpMain` screenshots are not reliable for final visual comparison because they can preserve stale canvas state, including wrong background or portrait overlays. Use debug screenshots only for button mechanics.
- Main inn secondary routes are partially working through the full route, but several entrances still need targeted fixes before final visual acceptance: `sell`, `appearance`, and button 8.
- `room` needs asset mirroring for missing md5 `f1c5bc6ca25540e0dc9dc8fb94ef9a0d`.
- Button 8 needs state synchronization around story `118` Code214 random events; the canvas can show the UI while `runner-story-state` still reports Code214.
- Save/load is functionally restored in the validation harness, but the user-facing save page should still be manually checked after the secondary-page fixes.

## Code Changes In This Round

- Added default auto handling for the newbie chest choice and the following single-button continue screens.
- Extended Code214 name-form stubbing to lower index `473`; `479` is handled separately as random order UI in the validation harness.
- Added a collect-state fallback that calls `eventFinish()` after stubbing Code214 name forms.

## Follow-up Fixes

- Mirrored missing room background resource `f1c5bc6ca25540e0dc9dc8fb94ef9a0d` (`graphics/background/客栈/客房/1.1.jpg`).
- Narrowed Code214 name-form stubbing so `479` no longer closes real custom UI pages such as sell/order panels.
- Added a pre-main-only close for `story15` Code214 index `126`; once the inn main screen is seen, secondary custom UIs are left open.
- Updated the main-button validation harness to skip story `118` random order UI by clicking the decline/next-time option instead of treating it as a name form.

Follow-up validation artifacts:

- `C:\tmp\claw_main_2_5_7_9_after_random_skip_20260702`
- `C:\tmp\claw_main_button8_after_random_skip_20260702`
- `C:\tmp\claw_save_load_after_random_skip_20260702`

Follow-up validation result:

- Main buttons `2`, `5`, `7`, `8`, and `9`: `status=ok`, `local404Count=0`, `missingMd5s=[]`.
- Save/load: `status=ok`.
