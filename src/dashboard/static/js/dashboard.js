/**
 * dashboard.js — Index Page Polling and UI Logic
 * Swine Health Monitor Dashboard
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── Thermal Canvas ──────────────────────────────────────────────────────
    const canvas = document.getElementById('thermal-canvas');
    let ctx = null;
    if (canvas) {
        ctx = canvas.getContext('2d', { willReadFrequently: true });
        // Scale canvas internal resolution to 32x32 to allow smooth bilinear interpolation 
        // when drawn to screen size via CSS
        canvas.width = 32;
        canvas.height = 32;
        ctx.imageSmoothingEnabled = true;
    }

    function getColor(temp) {
        // Map 20C (blue) to 40C (red) smoothly
        const minT = 20, maxT = 40;
        let t = (temp - minT) / (maxT - minT);
        t = Math.max(0, Math.min(1, t)); // clamp 0-1
        
        // Simple heatmap gradient: Blue -> Cyan -> Green -> Yellow -> Red
        const r = Math.round(255 * Math.max(0, 1.5 * t - 0.5));
        const g = Math.round(255 * Math.sin(Math.PI * t));
        const b = Math.round(255 * Math.max(0, 1 - 2 * t));
        return `rgb(${r},${g},${b})`;
    }

    async function fetchThermal() {
        if (!ctx) return;
        try {
            const data = await apiFetch('/api/thermal_feed');
            if (!data.grid) {
                // Sensor offline or not ready
                ctx.fillStyle = '#161b22'; // var(--bg-panel)
                ctx.fillRect(0, 0, 32, 32);
                updateText('thermal-max', '--°C');
                updateText('thermal-avg', '--°C');
                updateText('thermal-min', '--°C');
                return;
            }

            // Draw to an 8x8 offscreen canvas first
            const off = document.createElement('canvas');
            off.width = 8;
            off.height = 8;
            const octx = off.getContext('2d');

            for (let i = 0; i < 8; i++) {
                for (let j = 0; j < 8; j++) {
                    octx.fillStyle = getColor(data.grid[i][j]);
                    octx.fillRect(j, i, 1, 1);
                }
            }

            // Draw offscreen to main canvas (scaled up with smoothing)
            ctx.drawImage(off, 0, 0, 8, 8, 0, 0, 32, 32);

            updateText('thermal-max', `${data.max_temp_c?.toFixed(1) ?? '--'}°C`);
            updateText('thermal-avg', `${data.avg_temp_c?.toFixed(1) ?? '--'}°C`);
            updateText('thermal-min', `${data.min_temp_c?.toFixed(1) ?? '--'}°C`);
        } catch (e) {
            // Silently fail on polling errors
        }
    }

    // ── Ambient Data ────────────────────────────────────────────────────────
    async function fetchAmbient() {
        try {
            const data = await apiFetch('/api/ambient');
            updateText('ambient-temp', `${data.temp_c}°C`);
            updateText('ambient-rh', `${data.humidity_pct}%`);
            
            const thiStr = data.thi.toFixed(1);
            updateText('thi-val', thiStr);
            
            // Mobile pills
            updateText('pill-temp', `${data.temp_c}°C`);
            updateText('pill-thi', thiStr);

            const badge = document.getElementById('thi-badge');
            if (badge) {
                badge.className = data.thi > 78 ? 'thi-badge stress' : 'thi-badge normal';
            }
        } catch (e) {}
    }

    // ── Behavior Distribution ───────────────────────────────────────────────
    // API keys use the canonical class names; the UI shortens 'social_interaction'
    const behaviorKeys = [
        ['lying', 'lying'],
        ['standing', 'standing'],
        ['walking', 'walking'],
        ['sitting', 'sitting'],
        ['feeding', 'feeding'],
        ['drinking', 'drinking'],
        ['social', 'social_interaction'],
        ['aggression', 'aggression'],
    ];

    async function fetchBehaviors() {
        try {
            const data = await apiFetch('/api/behavior_counts');
            const total = data.total || 0;
            
            updateText('pig-count', total.toString());
            updateText('pill-pigs', total.toString());

            behaviorKeys.forEach(([uiKey, apiKey]) => {
                const count = data[apiKey] || 0;
                const pct = total > 0 ? (count / total) * 100 : 0;
                
                updateText(`count-${uiKey}`, count.toString());
                
                const bar = document.getElementById(`bar-${uiKey}`);
                if (bar) {
                    bar.style.width = `${pct}%`;
                }
            });
        } catch (e) {}
    }

    // ── Alerts Log ──────────────────────────────────────────────────────────
    const alertBanner = document.getElementById('global-alert-banner');
    
    async function fetchAlerts() {
        try {
            const data = await apiFetch('/api/pen_alerts');
            const container = document.getElementById('alert-log-container');
            if (!container) return;
            
            if (!data.alerts || data.alerts.length === 0) {
                container.innerHTML = '<div class="alert-empty">No abnormal behavior detected.</div>';
                if (alertBanner) alertBanner.classList.remove('animate-in', 'visible');
                return;
            }
            
            let hasUnresolved = false;
            let html = '';
            
            data.alerts.forEach(alert => {
                if (!alert.resolved) hasUnresolved = true;
                
                let rowClass = 'alert-row';
                let icon = '🔴';
                
                if (alert.resolved) {
                    rowClass += ' resolved';
                    icon = '✅';
                } else if (alert.alert_type === 'population') {
                    rowClass += ' population';
                    icon = '🟡';
                } else {
                    rowClass += ' unresolved';
                }

                const resolveBtn = !alert.resolved 
                    ? `<button class="btn btn-resolve" onclick="resolveAlert('${alert.id}', this)">Resolve</button>` 
                    : '';
                    
                const smsBadge = alert.sms_sent 
                    ? `<span class="badge badge-success" style="margin-left: 8px; font-size: 0.75rem; padding: 2px 6px; border-radius: 4px; background: rgba(46,160,67,0.2); color: #3fb950; border: 1px solid rgba(46,160,67,0.4);">📱 SMS Dispatched</span>` 
                    : '';
                    
                const snapshotBtn = alert.snapshot_path 
                    ? `<a href="/snapshots/${alert.snapshot_path.split(/[\\/]/).pop()}" target="_blank" class="btn btn-ghost" style="padding: 4px 8px; font-size: 0.8rem; margin-right: 8px;">📸 Snapshot</a>` 
                    : '';

                html += `
                    <div class="${rowClass}" id="alert-row-${alert.id}">
                        <div class="alert-row__icon">${icon}</div>
                        <div class="alert-row__body">
                            <div class="alert-row__type">${alert.alert_type}</div>
                            <div class="alert-row__msg">${alert.message}</div>
                            <div class="alert-row__time">${alert.timestamp}${smsBadge}</div>
                        </div>
                        <div class="alert-row__actions" style="display: flex; align-items: center;">
                            ${snapshotBtn}
                            ${resolveBtn}
                        </div>
                    </div>
                `;
            });
            
            container.innerHTML = html;
            
            if (alertBanner) {
                if (hasUnresolved) {
                    if (!alertBanner.classList.contains('visible')) {
                        alertBanner.classList.add('animate-in', 'visible');
                    }
                } else {
                    alertBanner.classList.remove('animate-in', 'visible');
                }
            }
        } catch (e) {}
    }

    // Export resolve function to global scope for the inline onclick handler
    window.resolveAlert = async function(alertId, btnEl) {
        btnEl.disabled = true;
        btnEl.textContent = '...';
        try {
            await apiFetch(`/api/resolve_alert/${alertId}`, { method: 'POST' });
            // Remove row locally with animation
            const row = document.getElementById(`alert-row-${alertId}`);
            if (row) {
                row.classList.add('resolving');
                setTimeout(() => fetchAlerts(), 300); // re-fetch to sync state
            }
            showToast('Alert resolved', 'success');
        } catch (e) {
            btnEl.disabled = false;
            btnEl.textContent = 'Resolve';
            showToast('Failed to resolve alert', 'error');
        }
    };

    // ── Helper: Flash text update ───────────────────────────────────────────
    function updateText(id, newText) {
        const el = document.getElementById(id);
        if (el && el.textContent !== newText) {
            // Remove skeleton class if present (initial load)
            el.classList.remove('skeleton', 'skeleton-text', 'skeleton-value');
            
            el.textContent = newText;
            
            // Re-trigger CSS flash animation
            el.classList.remove('flash');
            void el.offsetWidth; // trigger reflow
            el.classList.add('flash');
        }
    }

    // ── Remove Skeletons on First Load ──────────────────────────────────────
    function removeSkeletons(parentSelector) {
        document.querySelectorAll(`${parentSelector} .skeleton`).forEach(el => {
            el.classList.remove('skeleton', 'skeleton-text', 'skeleton-value');
        });
    }

    // ── AP Connection Info ───────────────────────────────────────────────────
    async function fetchApInfo() {
        try {
            const data = await apiFetch('/api/ap-info');
            if (!data || !data.ap_active) return; // LAN mode — keep card hidden

            const card = document.getElementById('ap-info-card');
            if (card) card.style.display = '';

            const ssidEl = document.getElementById('ap-ssid');
            const passEl = document.getElementById('ap-password');
            const urlEl  = document.getElementById('ap-url');
            const canvas = document.getElementById('ap-qr-canvas');

            if (ssidEl) ssidEl.textContent = data.ssid || '--';
            if (passEl) passEl.textContent = data.password || '--';
            if (urlEl)  urlEl.textContent  = data.dashboard_url || '--';

            // Render QR code onto canvas (qrcode.js must be loaded)
            if (canvas && data.wifi_qr && typeof QRCode !== 'undefined') {
                QRCode.toCanvas(canvas, data.wifi_qr, {
                    width: 180,
                    margin: 1,
                    color: { dark: '#000000', light: '#ffffff' }
                }, (err) => {
                    if (err) console.warn('QR generation failed:', err);
                });
            }
        } catch (e) {
            // AP info is non-critical — fail silently
        }
    }

    // ── Start Polling ───────────────────────────────────────────────────────
    // Initial fetch
    fetchThermal();
    fetchAmbient();
    fetchBehaviors();
    fetchAlerts();
    fetchApInfo(); // One-time: AP config doesn't change at runtime

    // Start intervals
    setInterval(fetchThermal, 200);   // Fast refresh for thermal mapping
    setInterval(fetchBehaviors, 1000); // 1s for behaviors
    setInterval(fetchAmbient, 5000);  // 5s for ambient (sensor is slow anyway)
    setInterval(fetchAlerts, 5000);   // 5s for alerts
});
