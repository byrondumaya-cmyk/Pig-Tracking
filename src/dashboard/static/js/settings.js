/**
 * settings.js — Settings Page Logic (Tabs + API integration)
 * Swine Health Monitor Dashboard
 */

document.addEventListener('DOMContentLoaded', () => {
    // ── Tab Navigation ──────────────────────────────────────────────────────
    const tabs = document.querySelectorAll('.tab-btn');
    const panels = document.querySelectorAll('.tab-panel');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetId = tab.dataset.target;
            
            // Deactivate all
            tabs.forEach(t => t.classList.remove('active'));
            panels.forEach(p => p.classList.remove('active'));
            
            // Activate target
            tab.classList.add('active');
            document.getElementById(targetId).classList.add('active');
            
            // Optional: trigger reload of specific tab data if needed
            if (targetId === 'tab-logs') loadSmsLogs();
        });
    });

    // ── Initialize Data ─────────────────────────────────────────────────────
    loadAlertConfig();
    loadRecipients();
    loadSmsTemplates();
    loadSmsLogs();
    loadTimeSyncLogs();
    
    updateCurrentTime();
    setInterval(updateCurrentTime, 1000);

    // ── Event Listeners ─────────────────────────────────────────────────────
    document.getElementById('save-alerts-btn').addEventListener('click', saveAlertConfig);
    document.getElementById('reset-alerts-btn').addEventListener('click', resetAlertConfig);
    
    document.getElementById('add-recipient-btn').addEventListener('click', addRecipient);
    document.getElementById('new-phone-input').addEventListener('keypress', e => {
        if (e.key === 'Enter') addRecipient();
    });

    document.getElementById('filter-logs-btn').addEventListener('click', loadSmsLogs);
    document.getElementById('clear-logs-btn').addEventListener('click', deleteOldLogs);
    
    document.getElementById('sync-ntp-btn').addEventListener('click', syncNtp);

    // Set today as max date for log filter
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('log-date-picker').max = today;
});

// ── Alert Config ────────────────────────────────────────────────────────────
async function loadAlertConfig() {
    try {
        const data = await apiFetch('/api/alert_config');
        if (data.status === 'success') {
            const c = data.config;
            document.getElementById('alert_individual_enabled').checked = c.alert_individual_enabled;
            document.getElementById('stationary_alert_minutes').value = c.stationary_alert_minutes;
            document.getElementById('stationary_heat_stress_minutes').value = c.stationary_heat_stress_minutes;
            document.getElementById('fever_delta_threshold_c').value = c.fever_delta_threshold_c;
            
            document.getElementById('alert_population_enabled').checked = c.alert_population_enabled;
            document.getElementById('population_lethargy_ratio').value = c.population_lethargy_ratio;
            document.getElementById('population_persist_seconds').value = c.population_persist_seconds;
            
            document.getElementById('thi_heat_stress_threshold').value = c.thi_heat_stress_threshold;
            document.getElementById('cooldown_minutes').value = c.cooldown_minutes;
        }
    } catch (e) {
        showToast('Failed to load alert settings', 'error');
    }
}

async function saveAlertConfig() {
    const btn = document.getElementById('save-alerts-btn');
    btn.disabled = true;
    
    const config = {
        alert_individual_enabled: document.getElementById('alert_individual_enabled').checked,
        stationary_alert_minutes: parseFloat(document.getElementById('stationary_alert_minutes').value),
        stationary_heat_stress_minutes: parseFloat(document.getElementById('stationary_heat_stress_minutes').value),
        fever_delta_threshold_c: parseFloat(document.getElementById('fever_delta_threshold_c').value),
        
        alert_population_enabled: document.getElementById('alert_population_enabled').checked,
        population_lethargy_ratio: parseFloat(document.getElementById('population_lethargy_ratio').value),
        population_persist_seconds: parseInt(document.getElementById('population_persist_seconds').value),
        
        thi_heat_stress_threshold: parseFloat(document.getElementById('thi_heat_stress_threshold').value),
        cooldown_minutes: parseInt(document.getElementById('cooldown_minutes').value)
    };

    try {
        const data = await apiFetch('/api/alert_config', {
            method: 'PATCH',
            body: JSON.stringify(config)
        });
        showToast('Alert settings saved', 'success');
        await loadAlertConfig(); // reload to confirm
    } catch (e) {
        showToast('Failed to save settings: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

async function resetAlertConfig() {
    if (!confirm('Reset all alert settings to defaults?')) return;
    
    // We fetch defaults from the server
    try {
        const data = await apiFetch('/api/alert_config/defaults');
        if (data.status === 'success') {
            await apiFetch('/api/alert_config', {
                method: 'PATCH',
                body: JSON.stringify(data.defaults)
            });
            showToast('Settings reset to defaults', 'success');
            await loadAlertConfig();
        }
    } catch (e) {
        showToast('Failed to reset settings', 'error');
    }
}

// ── SMS Recipients ──────────────────────────────────────────────────────────
async function loadRecipients() {
    const list = document.getElementById('recipients-list');
    try {
        const data = await apiFetch('/api/recipients');
        if (!data.recipients || data.recipients.length === 0) {
            list.innerHTML = `<div class="info-box">No recipients configured. Add one below.</div>`;
            return;
        }
        
        list.innerHTML = data.recipients.map(r => `
            <div class="recipient-item ${!r.enabled ? 'disabled' : ''}">
                <div>
                    <div class="recipient-phone">${escapeHtml(r.phone_number)}</div>
                    <div class="recipient-status ${r.enabled ? 'active' : ''}">
                        ${r.enabled ? 'Active' : 'Disabled'}
                    </div>
                </div>
                <div class="recipient-actions">
                    <button class="btn ${r.enabled ? 'btn-ghost' : 'btn-primary'}" 
                            onclick="toggleRecipient(${r.id}, ${r.enabled})">
                        ${r.enabled ? 'Disable' : 'Enable'}
                    </button>
                    <button class="btn btn-danger" onclick="removeRecipient(${r.id})">Remove</button>
                </div>
            </div>
        `).join('');
    } catch (e) {
        list.innerHTML = `<div class="info-box" style="border-left-color: var(--red);">Error loading recipients</div>`;
    }
}

async function addRecipient() {
    const input = document.getElementById('new-phone-input');
    const phone = input.value.trim();
    if (!phone) {
        showToast('Enter a phone number', 'error');
        return;
    }
    
    const btn = document.getElementById('add-recipient-btn');
    btn.disabled = true;
    
    try {
        const data = await apiFetch('/api/recipients', {
            method: 'POST',
            body: JSON.stringify({ phone_number: phone })
        });
        showToast('Recipient added', 'success');
        input.value = '';
        await loadRecipients();
    } catch (e) {
        showToast('Failed to add recipient: ' + e.message, 'error');
    } finally {
        btn.disabled = false;
    }
}

// Global functions for inline onclick
window.toggleRecipient = async function(id, currentlyEnabled) {
    try {
        await apiFetch(`/api/recipients/${id}/toggle`, {
            method: 'PATCH',
            body: JSON.stringify({ enabled: !currentlyEnabled })
        });
        showToast(currentlyEnabled ? 'Recipient disabled' : 'Recipient enabled', 'success');
        await loadRecipients();
    } catch (e) {
        showToast('Failed to toggle recipient', 'error');
    }
};

window.removeRecipient = async function(id) {
    if (!confirm('Remove this recipient?')) return;
    try {
        await apiFetch(`/api/recipients/${id}`, { method: 'DELETE' });
        showToast('Recipient removed', 'success');
        await loadRecipients();
    } catch (e) {
        showToast('Failed to remove recipient', 'error');
    }
};

// ── SMS Templates ───────────────────────────────────────────────────────────
async function loadSmsTemplates() {
    const list = document.getElementById('templates-list');
    try {
        const data = await apiFetch('/api/sms_templates');
        if (!data.templates || data.templates.length === 0) {
            list.innerHTML = `<div class="info-box">No templates found.</div>`;
            return;
        }
        
        list.innerHTML = data.templates.map(t => `
            <div class="panel" style="margin-bottom: var(--space-4);">
                <div class="panel__header">
                    <h3 class="panel__title">${escapeHtml(t.name)}</h3>
                    <span class="text-xs font-mono text-subtle">${t.alert_type}</span>
                </div>
                <div class="panel__body">
                    <p class="font-mono text-sm" style="margin-bottom: var(--space-3); color: var(--text-primary);">
                        ${escapeHtml(t.message_body)}
                    </p>
                    <button class="btn btn-ghost" onclick="editTemplate(${t.id}, '${escapeHtml(t.message_body)}')">
                        Edit Message
                    </button>
                </div>
            </div>
        `).join('');
    } catch (e) {
        list.innerHTML = `<div class="info-box">Error loading templates</div>`;
    }
}

window.editTemplate = async function(id, currentMsg) {
    const newMsg = prompt('Edit template message (leave variables like {zone_temp} intact):', currentMsg);
    if (newMsg === null || newMsg === currentMsg) return;
    if (newMsg.trim() === '') {
        showToast('Message cannot be empty', 'error');
        return;
    }
    
    try {
        await apiFetch(`/api/sms_templates/${id}`, {
            method: 'PATCH',
            body: JSON.stringify({ message_body: newMsg.trim() })
        });
        showToast('Template updated', 'success');
        await loadSmsTemplates();
    } catch (e) {
        showToast('Failed to update template', 'error');
    }
};

// ── SMS Logs ────────────────────────────────────────────────────────────────
async function loadSmsLogs() {
    const container = document.getElementById('sms-logs-container');
    const dateInput = document.getElementById('log-date-picker').value;
    const url = dateInput ? `/api/sms_logs?date=${dateInput}` : '/api/sms_logs?days=7';
    
    try {
        const data = await apiFetch(url);
        if (!data.logs || data.logs.length === 0) {
            container.innerHTML = `<div class="alert-empty">No SMS logs found for this period.</div>`;
            return;
        }
        
        let html = `
            <table class="sms-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Type</th>
                        <th>Recipient</th>
                        <th>Status</th>
                        <th>Message</th>
                    </tr>
                </thead>
                <tbody>
        `;
        
        data.logs.forEach(log => {
            const statusClass = log.status === 'sent' ? 'text-green' : 'text-red';
            html += `
                <tr>
                    <td>${log.timestamp.split('T')[1]?.substring(0,8) || log.timestamp}</td>
                    <td><span class="thi-badge ${log.status === 'sent' ? 'normal' : 'stress'}">${log.alert_type}</span></td>
                    <td class="font-mono">${escapeHtml(log.recipient_phone)}</td>
                    <td class="font-bold ${statusClass}">${log.status}</td>
                    <td>${escapeHtml(log.message_body)}</td>
                </tr>
            `;
        });
        
        html += `</tbody></table>`;
        container.innerHTML = html;
        
    } catch (e) {
        container.innerHTML = `<div class="alert-empty text-red">Error loading logs</div>`;
    }
}

async function deleteOldLogs() {
    const input = prompt('Delete logs older than this date (YYYY-MM-DD):', new Date().toISOString().split('T')[0]);
    if (!input) return;
    
    if (!confirm(`Are you sure you want to permanently delete logs before ${input}?`)) return;
    
    try {
        const data = await apiFetch('/api/sms_logs/delete', {
            method: 'POST',
            body: JSON.stringify({ before_date: input })
        });
        showToast(data.message || 'Logs deleted', 'success');
        await loadSmsLogs();
    } catch (e) {
        showToast('Failed to delete logs: ' + e.message, 'error');
    }
}

// ── System Time Sync ────────────────────────────────────────────────────────
function updateCurrentTime() {
    const el = document.getElementById('current-time');
    if (el) {
        const now = new Date();
        el.textContent = now.toLocaleString();
    }
}

async function loadTimeSyncLogs() {
    const container = document.getElementById('time-sync-logs');
    try {
        const data = await apiFetch('/api/time_sync');
        if (!data.sync_logs || data.sync_logs.length === 0) {
            container.innerHTML = `<div class="text-subtle text-sm">No sync history.</div>`;
            return;
        }
        
        container.innerHTML = data.sync_logs.map(log => `
            <div class="text-sm" style="margin-bottom: 4px;">
                <span class="font-mono text-subtle">${log.timestamp.split('T')[1].substring(0,8)}</span>
                <span class="${log.status === 'success' ? 'text-green' : 'text-red'} font-bold" style="margin-left: 8px;">[${log.source_type.toUpperCase()}]</span>
                <span>${log.status}</span>
            </div>
        `).join('');
    } catch (e) {
        // fail silently
    }
}

async function syncNtp() {
    const btn = document.getElementById('sync-ntp-btn');
    btn.disabled = true;
    
    try {
        const data = await apiFetch('/api/time_sync', {
            method: 'POST',
            body: JSON.stringify({ source_type: 'ntp' })
        });
        showToast(data.message, data.status === 'success' ? 'success' : 'error');
        await loadTimeSyncLogs();
    } catch (e) {
        showToast('NTP sync failed', 'error');
    } finally {
        btn.disabled = false;
    }
}

// Simple HTML escaper
function escapeHtml(unsafe) {
    if (!unsafe) return '';
    return unsafe
         .toString()
         .replace(/&/g, "&amp;")
         .replace(/</g, "&lt;")
         .replace(/>/g, "&gt;")
         .replace(/"/g, "&quot;")
         .replace(/'/g, "&#039;");
}
