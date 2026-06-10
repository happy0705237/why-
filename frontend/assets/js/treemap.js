/**
 * TreeMap 可视化组件
 */

// 文件类型颜色
const TYPE_COLORS = {
    video: '#EF4444',
    image: '#F59E0B',
    audio: '#8B5CF6',
    document: '#3B82F6',
    archive: '#10B981',
    code: '#06B6D4',
    executable: '#EC4899',
    directory: '#6366F1',
    other: '#6B7280',
};

// 扩展名 -> 类型映射
const EXT_TYPE = {
    mp4:'video',avi:'video',mkv:'video',mov:'video',wmv:'video',flv:'video',webm:'video',
    jpg:'image',jpeg:'image',png:'image',gif:'image',bmp:'image',svg:'image',webp:'image',ico:'image',heic:'image',
    mp3:'audio',wav:'audio',flac:'audio',aac:'audio',ogg:'audio',wma:'audio',m4a:'audio',
    pdf:'document',doc:'document',docx:'document',xls:'document',xlsx:'document',ppt:'document',pptx:'document',
    txt:'document',rtf:'document',csv:'document',md:'document',
    zip:'archive',rar:'archive','7z':'archive',tar:'archive',gz:'archive',iso:'archive',
    py:'code',js:'code',ts:'code',html:'code',css:'code',java:'code',c:'code',cpp:'code',
    go:'code',rs:'code',rb:'code',php:'code',json:'code',xml:'code',yaml:'code',yml:'code',sql:'code',
    exe:'executable',msi:'executable',dll:'executable',
};

function getFileColor(ext, isDir) {
    if (isDir) return TYPE_COLORS.directory;
    if (!ext) return TYPE_COLORS.other;
    const type = EXT_TYPE[ext.toLowerCase()];
    return TYPE_COLORS[type] || TYPE_COLORS.other;
}

function getFileTypeLabel(ext, isDir) {
    if (isDir) return '目录';
    if (!ext) return '文件';
    const type = EXT_TYPE[ext.toLowerCase()];
    const labels = {
        video: '视频', image: '图片', audio: '音频', document: '文档',
        archive: '压缩包', code: '代码', executable: '程序',
    };
    return labels[type] || '文件';
}

let treemapInstance = null;

function initTreemap(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return null;
    if (treemapInstance) {
        treemapInstance.dispose();
    }
    treemapInstance = echarts.init(container, null, { renderer: 'canvas' });

    // 响应式
    window.addEventListener('resize', () => {
        if (treemapInstance) treemapInstance.resize();
    });

    return treemapInstance;
}

function renderTreemap(containerId, items, currentPath, onClickItem) {
    const chart = initTreemap(containerId);
    if (!chart || !items || items.length === 0) {
        if (chart) {
            chart.setOption({
                graphic: {
                    type: 'text',
                    left: 'center',
                    top: 'center',
                    style: { text: '暂无数据', fontSize: 16, fill: '#94A3B8' }
                }
            });
        }
        return;
    }

    // 过滤掉 "其他" 项用于 treemap
    const dataItems = items.filter(i => !i.is_others);
    const othersItem = items.find(i => i.is_others);

    // 构建 treemap 数据
    const data = dataItems.map(item => {
        const isDir = !!item.is_dir;
        const ext = item.extension || '';
        const color = getFileColor(ext, isDir);

        return {
            name: item.name,
            value: item.size || 0,
            path: item.path,
            isDir: isDir,
            ext: ext,
            sizePercent: item.size_percent || 0,
            fileCount: item.file_count,
            dirCount: item.dir_count,
            itemStyle: {
                color: color,
                borderColor: '#0F172A',
                borderWidth: 2,
                gapWidth: 2,
            },
        };
    });

    // 添加 "其他" 项
    if (othersItem && othersItem.size > 0) {
        data.push({
            name: othersItem.name,
            value: othersItem.size,
            path: '__others__',
            isDir: false,
            sizePercent: othersItem.size_percent || 0,
            itemStyle: {
                color: '#374151',
                borderColor: '#0F172A',
                borderWidth: 2,
                gapWidth: 2,
            },
        });
    }

    const option = {
        tooltip: {
            formatter: function (info) {
                const d = info.data;
                if (!d) return '';
                const size = formatSize(d.value);
                const pct = d.sizePercent ? d.sizePercent.toFixed(1) + '%' : '';
                const type = d.isDir ? '📁 目录' : (d.ext ? `📄 .${d.ext}` : '📄 文件');
                let html = `<div style="font-weight:600;margin-bottom:4px">${d.name}</div>`;
                html += `<div>${type}</div>`;
                html += `<div>大小: ${size}</div>`;
                if (pct) html += `<div>占比: ${pct}</div>`;
                if (d.isDir && d.fileCount !== undefined) {
                    html += `<div>文件: ${d.fileCount.toLocaleString()}</div>`;
                }
                return html;
            },
            backgroundColor: '#1E293B',
            borderColor: '#334155',
            textStyle: { color: '#F8FAFC', fontSize: 13 },
            padding: [10, 14],
        },
        series: [{
            type: 'treemap',
            data: data,
            width: '100%',
            height: '100%',
            roam: false,
            nodeClick: false,  // 我们自己处理点击
            breadcrumb: { show: false },
            label: {
                show: true,
                formatter: function (params) {
                    const d = params.data;
                    if (!d) return '';
                    const size = formatSize(d.value);
                    const name = d.name.length > 20 ? d.name.substring(0, 18) + '...' : d.name;
                    return `{name|${name}}\n{size|${size}}`;
                },
                rich: {
                    name: {
                        fontSize: 13,
                        fontWeight: 600,
                        color: '#F8FAFC',
                        lineHeight: 20,
                        textShadowColor: 'rgba(0,0,0,0.5)',
                        textShadowBlur: 3,
                    },
                    size: {
                        fontSize: 11,
                        color: 'rgba(248,250,252,0.7)',
                        lineHeight: 16,
                    },
                },
                padding: [4, 6],
            },
            upperLabel: { show: false },
            itemStyle: {
                borderColor: '#0F172A',
                borderWidth: 2,
                gapWidth: 2,
            },
            levels: [{
                itemStyle: {
                    borderColor: '#0F172A',
                    borderWidth: 3,
                    gapWidth: 3,
                },
            }],
        }],
    };

    chart.setOption(option);

    // 点击事件
    chart.off('click');
    chart.on('click', function (params) {
        const d = params.data;
        if (d && d.isDir && d.path && d.path !== '__others__') {
            onClickItem(d.path);
        }
    });

    return chart;
}

let pieInstance = null;

function renderPieChart(containerId, categories) {
    const container = document.getElementById(containerId);
    if (!container) return;

    if (pieInstance) pieInstance.dispose();
    pieInstance = echarts.init(container);

    const data = categories.slice(0, 15).map(c => {
        const type = EXT_TYPE[c.extension] || 'other';
        return {
            name: c.extension === '(无扩展名)' ? '其他' : `.${c.extension}`,
            value: c.total_size,
            itemStyle: { color: TYPE_COLORS[type] || TYPE_COLORS.other },
        };
    });

    const option = {
        tooltip: {
            formatter: function (info) {
                return `${info.name}<br/>大小: ${formatSize(info.value)}<br/>占比: ${info.percent.toFixed(1)}%`;
            },
            backgroundColor: '#1E293B',
            borderColor: '#334155',
            textStyle: { color: '#F8FAFC' },
        },
        series: [{
            type: 'pie',
            radius: ['40%', '70%'],
            center: ['50%', '50%'],
            data: data,
            label: {
                color: '#94A3B8',
                fontSize: 12,
                formatter: '{b}: {d}%',
            },
            labelLine: {
                lineStyle: { color: '#334155' },
            },
            emphasis: {
                itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' },
            },
        }],
    };

    pieInstance.setOption(option);
    window.addEventListener('resize', () => { if (pieInstance) pieInstance.resize(); });
}
