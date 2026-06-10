/**
 * DiskManager 主应用逻辑
 */

// ==================== 状态 ====================
const state = {
    currentPage: 'dashboard',
    currentScanId: null,
    currentPath: null,
    scanPollTimer: null,
};

// ==================== 工具函数 ====================

/** HTML 文本转义（防 XSS） */
function esc(s) {
    if (s == null) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/** HTML 属性值转义 */
function escAttr(s) {
    if (s == null) return '';
    return String(s).replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/'/g, '&#39;').replace(/</g, '&lt;');
}

function formatSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return (bytes / Math.pow(1024, i)).toFixed(i > 1 ? 2 : 0) + ' ' + units[i];
}

function formatDuration(seconds) {
    if (!seconds) return '-';
    if (seconds < 1) return '< 1 秒';
    if (seconds < 60) return seconds.toFixed(1) + ' 秒';
    return Math.floor(seconds / 60) + ' 分 ' + Math.round(seconds % 60) + ' 秒';
}

function formatTime(timeStr) {
    if (!timeStr) return '-';
    const d = new Date(timeStr);
    const now = new Date();
    const isToday = d.toDateString() === now.toDateString();
    if (isToday) {
        return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    }
    const yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) {
        return '昨天 ' + d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    }
    return d.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' }) + ' ' +
           d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
}

function showToast(msg, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = msg;
    toast.className = 'toast show ' + type;
    setTimeout(() => { toast.className = 'toast'; }, 3000);
}

function setStatus(text) {
    document.getElementById('status-text').textContent = text;
}

// ==================== 页面切换 ====================
function showPage(page) {
    state.currentPage = page;
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(`page-${page}`).classList.add('active');

    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    const navBtn = document.getElementById(`nav-${page}`);
    if (navBtn) navBtn.classList.add('active');

    if (page === 'dashboard') {
        document.getElementById('nav-scan').style.display = 'none';
        loadDashboard();
    }
}

// ==================== Dashboard ====================
async function loadDashboard() {
    await Promise.all([loadDisks(), loadScanHistory()]);
    populatePathSuggestions();
}

async function loadDisks() {
    try {
        const res = await API.getDisks();
        const partitions = res.data.partitions;
        const container = document.getElementById('disk-cards');
        container.innerHTML = partitions.map(p => {
            // data-path 直接存放原始路径，由事件委托读取，不经过 HTML 属性转义
            const safePath = escAttr(p.mount_point);
            return `
            <div class="disk-card" data-action="quick-scan" data-path="${safePath}">
                <div class="disk-header">
                    <div class="disk-icon">💾</div>
                    <div>
                        <div class="disk-letter">${esc(p.letter)}</div>
                        <div class="disk-label">${esc(p.fs_type)} ${esc(p.mount_point)}</div>
                    </div>
                </div>
                <div class="disk-bar">
                    <div class="disk-bar-fill" style="width:${p.usage_percent}%;background:${getUsageColor(p.usage_percent)}"></div>
                </div>
                <div class="disk-stats">
                    <div class="stat-item">
                        <span class="stat-value">${p.usage_percent}%</span>
                        <span class="stat-label">已用</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-value">${formatSize(p.used_space)}</span>
                        <span class="stat-label">已用</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-value">${formatSize(p.free_space)}</span>
                        <span class="stat-label">可用</span>
                    </div>
                </div>
            </div>`;
        }).join('');
    } catch (e) {
        showToast('加载磁盘信息失败: ' + e.message, 'error');
    }
}

function getUsageColor(pct) {
    if (pct > 90) return '#EF4444';
    if (pct > 75) return '#F59E0B';
    return '#3B82F6';
}

function quickScanDisk(mountPoint) {
    document.getElementById('scan-path').value = mountPoint;
    startScan();
}

function populatePathSuggestions() {
    // 浏览器无法获取系统用户名，仅提供占位提示
    // 用户在输入框中输入路径后由浏览器原生 datalist 提供历史
    const datalist = document.getElementById('path-suggestions');
    datalist.innerHTML = '';
}

async function loadScanHistory() {
    try {
        const res = await API.listScans();
        const items = res.data.items || [];
        const tbody = document.getElementById('history-body');
        const empty = document.getElementById('history-empty');

        if (items.length === 0) {
            tbody.innerHTML = '';
            empty.style.display = 'block';
            return;
        }

        empty.style.display = 'none';
        tbody.innerHTML = items.map((s, i) => `
            <tr data-action="view-scan" data-scan-id="${s.id}">
                <td>${s.id}</td>
                <td style="max-width:300px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(s.root_path)}</td>
                <td>${formatSize(s.total_size)}</td>
                <td>${(s.file_count || 0).toLocaleString()}</td>
                <td>${formatDuration(s.scan_duration)}</td>
                <td><span class="status-badge ${s.status}">${statusLabel(s.status)}</span></td>
                <td>${formatTime(s.completed_at || s.created_at)}</td>
            </tr>
        `).join('');
    } catch (e) {
        console.error('加载历史失败:', e);
    }
}

function statusLabel(status) {
    const labels = { scanning: '扫描中', completed: '已完成', failed: '失败', pending: '等待中', cancelled: '已取消' };
    return labels[status] || status;
}

// ==================== 扫描 ====================
async function startScan() {
    const path = document.getElementById('scan-path').value.trim();
    if (!path) {
        showToast('请输入目录路径', 'error');
        return;
    }

    const btn = document.getElementById('scan-btn');
    btn.disabled = true;
    btn.textContent = '扫描中...';

    const excludePaths = [];
    if (document.getElementById('opt-exclude-sys').checked) {
        excludePaths.push('C:\\$Recycle.Bin', 'C:\\System Volume Information', 'C:\\Windows');
    }

    try {
        const res = await API.createScan({
            path: path,
            exclude_paths: excludePaths,
        });

        if (res.data.scan_id) {
            state.currentScanId = res.data.scan_id;
            showToast('扫描任务已启动', 'success');
            startScanPolling(res.data.scan_id);
        }
    } catch (e) {
        showToast('启动扫描失败: ' + e.message, 'error');
        btn.disabled = false;
        btn.textContent = '开始扫描';
    }
}

function startScanPolling(scanId) {
    const progressEl = document.getElementById('scan-progress');
    progressEl.classList.add('active');

    if (state.scanPollTimer) clearInterval(state.scanPollTimer);

    let startTime = Date.now();

    state.scanPollTimer = setInterval(async () => {
        try {
            const res = await API.getScan(scanId);
            const scan = res.data;
            const elapsed = (Date.now() - startTime) / 1000;

            // 更新进度显示
            const files = scan.progress?.scanned_files || scan.file_count || 0;
            const dirs = scan.progress?.scanned_dirs || scan.dir_count || 0;
            document.getElementById('progress-files').textContent =
                `已扫描 ${files.toLocaleString()} 个文件, ${dirs.toLocaleString()} 个目录`;
            document.getElementById('progress-speed').textContent =
                scan.status === 'scanning' ? `${Math.round(files / Math.max(elapsed, 1))} 文件/秒` : '';

            if (scan.status === 'completed' || scan.status === 'failed' || scan.status === 'cancelled') {
                clearInterval(state.scanPollTimer);
                state.scanPollTimer = null;
                progressEl.classList.remove('active');

                const btn = document.getElementById('scan-btn');
                btn.disabled = false;
                btn.textContent = '开始扫描';

                if (scan.status === 'completed') {
                    showToast(`扫描完成！${formatSize(scan.total_size)}, ${scan.file_count} 个文件`, 'success');
                    // 跳转到扫描详情
                    viewScan(scanId);
                } else {
                    showToast('扫描' + statusLabel(scan.status), 'error');
                }

                loadScanHistory();
            }
        } catch (e) {
            console.error('轮询扫描状态失败:', e);
        }
    }, 800);
}

// ==================== 扫描详情 ====================
async function viewScan(scanId) {
    state.currentScanId = scanId;
    showPage('scan');
    document.getElementById('nav-scan').style.display = '';

    try {
        // 加载扫描信息
        const scanRes = await API.getScan(scanId);
        const scan = scanRes.data;

        document.getElementById('scan-title').textContent = '扫描结果 - ' + scan.root_path;
        document.getElementById('scan-status-badge').className = `status-badge ${scan.status}`;
        document.getElementById('scan-status-badge').textContent = statusLabel(scan.status);

        // 更新信息面板
        document.getElementById('info-path').textContent = scan.root_path;
        document.getElementById('info-size').textContent = formatSize(scan.total_size);
        document.getElementById('info-files').textContent = (scan.file_count || 0).toLocaleString();
        document.getElementById('info-dirs').textContent = (scan.dir_count || 0).toLocaleString();
        document.getElementById('info-errors').textContent = scan.error_count || 0;

        // 加载目录树
        await loadTree(scanId, scan.root_path);

        // 加载类型统计到侧面板
        loadSideTypes(scanId);

        // 加载扫描错误（如有）
        loadScanErrors(scanId, scan.error_count || 0);

        setStatus(`扫描 #${scanId} - ${scan.root_path}`);
    } catch (e) {
        showToast('加载扫描结果失败: ' + e.message, 'error');
    }
}

async function loadTree(scanId, path) {
    state.currentPath = path;

    try {
        const res = await API.getTree(scanId, path);
        const data = res.data;

        // 更新面包屑
        renderBreadcrumb(data.breadcrumb, scanId);

        // 渲染 TreeMap
        renderTreemap('treemap-chart', data.items, data.current_path, (clickedPath) => {
            loadTree(scanId, clickedPath);
        });

        // 渲染目录内容表格
        renderContentTable(data.items, scanId);

    } catch (e) {
        showToast('加载目录树失败: ' + e.message, 'error');
    }
}

function renderBreadcrumb(breadcrumb, scanId) {
    const container = document.getElementById('breadcrumb');
    container.innerHTML = breadcrumb.map((item, i) => {
        const isLast = i === breadcrumb.length - 1;
        const sep = i > 0 ? '<span class="breadcrumb-sep">›</span>' : '';
        const cls = isLast ? 'breadcrumb-item current' : 'breadcrumb-item';
        const attr = isLast ? '' : `data-action="drill" data-scan-id="${scanId}" data-path="${escAttr(item.path)}"`;
        return `${sep}<span class="${cls}" ${attr}>${esc(item.name)}</span>`;
    }).join('');
}

function renderContentTable(items, scanId) {
    const tbody = document.getElementById('content-body');
    if (!items || items.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:#64748B;padding:30px">目录为空</td></tr>';
        return;
    }

    tbody.innerHTML = items.map(item => {
        if (item.is_others) {
            return `<tr style="color:#64748B">
                <td>📦 ${esc(item.name)}</td>
                <td class="size-cell">${formatSize(item.size)}</td>
                <td>-</td>
                <td>${item.size_percent}%</td>
                <td></td>
            </tr>`;
        }

        const isDir = !!item.is_dir;
        const icon = isDir ? '📁' : getFileEmoji(item.extension);
        const type = isDir ? '目录' : `.${item.extension || '-'}`;

        // 行级 data-action（目录可点击下钻）
        const rowAttr = isDir
            ? `data-action="drill" data-scan-id="${scanId}" data-path="${escAttr(item.path)}" style="cursor:pointer"`
            : '';

        // "打开位置" 按钮
        const openPath = item.parent_path || item.path;
        const openBtn = !isDir
            ? `<button class="open-location-btn" data-action="open-location" data-path="${escAttr(openPath)}">打开位置</button>`
            : '';

        return `<tr ${rowAttr}>
            <td>${icon} ${esc(item.name)}</td>
            <td class="size-cell">${formatSize(item.size)}</td>
            <td>${type}</td>
            <td>${item.size_percent}%</td>
            <td>${openBtn}</td>
        </tr>`;
    }).join('');
}

function getFileEmoji(ext) {
    if (!ext) return '📄';
    const type = EXT_TYPE[ext.toLowerCase()];
    const emojis = {
        video: '🎬', image: '🖼️', audio: '🎵', document: '📄',
        archive: '📦', code: '💻', executable: '⚙️',
    };
    return emojis[type] || '📄';
}

// ==================== Tab 切换 ====================
function switchTab(tab) {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(p => p.style.display = 'none');

    event.target.classList.add('active');
    document.getElementById(`tab-${tab}`).style.display = '';

    if (tab === 'topfiles' && state.currentScanId) {
        loadTopFiles(state.currentScanId);
    } else if (tab === 'types' && state.currentScanId) {
        loadTypeStats(state.currentScanId);
    }
}

async function loadTopFiles(scanId) {
    try {
        const res = await API.getTopFiles(scanId, 50);
        const items = res.data.items || [];
        const tbody = document.getElementById('topfiles-body');

        tbody.innerHTML = items.map((f, i) => `
            <tr>
                <td>${i + 1}</td>
                <td>${getFileEmoji(f.extension)} ${esc(f.name)}</td>
                <td class="size-cell">${formatSize(f.size)}</td>
                <td>.${esc(f.extension) || '-'}</td>
                <td style="max-width:250px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#64748B">${esc(f.parent_dir)}</td>
                <td><button class="open-location-btn" data-action="open-location" data-path="${escAttr(f.parent_dir)}">打开位置</button></td>
            </tr>
        `).join('');
    } catch (e) {
        showToast('加载大文件失败: ' + e.message, 'error');
    }
}

async function loadTypeStats(scanId) {
    try {
        const res = await API.getFileTypes(scanId);
        const data = res.data;

        // 渲染饼图
        renderPieChart('types-pie', data.categories);

        // 渲染列表
        const listEl = document.getElementById('types-list');
        listEl.innerHTML = data.categories.slice(0, 15).map(c => {
            const type = EXT_TYPE[c.extension] || 'other';
            const color = TYPE_COLORS[type] || TYPE_COLORS.other;
            const extLabel = c.extension === '(无扩展名)' ? '其他' : `.${c.extension}`;
            return `<div class="type-item">
                <span class="type-dot" style="background:${color}"></span>
                <span class="type-name">${extLabel}</span>
                <span class="type-size">${formatSize(c.total_size)}</span>
                <span class="type-percent">${c.size_percent}%</span>
            </div>`;
        }).join('');
    } catch (e) {
        showToast('加载类型统计失败: ' + e.message, 'error');
    }
}

async function loadSideTypes(scanId) {
    try {
        const res = await API.getFileTypes(scanId);
        const data = res.data;
        const listEl = document.getElementById('info-types');

        listEl.innerHTML = data.categories.slice(0, 8).map(c => {
            const type = EXT_TYPE[c.extension] || 'other';
            const color = TYPE_COLORS[type] || TYPE_COLORS.other;
            const extLabel = c.extension === '(无扩展名)' ? '其他' : `.${c.extension}`;
            return `<div class="type-item">
                <span class="type-dot" style="background:${color}"></span>
                <span class="type-name">${extLabel}</span>
                <span class="type-size">${c.size_percent}%</span>
            </div>`;
        }).join('');
    } catch (e) {
        console.error('加载侧面类型统计失败:', e);
    }
}

// ==================== 扫描错误 ====================
async function loadScanErrors(scanId, errorCount) {
    const panel = document.getElementById('errors-panel');
    if (!errorCount || errorCount <= 0) {
        panel.style.display = 'none';
        return;
    }
    panel.style.display = '';

    try {
        const res = await API.getScanErrors(scanId, 30);
        const data = res.data;

        // 汇总行
        const summaryEl = document.getElementById('errors-summary');
        const typeLabels = { permission: '权限不足', os_error: '系统错误', path_too_long: '路径过长' };
        const parts = Object.entries(data.by_type || {}).map(
            ([t, n]) => `${typeLabels[t] || t}: ${n}`
        );
        summaryEl.innerHTML = `<div style="font-size:12px;color:var(--text-muted);margin-top:4px">
            共 ${data.total} 个错误 — ${parts.join('、')}
        </div>`;

        // 详情列表
        const detailEl = document.getElementById('errors-detail');
        detailEl.innerHTML = data.items.map(e => `
            <div style="padding:5px 0;border-bottom:1px solid var(--border);font-size:12px">
                <div style="color:var(--warning);font-weight:500">${esc(e.error_type)}</div>
                <div style="color:var(--text-secondary);word-break:break-all">${esc(e.path)}</div>
                ${e.error_message ? `<div style="color:var(--text-muted)">${esc(e.error_message)}</div>` : ''}
            </div>
        `).join('');
    } catch (e) {
        console.error('加载扫描错误失败:', e);
    }
}

function toggleErrors() {
    const detail = document.getElementById('errors-detail');
    const toggle = document.getElementById('errors-toggle');
    if (detail.style.display === 'none') {
        detail.style.display = '';
        toggle.textContent = '▼ 收起';
    } else {
        detail.style.display = 'none';
        toggle.textContent = '▶ 展开';
    }
}

// ==================== 操作 ====================
async function openFileLocation(path) {
    try {
        const res = await fetch('/api/open-explorer', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: path }),
        });
        const data = await res.json();
        if (data.code === 200) {
            showToast('已在资源管理器中打开', 'success');
        } else if (data.code === 404) {
            // 文件不存在，回退到复制路径
            await copyPathFallback(path, '文件不存在，路径已复制到剪贴板');
        } else {
            showToast('打开失败: ' + (data.message || '未知错误'), 'error');
        }
    } catch (e) {
        // 网络错误等，回退到复制路径
        await copyPathFallback(path, '无法调用资源管理器，路径已复制到剪贴板');
    }
}

async function copyPathFallback(path, msg) {
    try {
        await navigator.clipboard.writeText(path);
        showToast(msg, 'info');
    } catch {
        showToast('路径: ' + path, 'info');
    }
}

// ==================== 初始化 ====================

/**
 * 事件委托：统一处理所有 data-action 点击。
 * 避免在 innerHTML 中拼接路径到 onclick 属性（反斜杠/引号会导致 JS 语法错误或 XSS）。
 */
document.addEventListener('click', (e) => {
    const el = e.target.closest('[data-action]');
    if (!el) return;
    const action = el.dataset.action;

    if (action === 'quick-scan') {
        quickScanDisk(el.dataset.path);
    } else if (action === 'view-scan') {
        viewScan(Number(el.dataset.scanId));
    } else if (action === 'drill') {
        const scanId = Number(el.dataset.scanId);
        const path = el.dataset.path;
        if (scanId && path) loadTree(scanId, path);
    } else if (action === 'open-location') {
        openFileLocation(el.dataset.path);
    }
});

document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
});
