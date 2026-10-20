# Remaining work prompts

- Reproduce the historical pytest hang with a <=90 s cap; identify and fix a culprit only if a test hangs or fails, then prove all files pass and the full suite finishes under 60 s.
- Audit role/auth and fabricated dashboard fallbacks; require typed snooze/false-positive reasons, token-derived authors, role-specific UI, calibration-floor wording, and one passing test per role.
- Verify ml/robustness.py and regenerate metrics, evaluation report, model card, and figure; prove fold-mean vs pooled sparse-BP statistics and the CI/wins/t-test conclusion rule agree.
- Fix Risk Horizon history to use dated stored estimates or remove the past line; show one prediction per patient-day, no future dates, and measured events.
- Rewrite What-If effects from ml/whatif_effects.py; remove unchanged keys, hold unsupported HRV/sleep-efficiency values, and verify factual wording.
- Fix simulator tick cadence/seeding/row counts and WebSocket single-use tickets; verify final-day labels are unlabelled and preparation skips them.
- Finish dashboard workflow/accessibility requirements C1-C8 using real API data; capture real screenshots and test console only if Playwright is available.
- Finish README/API/env/tree generators, Docker/CI/safety/demo/presentation artifacts, and clean-clone smoke test; add genetic markers only if the budget gate is reopened, otherwise keep them out of scope.
