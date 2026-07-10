const state = {
    columns: [],
    previewRows: [],
    pdfId: null,
    pageCount: 0,
    currentPage: 1,
    placedFields: [],
    templateId: null,
    batchId: null,
    polling: false,
    suggestions: [],
    templates: [],
    workflowMode: 'single',
    workflowId: null,
    workflowExcelId: null,
    workflowRoutingColumn: null,
};

function api(method, url, data) {
    const opts = { method, headers: {} };
    if (data instanceof FormData) {
        opts.body = data;
    } else if (data) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(data);
    }
    return fetch(url, opts).then(async r => {
        if (!r.ok) {
            const err = await r.json().catch(() => ({ detail: r.statusText }));
            throw new Error(err.detail || `HTTP ${r.status}`);
        }
        const ct = r.headers.get('content-type') || '';
        if (ct.includes('application/json')) return r.json();
        return r;
    });
}

function pointToPixel(pt) { return pt * 150 / 72; }

function showMsg(id, msg, type) {
    const el = document.getElementById(id);
    if (!el) return;
    if (!msg) { el.style.display = 'none'; el.textContent = ''; return; }
    el.textContent = msg;
    el.className = 'msg-box ' + (type === 'error' ? 'status-error' : type === 'warning' ? 'warning-box' : 'status-ok');
    el.style.display = 'block';
}

// ======== STEP NAVIGATION ========

function switchStep(n) {
    document.querySelectorAll('.step-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('#step-nav .step').forEach(el => el.classList.remove('active'));
    document.getElementById('step-' + n).classList.add('active');
    document.querySelector('#step-nav .step[data-step="' + n + '"]').classList.add('active');
    if (n === 2) enterStep2();
    if (n === 3) enterStep3();
}

document.querySelectorAll('#step-nav .step').forEach(btn => {
    btn.addEventListener('click', () => {
        const n = parseInt(btn.dataset.step);
        if (n === 1) { switchStep(1); return; }
        if (n === 2 && state.columns.length && state.pdfId) { switchStep(2); return; }
        if (n === 3) { switchStep(3); }
    });
});

// ======== STEP 1: UPLOAD ========

document.getElementById('excel-input').addEventListener('change', async e => {
    const file = e.target.files[0];
    if (!file) return;
    showMsg('excel-status', 'Uploading...', 'ok');
    const fd = new FormData();
    fd.append('file', file);
    try {
        const data = await api('POST', '/upload/excel', fd);
        state.columns = data.columns;
        state.previewRows = data.preview_rows;
        document.querySelector('.upload-card:first-child').classList.add('file-loaded');
        showMsg('excel-status', 'Loaded ' + data.columns.length + ' columns', 'ok');
        document.getElementById('excel-preview').style.display = 'block';
        renderColumnTags(data.columns);
        renderPreviewTable(data.columns, data.preview_rows);
        checkStep2Ready();
    } catch (err) {
        showMsg('excel-status', err.message, 'error');
    }
});

document.getElementById('pdf-input').addEventListener('change', async e => {
    const file = e.target.files[0];
    if (!file) return;
    showMsg('pdf-status', 'Uploading...', 'ok');
    const fd = new FormData();
    fd.append('file', file);
    try {
        const data = await api('POST', '/upload/pdf', fd);
        state.pdfId = data.pdf_id;
        state.pageCount = data.page_count;
        document.querySelector('.upload-card:last-child').classList.add('file-loaded');
        showMsg('pdf-status', 'Loaded: ' + data.filename + ' (' + data.page_count + ' page' + (data.page_count > 1 ? 's' : '') + ')', 'ok');
        document.getElementById('pdf-details').textContent = 'Pages: ' + data.page_count + ' | Filename: ' + data.filename;
        document.getElementById('pdf-info').style.display = 'block';
        checkStep2Ready();
    } catch (err) {
        showMsg('pdf-status', err.message, 'error');
    }
});

function renderColumnTags(columns) {
    const container = document.getElementById('column-list-upload');
    container.innerHTML = '';
    columns.forEach(col => {
        const tag = document.createElement('span');
        tag.className = 'tag';
        tag.textContent = col;
        container.appendChild(tag);
    });
}

function renderPreviewTable(columns, rows) {
    const wrapper = document.getElementById('preview-table-wrapper');
    if (!rows || rows.length === 0) {
        wrapper.innerHTML = '<p class="hint">No data rows found.</p>';
        return;
    }
    let html = '<table><thead><tr>';
    columns.forEach(c => { html += '<th>' + esc(c) + '</th>'; });
    html += '</tr></thead><tbody>';
    rows.forEach(row => {
        html += '<tr>';
        columns.forEach(c => { html += '<td>' + esc(row[c] || '') + '</td>'; });
        html += '</tr>';
    });
    html += '</tbody></table>';
    wrapper.innerHTML = html;
}

function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function checkStep2Ready() {
    document.getElementById('to-position-btn').disabled = !(state.columns.length && state.pdfId);
}

document.getElementById('to-position-btn').addEventListener('click', () => {
    state.currentPage = 1;
    state.placedFields = [];
    state.templateId = null;
    switchStep(2);
});

// ======== STEP 2: POSITION ========

function enterStep2() {
    const container = document.getElementById('available-columns');
    container.innerHTML = '';
    state.columns.forEach(col => {
        const tag = document.createElement('span');
        tag.className = 'tag';
        tag.draggable = true;
        tag.textContent = col;
        tag.dataset.column = col;
        tag.addEventListener('dragstart', e => {
            e.dataTransfer.setData('text/plain', col);
        });
        container.appendChild(tag);
    });
    document.getElementById('template-name-input').value = '';
    state.suggestions = [];
    renderPlacedFields();
    updateSaveButton();
    loadPreview(state.currentPage);
    fetchSuggestions();
}

function loadPreview(page) {
    const img = document.getElementById('pdf-preview');
    if (!state.pdfId) return;
    img.src = '/preview/' + state.pdfId + '/' + page + '?t=' + Date.now();
    document.getElementById('page-indicator').textContent = 'Page ' + page + ' / ' + state.pageCount;
}

document.getElementById('prev-page').addEventListener('click', () => {
    if (state.currentPage > 1) {
        state.currentPage--;
        loadPreview(state.currentPage);
        setTimeout(renderMarkers, 100);
        fetchSuggestions();
    }
});

document.getElementById('next-page').addEventListener('click', () => {
    if (state.currentPage < state.pageCount) {
        state.currentPage++;
        loadPreview(state.currentPage);
        setTimeout(renderMarkers, 100);
        fetchSuggestions();
    }
});

// Drag & drop
const previewWrapper = document.getElementById('preview-wrapper');
const previewImg = document.getElementById('pdf-preview');

previewWrapper.addEventListener('dragover', e => { e.preventDefault(); previewWrapper.classList.add('drag-over'); });
previewWrapper.addEventListener('dragleave', () => { previewWrapper.classList.remove('drag-over'); });
previewWrapper.addEventListener('drop', e => {
    e.preventDefault();
    previewWrapper.classList.remove('drag-over');
    const column = e.dataTransfer.getData('text/plain');
    if (!column) return;
    if (!previewImg.naturalWidth) return;
    const rect = previewImg.getBoundingClientRect();
    const scaleX = previewImg.naturalWidth / rect.width;
    const scaleY = previewImg.naturalHeight / rect.height;
    const pixelX = (e.clientX - rect.left) * scaleX;
    const pixelY = (e.clientY - rect.top) * scaleY;
    const existing = state.placedFields.findIndex(f => f.column === column && f.page === state.currentPage);
    if (existing >= 0) {
        state.placedFields[existing].x = pixelX;
        state.placedFields[existing].y = pixelY;
    } else {
        state.placedFields.push({ column: column, page: state.currentPage, x: pixelX, y: pixelY, font_size: 11, max_width: null });
    }
    renderMarkers();
    renderPlacedFields();
    updateSaveButton();
});

function renderMarkers() {
    const wrapper = document.getElementById('preview-wrapper');
    wrapper.querySelectorAll('.marker, .marker-suggestion').forEach(el => el.remove());
    const img = previewImg;
    if (!img.naturalWidth) return;
    const scaleX = img.clientWidth / img.naturalWidth;
    const scaleY = img.clientHeight / img.naturalHeight;
    const pageFields = state.placedFields.filter(f => f.page === state.currentPage);
    pageFields.forEach(f => {
        const marker = document.createElement('div');
        marker.className = 'marker';
        marker.textContent = f.column;
        marker.style.left = (f.x * scaleX) + 'px';
        marker.style.top = (f.y * scaleY) + 'px';
        marker.addEventListener('click', () => removeField(f.column, f.page));
        wrapper.appendChild(marker);
    });
    const placedCols = new Set(state.placedFields.map(f => f.column));
    const unchecked = new Set();
    document.querySelectorAll('.sug-cb:not(:checked)').forEach(cb => {
        unchecked.add(cb.dataset.col);
    });
    state.suggestions.forEach(s => {
        if (placedCols.has(s.column)) return;
        if (unchecked.has(s.column)) return;
        const px = pointToPixel(s.x);
        const py = pointToPixel(s.y);
        const marker = document.createElement('div');
        marker.className = 'marker-suggestion';
        marker.textContent = s.column;
        marker.style.left = (px * scaleX) + 'px';
        marker.style.top = (py * scaleY) + 'px';
        wrapper.appendChild(marker);
    });
}

previewImg.addEventListener('load', renderMarkers);

function renderPlacedFields() {
    const list = document.getElementById('placed-fields-list');
    if (state.placedFields.length === 0) {
        list.innerHTML = '<p class="hint">No fields placed yet.</p>';
        return;
    }
    list.innerHTML = '';
    state.placedFields.forEach(f => {
        const div = document.createElement('div');
        div.className = 'placed-field';
        const sz = f.font_size || 11;
        const mw = f.max_width || '';
        div.innerHTML =
            '<span class="field-name">' + esc(f.column) + '</span>' +
            '<span style="font-size:10px;color:#888;">p' + f.page + '</span>' +
            '<label>Sz</label><input type="number" class="f-size" value="' + sz + '" min="6" max="36" data-col="' + esc(f.column) + '" data-p="' + f.page + '">' +
            '<label>W</label><input type="text" class="f-width" value="' + mw + '" placeholder="auto" data-col="' + esc(f.column) + '" data-p="' + f.page + '">' +
            '<button class="btn-danger btn-small" data-col="' + esc(f.column) + '" data-p="' + f.page + '">\u2715</button>';
        div.querySelector('.f-size').addEventListener('change', e => {
            let val = parseInt(e.target.value) || 11;
            val = Math.max(6, Math.min(36, val));
            e.target.value = val;
            const f2 = state.placedFields.find(x => x.column === e.target.dataset.col && x.page === parseInt(e.target.dataset.p));
            if (f2) f2.font_size = val;
        });
        div.querySelector('.f-width').addEventListener('change', e => {
            const val = e.target.value.trim();
            const f2 = state.placedFields.find(x => x.column === e.target.dataset.col && x.page === parseInt(e.target.dataset.p));
            if (f2) f2.max_width = val ? parseFloat(val) : null;
        });
        div.querySelector('.btn-danger').addEventListener('click', e => {
            removeField(e.target.dataset.col, parseInt(e.target.dataset.p));
        });
        list.appendChild(div);
    });
}

function removeField(column, page) {
    state.placedFields = state.placedFields.filter(f => !(f.column === column && f.page === page));
    renderMarkers();
    renderPlacedFields();
    updateSaveButton();
}

function updateSaveButton() {
    const btn = document.getElementById('save-template-btn');
    btn.disabled = state.placedFields.length === 0;
}

// ======== AUTO-POSITION SUGGESTIONS ========

async function fetchSuggestions() {
    if (!state.pdfId || !state.columns.length) return;
    const el = document.getElementById('suggestion-status');
    el.style.display = 'none';
    document.getElementById('apply-suggestions-btn').disabled = true;
    const params = state.columns.map(c => 'columns=' + encodeURIComponent(c)).join('&');
    const url = '/preview/suggest/' + state.pdfId + '/' + state.currentPage + '?' + params;
    try {
        const data = await api('GET', url);
        state.suggestions = data.suggestions || [];
        if (data.hint) {
            showMsg('suggestion-status', data.hint, 'warning');
        }
        renderSuggestions();
    } catch (err) {
        state.suggestions = [];
        renderSuggestions();
        showMsg('suggestion-status', err.message, 'error');
    }
}

function renderSuggestions() {
    const list = document.getElementById('suggestion-list');
    const placedCols = new Set(state.placedFields.map(f => f.column));
    const available = state.suggestions.filter(s => !placedCols.has(s.column));
    if (available.length === 0) {
        list.innerHTML = '<p class="hint">No suggestions for this page.</p>';
        document.getElementById('apply-suggestions-btn').disabled = true;
        renderMarkers();
        return;
    }
    let html = '';
    let allChecked = true;
    available.forEach(s => {
        const badgeClass = s.confidence >= 0.9 ? 'conf-high' : s.confidence >= 0.7 ? 'conf-mid' : 'conf-low';
        const pct = Math.round(s.confidence * 100);
        html += '<div class="suggestion-item">' +
            '<input type="checkbox" class="sug-cb" data-col="' + esc(s.column) + '" checked>' +
            '<label>' + esc(s.column) + '</label>' +
            '<span class="conf-badge ' + badgeClass + '">' + pct + '%</span>' +
            '</div>';
    });
    list.innerHTML = html;
    document.getElementById('apply-suggestions-btn').disabled = false;
    list.querySelectorAll('.sug-cb').forEach(cb => {
        cb.addEventListener('change', renderMarkers);
    });
    renderMarkers();
}

function applySuggestions() {
    const checked = new Set();
    document.querySelectorAll('.sug-cb:checked').forEach(cb => {
        checked.add(cb.dataset.col);
    });
    if (checked.size === 0) return;
    const placedCols = new Set(state.placedFields.map(f => f.column));
    state.suggestions.forEach(s => {
        if (!checked.has(s.column)) return;
        if (placedCols.has(s.column)) return;
        state.placedFields.push({
            column: s.column,
            page: state.currentPage,
            x: pointToPixel(s.x),
            y: pointToPixel(s.y),
            font_size: 11,
            max_width: null,
        });
        placedCols.add(s.column);
    });
    state.suggestions = [];
    renderSuggestions();
    renderPlacedFields();
    updateSaveButton();
}

document.getElementById('apply-suggestions-btn').addEventListener('click', applySuggestions);

document.getElementById('save-template-btn').addEventListener('click', async () => {
    const name = document.getElementById('template-name-input').value.trim();
    if (!name) {
        showMsg('template-save-status', 'Please enter a template name.', 'error');
        return;
    }
    const body = {
        name: name,
        pdf_file: state.pdfId + '.pdf',
        fields: state.placedFields.map(f => ({
            column: f.column,
            page: f.page,
            x: Math.round(f.x),
            y: Math.round(f.y),
            font_size: f.font_size,
            max_width: f.max_width,
        })),
    };
    try {
        const data = await api('POST', '/template', body);
        state.templateId = data.id;
        let html = 'Saved: "' + data.name + '" (' + data.field_count + ' fields)';
        showMsg('template-save-status', html, 'ok');
        if (data.warnings && data.warnings.length) {
            const el = document.getElementById('template-save-status');
            el.innerHTML += '<div class="msg-box warning-box" style="margin-top:4px">' + data.warnings.map(esc).join('<br>') + '</div>';
        }
        switchStep(3);
    } catch (err) {
        showMsg('template-save-status', err.message, 'error');
    }
});

// ======== STEP 3: GENERATE ========

document.getElementById('tab-btn-single').addEventListener('click', () => switchStep3Tab('single'));
document.getElementById('tab-btn-workflow').addEventListener('click', () => switchStep3Tab('workflow'));

function switchStep3Tab(tab) {
    state.workflowMode = tab;
    document.querySelectorAll('.step3-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
    document.getElementById('tab-single').classList.toggle('active', tab === 'single');
    document.getElementById('tab-workflow').classList.toggle('active', tab === 'workflow');
    document.getElementById('fill-progress').style.display = 'none';
    document.getElementById('fill-done').style.display = 'none';
    document.getElementById('fill-error').style.display = 'none';
}

async function enterStep3() {
    await loadTemplates();
    await loadWorkflows();
    document.getElementById('fill-excel-input').value = '';
    document.getElementById('fill-excel-status').style.display = 'none';
    document.getElementById('fill-warnings').style.display = 'none';
    document.getElementById('fill-progress').style.display = 'none';
    document.getElementById('fill-done').style.display = 'none';
    document.getElementById('fill-error').style.display = 'none';
    document.getElementById('start-fill-btn').disabled = true;
    document.getElementById('start-workflow-fill-btn').disabled = true;
    state.workflowId = null;
    state.workflowExcelId = null;
    state.workflowRoutingColumn = null;
    resetWorkflowBuilder();
    if (state.workflowMode === 'single') {
        switchStep3Tab('single');
    }
    if (state.templateId) {
        selectTemplate(state.templateId);
        checkFillReady();
    }
}

async function loadTemplates() {
    try {
        const list = await api('GET', '/template/list');
        state.templates = list;
        renderTemplateGrid(list);
    } catch (err) {
        console.error('Failed to load templates:', err);
        document.getElementById('template-grid').innerHTML = '<p class="hint">Failed to load templates.</p>';
    }
}

function renderTemplateGrid(list) {
    const grid = document.getElementById('template-grid');
    if (!list.length) {
        grid.innerHTML = '<p class="hint">No saved templates yet.</p>';
        return;
    }
    let html = '';
    list.forEach(t => {
        const isSelected = state.templateId === t.id;
        html += '<div class="template-card' + (isSelected ? ' selected' : '') + '"' +
            ' role="button" tabindex="0" data-id="' + t.id + '">' +
            '<img class="template-thumb" src="/template/' + t.id + '/thumbnail" loading="lazy" onerror="this.style.display=\'none\'">' +
            '<div class="template-card-name" title="' + esc(t.name) + '">' + esc(t.name) + '</div>' +
            '<div class="template-card-meta">' + t.field_count + ' fields</div>' +
            '<div class="template-card-actions">' +
            '<button class="btn-small" data-action="rename" data-id="' + t.id + '">Rename</button>' +
            '<button class="btn-small" data-action="duplicate" data-id="' + t.id + '">Copy</button>' +
            '<button class="btn-small btn-danger" data-action="delete" data-id="' + t.id + '">Del</button>' +
            '</div></div>';
    });
    grid.innerHTML = html;

    grid.querySelectorAll('.template-card').forEach(card => {
        card.addEventListener('click', e => {
            if (e.target.closest('.template-card-actions')) return;
            selectTemplate(card.dataset.id);
        });
        card.addEventListener('keydown', e => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                selectTemplate(card.dataset.id);
            }
        });
    });

    grid.querySelectorAll('[data-action="rename"]').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            renameTemplate(btn.dataset.id);
        });
    });
    grid.querySelectorAll('[data-action="duplicate"]').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            duplicateTemplate(btn.dataset.id);
        });
    });
    grid.querySelectorAll('[data-action="delete"]').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            deleteTemplate(btn.dataset.id);
        });
    });
}

function selectTemplate(id) {
    state.templateId = id;
    document.querySelectorAll('.template-card').forEach(c => {
        c.classList.toggle('selected', c.dataset.id === id);
    });
    checkFillReady();
}

async function renameTemplate(id) {
    const newName = window.prompt('New template name:');
    if (!newName || !newName.trim()) return;
    try {
        await api('PUT', '/template/' + id, { name: newName.trim() });
        loadTemplates();
    } catch (err) {
        alert('Rename failed: ' + err.message);
    }
}

async function duplicateTemplate(id) {
    try {
        await api('POST', '/template/' + id + '/duplicate', {});
        loadTemplates();
    } catch (err) {
        alert('Duplicate failed: ' + err.message);
    }
}

async function deleteTemplate(id) {
    if (!window.confirm('Delete this template?')) return;
    try {
        await api('DELETE', '/template/' + id);
        if (state.templateId === id) {
            state.templateId = null;
            checkFillReady();
        }
        loadTemplates();
    } catch (err) {
        alert('Delete failed: ' + err.message);
    }
}

document.getElementById('fill-excel-input').addEventListener('change', e => {
    checkFillReady();
    if (e.target.files[0]) {
        showMsg('fill-excel-status', 'Selected: ' + e.target.files[0].name, 'ok');
    } else {
        document.getElementById('fill-excel-status').style.display = 'none';
    }
});

function checkFillReady() {
    document.getElementById('start-fill-btn').disabled = !(state.templateId && document.getElementById('fill-excel-input').files.length > 0);
}

document.getElementById('start-fill-btn').addEventListener('click', async () => {
    const file = document.getElementById('fill-excel-input').files[0];
    if (!file || !state.templateId) return;
    document.getElementById('fill-done').style.display = 'none';
    document.getElementById('fill-error').style.display = 'none';
    document.getElementById('fill-warnings').style.display = 'none';
    const fd = new FormData();
    fd.append('file', file);
    try {
        const data = await api('POST', '/fill?template_id=' + state.templateId, fd);
        if (data.warnings && data.warnings.length) {
            const w = document.getElementById('fill-warnings');
            w.innerHTML = '<strong>Warnings:</strong><br>' + data.warnings.join('<br>');
            w.style.display = 'block';
        }
        state.batchId = data.batch_id;
        document.getElementById('fill-progress').style.display = 'block';
        document.getElementById('start-fill-btn').disabled = true;
        startPolling(data.batch_id);
    } catch (err) {
        showMsg('fill-error', err.message, 'error');
    }
});

function startPolling(batchId) {
    if (state.polling) return;
    state.polling = true;
    let attempts = 0;
    const MAX = 300;
    function poll() {
        if (attempts >= MAX) {
            state.polling = false;
            showMsg('fill-error', 'Timeout — generation took too long.', 'error');
            document.getElementById('start-fill-btn').disabled = false;
            return;
        }
        attempts++;
        api('GET', '/fill/' + batchId + '/status').then(data => {
            const bar = document.getElementById('progress-fill');
            const text = document.getElementById('progress-text');
            if (data.total > 0) {
                bar.style.width = (data.completed / data.total * 100) + '%';
            }
            text.textContent = data.completed + ' / ' + data.total;
            if (data.status === 'completed') {
                state.polling = false;
                document.getElementById('fill-progress').style.display = 'block';
                document.getElementById('fill-done').style.display = 'block';
                document.getElementById('download-link').href = '/fill/' + batchId + '/download';
                document.getElementById('start-fill-btn').disabled = false;
                document.getElementById('start-workflow-fill-btn').disabled = false;
                if (data.warnings && data.warnings.length) {
                    const w = document.getElementById('workflow-fill-warnings');
                    w.innerHTML = '<strong>Batch warnings:</strong><br>' + data.warnings.join('<br>');
                    w.style.display = 'block';
                }
            } else if (data.status === 'error') {
                state.polling = false;
                showMsg('fill-error', data.error || 'An error occurred during generation.', 'error');
                document.getElementById('start-fill-btn').disabled = false;
            } else {
                setTimeout(poll, 1000);
            }
        }).catch(err => {
            state.polling = false;
            showMsg('fill-error', err.message, 'error');
            document.getElementById('start-fill-btn').disabled = false;
        });
    }
    setTimeout(poll, 500);
}

// ======== WORKFLOW ========

async function loadWorkflows() {
    try {
        const list = await api('GET', '/workflow/list');
        renderWorkflowGrid(list);
    } catch (err) {
        console.error('Failed to load workflows:', err);
        document.getElementById('workflow-grid').innerHTML = '<p class="hint">Failed to load workflows.</p>';
    }
}

function renderWorkflowGrid(list) {
    const grid = document.getElementById('workflow-grid');
    if (!list.length) {
        grid.innerHTML = '<p class="hint">No saved workflows yet.</p>';
        return;
    }
    let html = '';
    list.forEach(w => {
        const isSelected = state.workflowId === w.id;
        html += '<div class="template-card' + (isSelected ? ' selected' : '') + '"' +
            ' role="button" tabindex="0" data-id="' + w.id + '">' +
            '<div class="workflow-card-icon">&#9878;</div>' +
            '<div class="template-card-name" title="' + esc(w.name) + '">' + esc(w.name) + '</div>' +
            '<div class="template-card-meta">' + w.route_count + ' routes &middot; ' + esc(w.routing_column) + '</div>' +
            '<div class="template-card-actions">' +
            '<button class="btn-small" data-action="rename" data-id="' + w.id + '">Rename</button>' +
            '<button class="btn-small btn-danger" data-action="delete" data-id="' + w.id + '">Del</button>' +
            '</div></div>';
    });
    grid.innerHTML = html;

    grid.querySelectorAll('.template-card').forEach(card => {
        card.addEventListener('click', e => {
            if (e.target.closest('.template-card-actions')) return;
            selectWorkflow(card.dataset.id);
        });
        card.addEventListener('keydown', e => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                selectWorkflow(card.dataset.id);
            }
        });
    });

    grid.querySelectorAll('[data-action="rename"]').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            renameWorkflow(btn.dataset.id);
        });
    });
    grid.querySelectorAll('[data-action="delete"]').forEach(btn => {
        btn.addEventListener('click', e => {
            e.stopPropagation();
            deleteWorkflow(btn.dataset.id);
        });
    });
}

function selectWorkflow(id) {
    state.workflowId = id;
    document.querySelectorAll('#workflow-grid .template-card').forEach(c => {
        c.classList.toggle('selected', c.dataset.id === id);
    });
    checkWorkflowFillReady();
}

async function renameWorkflow(id) {
    const newName = window.prompt('New workflow name:');
    if (!newName || !newName.trim()) return;
    try {
        await api('PUT', '/workflow/' + id, { name: newName.trim() });
        loadWorkflows();
    } catch (err) {
        alert('Rename failed: ' + err.message);
    }
}

async function deleteWorkflow(id) {
    if (!window.confirm('Delete this workflow?')) return;
    try {
        await api('DELETE', '/workflow/' + id);
        if (state.workflowId === id) {
            state.workflowId = null;
            checkWorkflowFillReady();
        }
        loadWorkflows();
    } catch (err) {
        alert('Delete failed: ' + err.message);
    }
}

document.getElementById('toggle-create-workflow-btn').addEventListener('click', () => {
    const panel = document.getElementById('create-workflow-panel');
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
});

function resetWorkflowBuilder() {
    document.getElementById('create-workflow-panel').style.display = 'none';
    document.getElementById('workflow-name-input').value = '';
    document.getElementById('workflow-excel-input').value = '';
    document.getElementById('workflow-routing-preview').style.display = 'none';
    document.getElementById('routing-column-select').innerHTML = '<option value="">-- Pick a column --</option>';
    document.getElementById('routing-values-list').innerHTML = '';
    document.getElementById('save-workflow-btn').disabled = true;
    showMsg('workflow-save-status', null, 'ok');
}

document.getElementById('workflow-excel-input').addEventListener('change', async e => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
        const data = await api('POST', '/upload/excel', fd);
        state.workflowExcelId = data.excel_id;
        const sel = document.getElementById('routing-column-select');
        sel.innerHTML = '<option value="">-- Pick a column --</option>';
        data.columns.forEach(col => {
            const opt = document.createElement('option');
            opt.value = col;
            opt.textContent = col;
            sel.appendChild(opt);
        });
        document.getElementById('workflow-routing-preview').style.display = 'block';
        document.getElementById('routing-values-list').innerHTML = '<p class="hint">Select a routing column above.</p>';
        document.getElementById('save-workflow-btn').disabled = true;
    } catch (err) {
        alert('Excel upload failed: ' + err.message);
    }
});

document.getElementById('routing-column-select').addEventListener('change', async () => {
    const column = document.getElementById('routing-column-select').value;
    if (!column || !state.workflowExcelId) {
        document.getElementById('save-workflow-btn').disabled = true;
        return;
    }
    state.workflowRoutingColumn = column;
    try {
        const data = await api('GET', '/upload/' + state.workflowExcelId + '/unique/' + encodeURIComponent(column));
        renderRoutingValues(data.values);
        document.getElementById('save-workflow-btn').disabled = data.values.length === 0;
    } catch (err) {
        alert('Failed to load routing values: ' + err.message);
        document.getElementById('save-workflow-btn').disabled = true;
    }
});

function renderRoutingValues(values) {
    const list = document.getElementById('routing-values-list');
    if (!values.length) {
        list.innerHTML = '<p class="hint">Column has no values in data rows.</p>';
        return;
    }
    let html = '<table class="route-mapping-table"><thead><tr><th>Value</th><th>Template</th></tr></thead><tbody>';
    values.forEach(v => {
        html += '<tr><td>' + esc(v) + '</td><td><select class="route-template-select">' +
            '<option value="">-- Pick --</option>';
        state.templates.forEach(t => {
            html += '<option value="' + t.id + '">' + esc(t.name) + '</option>';
        });
        html += '</select></td></tr>';
    });
    html += '</tbody></table>';
    list.innerHTML = html;
}

document.getElementById('save-workflow-btn').addEventListener('click', async () => {
    const name = document.getElementById('workflow-name-input').value.trim();
    if (!name) {
        showMsg('workflow-save-status', 'Please enter a workflow name.', 'error');
        return;
    }
    const routes = [];
    document.querySelectorAll('.route-template-select').forEach(sel => {
        if (sel.value) {
            const row = sel.closest('tr');
            const valueTd = row.querySelector('td');
            routes.push({ value: valueTd.textContent, template_id: sel.value });
        }
    });
    if (!routes.length) {
        showMsg('workflow-save-status', 'Please map at least one value to a template.', 'error');
        return;
    }
    try {
        const data = await api('POST', '/workflow', {
            name: name,
            routing_column: state.workflowRoutingColumn,
            routes: routes,
        });
        showMsg('workflow-save-status', 'Workflow "' + data.name + '" saved (' + data.route_count + ' routes)', 'ok');
        resetWorkflowBuilder();
        loadWorkflows();
    } catch (err) {
        showMsg('workflow-save-status', err.message, 'error');
    }
});

document.getElementById('workflow-excel-data-input').addEventListener('change', e => {
    checkWorkflowFillReady();
    if (e.target.files[0]) {
        showMsg('workflow-fill-excel-status', 'Selected: ' + e.target.files[0].name, 'ok');
    } else {
        document.getElementById('workflow-fill-excel-status').style.display = 'none';
    }
});

function checkWorkflowFillReady() {
    document.getElementById('start-workflow-fill-btn').disabled = !(
        state.workflowId && document.getElementById('workflow-excel-data-input').files.length > 0
    );
}

document.getElementById('start-workflow-fill-btn').addEventListener('click', async () => {
    const file = document.getElementById('workflow-excel-data-input').files[0];
    if (!file || !state.workflowId) return;
    document.getElementById('fill-done').style.display = 'none';
    document.getElementById('fill-error').style.display = 'none';
    document.getElementById('workflow-fill-warnings').style.display = 'none';
    const fd = new FormData();
    fd.append('file', file);
    try {
        const data = await api('POST', '/fill/workflow?workflow_id=' + state.workflowId, fd);
        if (data.warnings && data.warnings.length) {
            const w = document.getElementById('workflow-fill-warnings');
            w.innerHTML = '<strong>Warnings:</strong><br>' + data.warnings.join('<br>');
            w.style.display = 'block';
        }
        state.batchId = data.batch_id;
        document.getElementById('fill-progress').style.display = 'block';
        document.getElementById('start-workflow-fill-btn').disabled = true;
        startPolling(data.batch_id);
    } catch (err) {
        showMsg('fill-error', err.message, 'error');
    }
});
