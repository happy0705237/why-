/**
 * API 调用封装
 */
const API_BASE = '';

async function apiGet(path) {
    try {
        const res = await fetch(`${API_BASE}${path}`);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return await res.json();
    } catch (e) {
        console.error(`GET ${path} failed:`, e);
        throw e;
    }
}

async function apiPost(path, body) {
    try {
        const res = await fetch(`${API_BASE}${path}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return await res.json();
    } catch (e) {
        console.error(`POST ${path} failed:`, e);
        throw e;
    }
}

async function apiDelete(path) {
    try {
        const res = await fetch(`${API_BASE}${path}`, { method: 'DELETE' });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        return await res.json();
    } catch (e) {
        console.error(`DELETE ${path} failed:`, e);
        throw e;
    }
}

// API 端点
const API = {
    getDisks: () => apiGet('/api/disks'),
    getCommonPaths: () => apiGet('/api/common-paths'),
    createScan: (data) => apiPost('/api/scan', data),
    getScan: (id) => apiGet(`/api/scan/${id}`),
    deleteScan: (id) => apiDelete(`/api/scan/${id}`),
    listScans: (page = 1) => apiGet(`/api/scans?page=${page}`),
    getTree: (scanId, path = null, sortBy = 'size', order = 'desc') => {
        let url = `/api/scan/${scanId}/tree?sort_by=${sortBy}&order=${order}`;
        if (path) url += `&path=${encodeURIComponent(path)}`;
        return apiGet(url);
    },
    getTopFiles: (scanId, limit = 50, offset = 0) =>
        apiGet(`/api/scan/${scanId}/files/top?limit=${limit}&offset=${offset}`),
    getFileTypes: (scanId) => apiGet(`/api/scan/${scanId}/files/types`),
    getScanErrors: (scanId, limit = 50) =>
        apiGet(`/api/scan/${scanId}/errors?limit=${limit}`),
};
