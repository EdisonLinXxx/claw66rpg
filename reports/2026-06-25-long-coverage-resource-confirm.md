# Long Coverage Resource Confirmation

- Date: 2026-06-25
- Goal: extend the first-game autoplay collection beyond the 5-minute three-policy baseline and identify whether longer play reaches new blockers before a full completion pass.

## Initial Long Run

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\collect-story-coverage.ps1 -DurationSeconds 1800 -MaxSteps 900 -TimeoutSeconds 2400 -Out C:\tmp\claw_story_coverage_long_30m -Policies "round-robin,first,last"
```

Observed result:

- The first policy, `round-robin`, reached deeper management paths.
- It exposed missing local mapped resources and stopped making useful progress around `57:1355:1010`.
- Newly mirrored MD5s:
  - `b45a257f034cf39cda28fce740277358`
  - `f386d14ed0640d8d8460582b0fb4325a`
  - `f9d0f589c4a6d8272b4a3c47cdf8f5db`

## Rerun And Additional Resource Discovery

Rerun output:

- `C:\tmp\claw_story_coverage_long_30m_rerun`

Additional missing MD5:

- `3e478efeaeac3640aa727c966e2c1ab5`

Follow-up 720-second confirmation output:

- `C:\tmp\claw_autoplay_confirm_after_long_mirrors`

Additional missing MD5s:

- `42a71e1e70038f47d646c1d13fd2a74f`
- `5bd85705bf1165c1ad16e06c26bdd10d`

## Final Confirmation

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\autoplay-story.ps1 -DurationSeconds 720 -MaxSteps 340 -Out C:\tmp\claw_autoplay_confirm_after_more_mirrors -Port 8935 -ChoicePolicy round-robin
```

Result:

| Check | Result |
| --- | --- |
| status | `duration_reached` |
| trace count | `310` |
| unique story states | `177` |
| local 404 count | `0` |
| missing MD5 count | `0` |
| last state | `54:287:100` |
| duration | `721.6s` |

Current conclusion: longer play is now reaching deeper management and map paths than the earlier 5-minute merged report. The run exposed six additional mapped static resources; after mirroring them, a 720-second `round-robin` confirmation reached `177` unique states with no local 404 and no missing MD5s. A full 30-minute-per-policy three-policy collection should be rerun next now that this resource wave is fixed.
