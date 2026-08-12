# Deployment & Testing Guide - Phase 2 Updates

## Summary of Changes

This deployment includes:
1. **Camera Resolution Upgrade**: 320x240 → 640x480 for improved readability
2. **Database Schema Enhancement**: New `alert_recipients` and `alert_config` tables
3. **Recipient Management**: Dynamic add/remove/toggle via dashboard (no more hardcoding)
4. **GSMNotifier Enhancement**: Uses database recipients by default, falls back to config
5. **Dashboard API**: New endpoints for managing recipients

## Pre-Deployment Checklist

- [ ] Verify all Python files have no syntax errors (✅ Completed)
- [ ] Backup existing database (if upgrading from previous version)
- [ ] Review config.yaml camera settings (640x480 now)
- [ ] Verify Flask and dependencies installed

## Deployment Steps

### 1. Pull/Update Code
```bash
cd /path/to/Pig_Tracking
git pull origin main  # or merge your branch
```

### 2. Database Initialization (Automatic)
On first run, the system will:
- Check if database exists at `database.db.sqlite`
- If not, call `initialize_database()` from `src/database/schema.py`
- Create `alert_recipients` and `alert_config` tables
- Initialize other tables if missing

**No manual SQL migration needed** — schema.py uses `CREATE TABLE IF NOT EXISTS`.

### 3. First Run Setup
```bash
python3 src/main.py
```

Expected first-run behavior:
- Database created (or tables added)
- No recipients configured yet → SMS alerts will not send (logged as warning)
- Camera opens at 640x480
- Dashboard available at http://localhost:5000

### 4. Add Recipients via Dashboard

**Method 1: UI (Recommended)**
1. Navigate to http://localhost:5000/settings
2. Scroll to "GSM SMS Alerts" section
3. Enter phone number in format "+63XXXXXXXXXX"
4. Click "+ Add" button
5. Verify recipient appears in list with "✓ Active" status

**Method 2: Database Direct (Emergency)**
```bash
sqlite3 database.db.sqlite
INSERT INTO alert_recipients (phone_number, enabled, created_at, updated_at) 
  VALUES ('+63XXXXXXXXXX', 1, datetime('now'), datetime('now'));
.quit
```

### 5. Backward Compatibility Check

If upgrading from old code that used `config.gsm.phone_numbers`:
- Old phone numbers in config.yaml are still respected as fallback
- New recipients in database take precedence
- SMS dispatch order:
  1. Repository recipients (if available)
  2. Config phone_numbers (if repo lookup fails)
  3. No SMS (if neither available)

To migrate old config recipients to database:
1. Note current phone numbers from config.yaml
2. Add them via dashboard settings (UI or direct)
3. Optionally remove from config.yaml (but not required)

### 6. Testing the Recipients System

**Manual Test - Add Recipient**
```bash
curl -X POST http://localhost:5000/api/recipients \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "+63XXXXXXXXXX"}'

# Expected response:
# {"status": "success", "message": "Recipient added: +63XXXXXXXXXX", "recipient_id": 1}
```

**Manual Test - List Recipients**
```bash
curl http://localhost:5000/api/recipients

# Expected response:
# {"status": "success", "recipients": [{"id": 1, "phone_number": "+63XXXXXXXXXX", "enabled": 1}]}
```

**Manual Test - Toggle Recipient**
```bash
curl -X PATCH http://localhost:5000/api/recipients/1/toggle \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'

# Expected response:
# {"status": "success", "message": "Recipient disabled", "recipient_id": 1, "enabled": false}
```

**Manual Test - SMS Dispatch**
1. Add a recipient via dashboard
2. Trigger an alert condition (e.g., high THI or stationary pig)
3. Verify in logs: `SMS alert sent [alert_type] to X recipient(s)`
4. If SMS module available, verify SMS delivery

### 7. Camera Resolution Testing

Expected FPS with 640x480 on Raspberry Pi 4:
- Baseline ONNX inference: 48-54ms (~20 FPS theoretical max)
- With frame_skip=3: ~5-8 FPS displayed (detection every 4th frame, tracking every frame)
- Display refresh: 30 FPS max (MJPEG sleep 0.033s)

**Performance Check**
1. Monitor logs for FPS output (every 30 frames)
2. Check dashboard video feed responsiveness
3. If FPS drops below 3, consider:
   - Increase frame_skip to 4 in config.yaml
   - Check Pi CPU usage (htop)
   - Verify no other processes consuming resources

### 8. Rollback Plan

If issues occur:
1. **Database Problem**: Delete `database.db.sqlite`, restart (will recreate)
2. **Recipients Not Working**: Check logs for errors, verify database tables exist
3. **Previous Code**: `git checkout HEAD~1` to revert commits
4. **Restore Config**: Keep backup of config.yaml with working phone_numbers

## Known Issues & Workarounds

### Issue: Recipients show but SMS not sending
**Cause**: Repository lookup failing silently, config.gsm.phone_numbers may be empty
**Fix**: 
1. Check logs for errors in `get_enabled_recipients()`
2. Verify alert_recipients table has enabled=1 rows
3. Fallback: Add phone_numbers back to config.yaml GSM section

### Issue: Camera at 640x480 causes lag
**Cause**: ONNX inference slower at higher resolution
**Fix**:
1. Increase frame_skip from 3 to 4 (process detection every 5 frames)
2. Or revert to 320x240 in config.yaml
3. Trade-off: Lower resolution = sharper FPS, smaller image

### Issue: Settings page doesn't load recipients
**Cause**: API endpoint returning error or database not initialized
**Fix**:
1. Check browser console (F12) for fetch errors
2. Verify database.db.sqlite exists and is readable
3. Check Flask logs for 500 errors on `/api/recipients`

## Configuration Reference

### config.yaml Changes
```yaml
camera:
  width: 640          # Changed from 320
  height: 480         # Changed from 240
  fps: 30
  
gsm:
  enabled: true
  phone_numbers: []   # Optional (only used as fallback)
  cooldown_minutes: 5
```

### Database Tables Added

**alert_recipients**
```sql
CREATE TABLE alert_recipients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number TEXT NOT NULL UNIQUE,
    enabled INTEGER DEFAULT 1,           -- 1=active, 0=disabled
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

**alert_config** (Reserved for future use)
```sql
CREATE TABLE alert_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    data_type TEXT,
    description TEXT,
    updated_at TEXT NOT NULL
);
```

### New API Endpoints
- `GET /api/recipients` → List all
- `POST /api/recipients` → Add (JSON: {phone_number: "..."})
- `DELETE /api/recipients/<id>` → Remove
- `PATCH /api/recipients/<id>/toggle` → Toggle enabled (JSON: {enabled: true/false})

## Next Phase: Alert Configuration Dashboard

The foundation is now in place for Phase 3, which will:
1. Expose HerdRiskEngine parameters to dashboard
2. Add enable/disable toggles for alert types
3. Allow custom SMS message templates
4. Load alert config from database at runtime

Database table `alert_config` is already created but not yet used. When Phase 3 starts:
- Repository methods `get_alert_config()`, `set_alert_config()` are ready
- Dashboard routes need to be extended with `/api/alert_config` endpoints
- HerdRiskEngine needs refactoring to load config at runtime

## Monitoring & Diagnostics

After deployment, monitor these:
1. **Database Size**: `ls -lh database.db.sqlite` (should stay small, <10MB)
2. **Recipient Count**: `curl http://localhost:5000/api/recipients` (verify populated)
3. **SMS Logs**: `grep "SMS alert" logs/main.log` (verify dispatch)
4. **FPS**: Check main loop console output (should be 5-8 FPS with 640x480)
5. **Errors**: Check for `ERROR` level logs in dashboard

## Support

For issues:
1. Check logs: `tail -100 /path/to/logfile.log`
2. Verify database: `sqlite3 database.db.sqlite ".tables"` (should show alert_recipients)
3. Test API: `curl http://localhost:5000/api/recipients`
4. Check Flask: Restart and watch for initialization errors

---
**Version**: Phase 2 (Camera Upgrade + Recipient Management)
**Date**: 2026-08-13
**Status**: Ready for Deployment
