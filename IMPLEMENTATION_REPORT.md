# Audit Remediation Implementation Report

## Pre-Remediation Checkpoint
- **Commit:** `6466c8a3455779833bd8e0bf926e5ba670035710`
- **Backup Branch:** `backup/pre-audit-fixes-2026-09-20`
- **Backup Tag:** `pre-audit-fixes-2026-09-20`

*This checkpoint represents the safe fallback state of the application before any audit remediation code was modified.*

## Audit Fixes Executed

- **ID-1:** Decoupled thermal I2C reading into a daemon thread in `src/main.py`. The camera relay and inference loops now read lazily from `ThermalBuffer`.
- **ID-2:** Offloaded JPEG encoding off the asyncio event loop using `run_in_executor` in `src/api/websocket_server.py`.
- **ID-3:** Implemented a bounded `queue.Queue(maxsize=1)` and a background worker thread for SMS dispatch in `src/hardware/gsm_notifier.py`.
- **ID-4:** Refactored `/api/settings` to a validate-first atomic mutation pattern in `src/dashboard/routes.py`.
- **ID-5:** Sanitized `timedatectl` input by parsing as ISO 8601 `datetime` objects before shell execution.
- **ID-6:** Documented that config staleness (inference threshold) requires restart instead of building risky live-reload logic mid-inference.

## Commit
All changes are cleanly committed in branch `audit-remediation`.