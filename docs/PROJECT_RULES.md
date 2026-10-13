# NightWatch project rules (agent must follow)
1. All data is synthetic. Never add real patient data, credentials, or secrets. Only placeholders in .env.example.
2. Home BP cuff readings are ground truth. Wearables are context only. Never claim a watch measures BP.
3. Decision support, not diagnosis. Keep the disclaimer visible in README and dashboard. Use "associated with", never "caused by".
4. Never hard-code, fabricate, or hand-type metrics, coverage, timestamps, or explanations. Every number shown must come from stored data or a script output.
5. Never silently impute missing data. Keep NaN, report coverage, and refuse prediction below the coverage threshold.
6. No test-only flags or dependency_overrides in production code.
7. After every task, report FACTS ONLY: commands run, exact output, files changed (git diff --stat). Do not write "verified" or "Unfinished: None" without pasted evidence. List anything not run or not tested explicitly.
8. If a result is weak, report it as weak. Do not tune to look better. Do not change evaluation splits or seeds to improve numbers.
9. One milestone at a time. Do not touch files outside the milestone scope. Commit only when I ask.
10. Time zone: store UTC, display in the user's local zone (default Asia/Kolkata).