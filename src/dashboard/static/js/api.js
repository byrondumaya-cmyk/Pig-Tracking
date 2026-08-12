/**
 * api.js — Shared Fetch Helpers
 * Swine Health Monitor Dashboard
 */

/**
 * Standard fetch wrapper that handles JSON parsing and error throwing.
 * @param {string} url - API endpoint
 * @param {object} options - Fetch options (method, body, etc.)
 * @returns {Promise<any>} JSON response data
 */
async function apiFetch(url, options = {}) {
    const defaultHeaders = {
        'Accept': 'application/json',
    };
    
    // If sending JSON, set Content-Type
    if (options.body && typeof options.body === 'string' && options.body.startsWith('{')) {
        defaultHeaders['Content-Type'] = 'application/json';
    }

    const config = {
        ...options,
        headers: {
            ...defaultHeaders,
            ...options.headers
        }
    };

    try {
        const response = await fetch(url, config);
        
        // Some endpoints (like DELETE) might return 204 No Content
        if (response.status === 204) {
            return null;
        }

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || `HTTP error ${response.status}`);
        }

        return data;
    } catch (error) {
        console.error(`API Error (${url}):`, error);
        throw error;
    }
}

/**
 * Show a temporary toast notification (requires a #toast element in HTML, or creates one)
 */
function showToast(message, type = 'info') {
    let toast = document.getElementById('toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast';
        Object.assign(toast.style, {
            position: 'fixed',
            bottom: '20px',
            right: '20px',
            padding: '12px 20px',
            borderRadius: '8px',
            color: 'white',
            fontWeight: '500',
            fontSize: '14px',
            zIndex: '9999',
            opacity: '0',
            transform: 'translateY(20px)',
            transition: 'all 0.3s ease',
            boxShadow: '0 4px 12px rgba(0,0,0,0.3)',
            pointerEvents: 'none'
        });
        document.body.appendChild(toast);
    }

    // Set color based on type
    if (type === 'success') toast.style.backgroundColor = 'var(--green, #3fb950)';
    else if (type === 'error') toast.style.backgroundColor = 'var(--red, #f85149)';
    else toast.style.backgroundColor = 'var(--bg-elevated, #21262d)';

    // Reset animation state
    toast.style.transition = 'none';
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(20px)';
    
    // Force reflow
    void toast.offsetWidth;

    // Show
    toast.textContent = message;
    toast.style.transition = 'all 0.3s ease';
    toast.style.opacity = '1';
    toast.style.transform = 'translateY(0)';

    // Hide after 3s
    if (toast.timeoutId) clearTimeout(toast.timeoutId);
    toast.timeoutId = setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(20px)';
    }, 3000);
}
