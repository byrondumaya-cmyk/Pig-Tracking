# Post-Implementation Verification & Integration Testing

## Goal
Perform a comprehensive verification pass on the newly refactored Pig Tracking System to ensure real-world integration between dashboard, alert logic, GSM, snapshots, and networking.

## Tasks
- [ ] **Task 1: GSM Diagnostic Module** → Verify: Add `/api/dev/gsm_test` protected by Developer Mode. Click "Test SMS" in UI, confirm it triggers GSM without writing a fake health alert to history.
- [ ] **Task 2: Dashboard/Auth Validation** → Verify: Run system, hit dashboard with unauthenticated browser (deployment mode). Confirm mutating settings are blocked (401). Log in and confirm changes are allowed.
- [ ] **Task 3: Event & Snapshot Persistence** → Verify: Inject mock "alert" into main loop. Confirm `data/snapshots/alert_*.jpg` is saved and `pen_alerts` DB table contains the image path and correct timestamp.
- [ ] **Task 4: State Machine & Tracking** → Verify: Inject persistent lethargy data. Confirm alert triggers, cooldown engages (no SMS spam), and ID drops/re-acquisitions don't falsely claim permanent identity.
- [ ] **Task 5: Network Subsystem Audit** → Verify: Ensure AP/LAN scripts dynamically pull IPs and avoid hardcoding, ensuring the Pi won't strand itself on reboot.

## Done When
- [ ] All demonstrated issues are fixed and recorded.
- [ ] `FINAL_REPORT.md` is updated with strict TESTED, SIMULATED, or BLOCKED status for all components.

## Notes
- Do not blindly assume implementation equals validation.
- Fix only demonstrated bugs.
- Do not rewrite components just for cleaner architecture.
