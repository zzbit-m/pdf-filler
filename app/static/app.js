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
    templates: [],
    batchFiles: [],
    previewIndex: 1,
    previewPage: 1,
    previewPageCount: 1,
    textBlockCounter: 0,
    fillFields: [],
    selectedField: null,
};

function api(method, url, data, timeoutMs = 30000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const opts = { method, headers: {}, signal: controller.signal };
    if (data instanceof FormData) {
        opts.body = data;
    } else if (data) {
        opts.headers['Content-Type'] = 'application/json';
        opts.body = JSON.stringify(data);
    }
    return fetch(url, opts).then(async r => {
        clearTimeout(timer);
        if (!r.ok) {
            const err = await r.json().catch(() => ({ detail: r.statusText }));
            throw new Error(err.detail || `HTTP ${r.status}`);
        }
        const ct = r.headers.get('content-type') || '';
        if (ct.includes('application/json')) return r.json();
        return r;
    }).catch(e => {
        clearTimeout(timer);
        if (e.name === 'AbortError') throw new Error('Request timed out');
        throw e;
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
    document.getElementById('excel-file-name').textContent = file.name;
    document.getElementById('excel-clear').style.display = 'inline-block';
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
        document.getElementById('excel-file-name').textContent = 'No file chosen';
        document.getElementById('excel-clear').style.display = 'none';
        e.target.value = '';
    }
});

document.getElementById('pdf-input').addEventListener('change', async e => {
    const file = e.target.files[0];
    if (!file) return;
    document.getElementById('pdf-file-name').textContent = file.name;
    document.getElementById('pdf-clear').style.display = 'inline-block';
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
        const previewImg = document.getElementById('pdf-upload-preview');
        if (previewImg) {
            previewImg.onerror = () => { document.getElementById('pdf-upload-preview-wrapper').classList.add('no-preview'); };
            previewImg.src = '/preview/' + data.pdf_id + '/1?t=' + Date.now();
        }
        checkStep2Ready();
    } catch (err) {
        showMsg('pdf-status', err.message, 'error');
        document.getElementById('pdf-file-name').textContent = 'No file chosen';
        document.getElementById('pdf-clear').style.display = 'none';
        e.target.value = '';
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

function esc(s) { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); }

function checkStep2Ready() {
    document.getElementById('to-position-btn').disabled = !(state.columns.length && state.pdfId);
}

document.getElementById('to-position-btn').addEventListener('click', () => {
    state.currentPage = 1;
    state.placedFields = [];
    state.templateId = null;
    switchStep(2);
});

function clamp(v, min, max) { return Math.max(min, Math.min(max, v)); }

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
            e.dataTransfer.effectAllowed = 'move';
        });
        container.appendChild(tag);
    });
    document.getElementById('template-name-input').value = '';
    renderPlacedFields();
    updateSaveButton();
    loadPreview(state.currentPage);
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
    }
});

document.getElementById('next-page').addEventListener('click', () => {
    if (state.currentPage < state.pageCount) {
        state.currentPage++;
        loadPreview(state.currentPage);
        setTimeout(renderMarkers, 100);
    }
});

// Drag & drop
const previewWrapper = document.getElementById('preview-wrapper');
const previewImg = document.getElementById('pdf-preview');

previewWrapper.addEventListener('dragenter', e => {
    e.preventDefault();
    previewWrapper.classList.add('drag-over');
});
previewWrapper.addEventListener('dragover', e => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    previewWrapper.classList.add('drag-over');
});
previewWrapper.addEventListener('dragleave', () => {
    previewWrapper.classList.remove('drag-over');
});
previewWrapper.addEventListener('dragend', () => {
    previewWrapper.classList.remove('drag-over');
});
previewWrapper.addEventListener('drop', e => {
    e.preventDefault();
    previewWrapper.classList.remove('drag-over');
    const column = e.dataTransfer.getData('text/plain');
    if (!column) return;
    const existingField = state.placedFields.find(f => f.column === column && f.page === state.currentPage);
    if (!existingField && !state.columns.includes(column)) return;
    if (!previewImg.naturalWidth) return;
    const rect = previewImg.getBoundingClientRect();
    const scaleX = previewImg.naturalWidth / previewImg.clientWidth;
    const scaleY = previewImg.naturalHeight / previewImg.clientHeight;
    const rawX = (e.clientX - rect.left) * scaleX;
    const rawY = (e.clientY - rect.top) * scaleY;
    const pixelX = clamp(rawX, 0, previewImg.naturalWidth);
    const pixelY = clamp(rawY, 0, previewImg.naturalHeight);
    const storedY = clamp(pixelY, 0, previewImg.naturalHeight);
    const existing = state.placedFields.findIndex(f => f.column === column && f.page === state.currentPage);
    if (existing >= 0) {
        state.placedFields[existing].x = pixelX;
        state.placedFields[existing].y = storedY;
    } else {
        state.placedFields.push({ column: column, page: state.currentPage, x: pixelX, y: storedY, font_size: 11, max_width: null });
    }
    renderPlacedFields();
    renderMarkers();
    updateSaveButton();
});

function renderMarkers() {
    const wrapper = document.getElementById('preview-wrapper');
    wrapper.querySelectorAll('.marker').forEach(el => el.remove());
    const img = previewImg;
    if (!img.naturalWidth) return;
    const scaleX = img.clientWidth / img.naturalWidth;
    const scaleY = img.clientHeight / img.naturalHeight;
    const pageFields = state.placedFields.filter(f => f.page === state.currentPage);
    pageFields.forEach(f => {
        const marker = document.createElement('div');
        marker.className = f.type === 'text' ? 'marker marker-text' : 'marker';
        marker.textContent = f.type === 'text' ? (f.text_value || f.column) : f.column;
        marker.style.left = (f.x * scaleX) + 'px';
        marker.style.top = (f.y * scaleY) + 'px';
        const ptToPx = 150 / 72;
        const fontSizePx = f.font_size * ptToPx * scaleY;
        marker.style.fontSize = fontSizePx + 'px';
        if (f.max_width) {
            const widthPx = f.max_width * ptToPx * scaleX;
            marker.style.width = widthPx + 'px';
            marker.style.whiteSpace = 'normal';
        }
        marker.draggable = true;
        marker.addEventListener('dragstart', e => {
            e.dataTransfer.setData('text/plain', f.column);
            e.dataTransfer.effectAllowed = 'move';
        });
        marker.addEventListener('click', () => {
            removeField(f.column, f.page);
        });
        wrapper.appendChild(marker);
    });
}

previewImg.addEventListener('load', renderMarkers);
window.addEventListener('resize', renderMarkers);

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
        if (f.type === 'text') {
            div.innerHTML =
                '<span class="field-name">' + esc(f.column) + '</span>' +
                '<span class="badge-text">Tx</span>' +
                '<span style="font-size:10px;color:#888;margin-left:2px;">All</span>' +
                '<label>Text</label><input type="text" class="text-value-input" value="' + esc(f.text_value || '') + '" data-col="' + esc(f.column) + '" data-p="' + f.page + '">' +
                '<label>Sz</label><input type="number" class="f-size" value="' + sz + '" min="6" max="36" data-col="' + esc(f.column) + '" data-p="' + f.page + '">' +
                '<button class="btn-danger btn-small" data-col="' + esc(f.column) + '" data-p="' + f.page + '">\u2715</button>';
        } else {
            div.innerHTML =
                '<span class="field-name">' + esc(f.column) + '</span>' +
                '<span style="font-size:10px;color:#888;">p' + f.page + '</span>' +
                '<label>Sz</label><input type="number" class="f-size" value="' + sz + '" min="6" max="36" data-col="' + esc(f.column) + '" data-p="' + f.page + '">' +
                '<label>W</label><input type="text" class="f-width" value="' + mw + '" placeholder="auto" data-col="' + esc(f.column) + '" data-p="' + f.page + '">' +
                '<button class="btn-danger btn-small" data-col="' + esc(f.column) + '" data-p="' + f.page + '">\u2715</button>';
        }
        div.querySelector('.f-size').addEventListener('change', e => {
            let val = parseInt(e.target.value) || 11;
            val = Math.max(6, Math.min(36, val));
            e.target.value = val;
            const f2 = state.placedFields.find(x => x.column === e.target.dataset.col && x.page === parseInt(e.target.dataset.p));
            if (f2) {
                f2.font_size = val;
                renderMarkers();
            }
        });
        const widthInput = div.querySelector('.f-width');
        if (widthInput) {
            widthInput.addEventListener('change', e => {
                const val = e.target.value.trim();
                const f2 = state.placedFields.find(x => x.column === e.target.dataset.col && x.page === parseInt(e.target.dataset.p));
                if (f2) {
                    f2.max_width = val ? parseFloat(val) : null;
                    if (f2.max_width !== null && isNaN(f2.max_width)) f2.max_width = null;
                    renderMarkers();
                }
            });
        }
        const textInput = div.querySelector('.text-value-input');
        if (textInput) {
            textInput.addEventListener('change', e => {
                const f2 = state.placedFields.find(x => x.column === e.target.dataset.col && x.page === parseInt(e.target.dataset.p));
                if (f2) {
                    f2.text_value = e.target.value;
                    renderMarkers();
                }
            });
        }
        div.querySelector('.btn-danger').addEventListener('click', e => {
            removeField(e.currentTarget.dataset.col, parseInt(e.currentTarget.dataset.p));
        });
        list.appendChild(div);
    });
}

function removeField(column, page) {
    state.placedFields = state.placedFields.filter(f => !(f.column === column && f.page === page));
    renderPlacedFields();
    renderMarkers();
    updateSaveButton();
}

function updateSaveButton() {
    const btn = document.getElementById('save-template-btn');
    btn.disabled = state.placedFields.length === 0;
}

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
            type: f.type || 'column',
            text_value: f.text_value || '',
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
        showMsg('fill-error', err.message, 'error');
    }
});

// ======== CLEAR FILE BUTTONS ========

document.getElementById('excel-clear').addEventListener('click', () => {
    document.getElementById('excel-input').value = '';
    document.getElementById('excel-file-name').textContent = 'No file chosen';
    document.getElementById('excel-clear').style.display = 'none';
    document.getElementById('excel-status').style.display = 'none';
    document.getElementById('excel-preview').style.display = 'none';
    document.querySelector('.upload-card:first-child').classList.remove('file-loaded');
    state.columns = [];
    state.previewRows = [];
    checkStep2Ready();
});

document.getElementById('pdf-clear').addEventListener('click', () => {
    document.getElementById('pdf-input').value = '';
    document.getElementById('pdf-file-name').textContent = 'No file chosen';
    document.getElementById('pdf-clear').style.display = 'none';
    document.getElementById('pdf-status').style.display = 'none';
    document.getElementById('pdf-info').style.display = 'none';
    document.getElementById('pdf-upload-preview').src = '';
    document.querySelector('.upload-card:last-child').classList.remove('file-loaded');
    state.pdfId = null;
    state.pageCount = 0;
    checkStep2Ready();
});

document.getElementById('add-text-block-btn').addEventListener('click', () => {
    const input = document.getElementById('text-block-input');
    const text = input.value.trim();
    if (!text) return;
    const img = document.getElementById('pdf-preview');
    const centerX = img.naturalWidth ? Math.round(img.naturalWidth / 2) : 300;
    const centerY = img.naturalHeight ? Math.round(img.naturalHeight / 2) : 400;
    state.textBlockCounter++;
    state.placedFields.push({
        column: 'Text ' + state.textBlockCounter,
        page: state.currentPage,
        x: centerX,
        y: centerY,
        font_size: 11,
        max_width: null,
        type: 'text',
        text_value: text,
    });
    input.value = '';
    renderPlacedFields();
    renderMarkers();
    updateSaveButton();
});

document.getElementById('fill-excel-clear').addEventListener('click', () => {
    document.getElementById('fill-excel-input').value = '';
    document.getElementById('fill-excel-file-name').textContent = 'No file chosen';
    document.getElementById('fill-excel-clear').style.display = 'none';
    document.getElementById('fill-excel-status').style.display = 'none';
    checkFillReady();
});

// ======== STEP 3: GENERATE ========

async function enterStep3() {
    await loadTemplates();
    document.getElementById('fill-excel-input').value = '';
    document.getElementById('fill-excel-file-name').textContent = 'No file chosen';
    document.getElementById('fill-excel-status').style.display = 'none';
    document.getElementById('fill-warnings').style.display = 'none';
    document.getElementById('fill-progress').style.display = 'none';
    document.getElementById('fill-done').style.display = 'none';
    document.getElementById('fill-error').style.display = 'none';
    document.getElementById('start-fill-btn').disabled = true;
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
    document.getElementById('delete-all-templates').style.display = list.length ? 'inline' : 'none';
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
    const el = document.getElementById('fill-excel-file-name');
    const btn = document.getElementById('fill-excel-clear');
    if (e.target.files[0]) {
        el.textContent = e.target.files[0].name;
        btn.style.display = 'inline-block';
        showMsg('fill-excel-status', 'Selected: ' + e.target.files[0].name, 'ok');
    } else {
        el.textContent = 'No file chosen';
        btn.style.display = 'none';
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
                if (data.warnings && data.warnings.length) {
                    const w = document.getElementById('fill-warnings');
                    w.innerHTML = '<strong>Batch warnings:</strong><br>' + data.warnings.join('<br>');
                    w.style.display = 'block';
                }
                state.batchFiles = data.files || [];
                state.previewIndex = 1;
                state.previewPage = 1;
                state.previewPageCount = 1;
                loadFillPreview(batchId);
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

// ======== DELETE ALL ========

document.getElementById('delete-all-templates').addEventListener('click', async e => {
    e.preventDefault();
    if (!window.confirm('Delete all templates? This cannot be undone.')) return;
    try {
        const list = await api('GET', '/template/list');
        for (const t of list) {
            await api('DELETE', '/template/' + t.id);
        }
        state.templateId = null;
        await loadTemplates();
    } catch (err) {
        showMsg('fill-error', err.message, 'error');
    }
});

// ======== FILL RESULT PREVIEW ========

function loadFillPreview(batchId) {
    const files = state.batchFiles;
    if (!files.length) return;
    const idx = state.previewIndex;
    if (idx < 1 || idx > files.length) return;
    document.getElementById('fill-preview').style.display = 'block';
    document.getElementById('fill-preview-file-info').textContent = 'File ' + idx + ' / ' + files.length;
    document.getElementById('prev-file').disabled = idx <= 1;
    document.getElementById('next-file').disabled = idx >= files.length;
    document.getElementById('fill-adjust-panel').style.display = 'none';
    state.selectedField = null;
    const img = document.getElementById('fill-preview-img');
    img.onload = () => {
        const totalPages = state.pageCount || 1;
        state.previewPageCount = totalPages;
        document.getElementById('fill-preview-page-info').textContent = 'Page ' + state.previewPage + ' / ' + totalPages;
        document.getElementById('prev-gen-page').disabled = state.previewPage <= 1;
        document.getElementById('next-gen-page').disabled = state.previewPage >= totalPages;
        renderFillMarkers();
    };
    img.src = '/fill/' + batchId + '/preview/' + idx + '/' + state.previewPage + '?t=' + Date.now();
    document.getElementById('fill-preview-wrapper').style.display = 'block';
    loadFillFields();
}

async function loadFillFields() {
    const batchId = state.batchId;
    const idx = state.previewIndex;
    const page = state.previewPage;
    if (!batchId || !idx || !page) return;
    try {
        const fields = await api('GET', '/fill/' + batchId + '/fields/' + idx + '/' + page);
        state.fillFields = fields;
        console.log('fillFields loaded:', fields.length, fields);
        renderFillMarkers();
        if (!fields.length) {
            document.getElementById('fill-error').textContent = 'No fields on this page — place fields in Step 2 first.';
            document.getElementById('fill-error').style.display = 'block';
        }
    } catch (err) {
        console.error('Failed to load fill fields:', err);
        showMsg('fill-error', 'Failed to load field positions: ' + err.message, 'error');
    }
}

function renderFillMarkers() {
    const wrapper = document.getElementById('fill-preview-wrapper');
    wrapper.querySelectorAll('.marker').forEach(el => el.remove());
    const img = document.getElementById('fill-preview-img');
    if (!img.naturalWidth) return;
    const scaleX = img.clientWidth / img.naturalWidth;
    const scaleY = img.clientHeight / img.naturalHeight;
    state.fillFields.forEach(f => {
        const marker = document.createElement('div');
        var cls = 'marker fill-preview-marker'; if (state.selectedField === f.column) cls += ' marker-selected'; marker.className = cls;
        marker.textContent = f.type === 'text' ? (f.text_value || f.column) : f.column;
        marker.style.left = (f.x * scaleX) + 'px';
        marker.style.top = (f.y * scaleY) + 'px';
        const ptToPx = 150 / 72;
        const fontSizePx = f.font_size * ptToPx * scaleY;
        marker.style.fontSize = fontSizePx + 'px';
        if (f.max_width) {
            const widthPx = f.max_width * ptToPx * scaleX;
            marker.style.width = widthPx + 'px';
            marker.style.whiteSpace = 'normal';
        }
        marker.dataset.column = f.column;
        marker.draggable = true;
        marker.addEventListener('dragstart', e => {
            e.dataTransfer.setData('text/plain', f.column);
            e.dataTransfer.effectAllowed = 'move';
        });
        marker.addEventListener('click', e => {
            e.stopPropagation();
            selectFillField(f.column);
        });
        wrapper.appendChild(marker);
    });
}

function selectFillField(column) {
    const field = state.fillFields.find(f => f.column === column);
    if (!field) return;
    state.selectedField = column;
    renderFillMarkers();
    document.getElementById('adjust-field-name').textContent = field.column;
    document.getElementById('adjust-font-size').value = field.font_size;
    document.getElementById('fill-adjust-panel').style.display = 'block';
}

async function applyFillAdjustment(column, extra) {
    const field = state.fillFields.find(f => f.column === column);
    if (!field) return;
    const fontInput = document.getElementById('adjust-font-size');
    const fontSize = parseInt(fontInput.value) || 11;
    const payload = {
        column: column,
        page: state.previewPage,
        font_size: Math.max(6, Math.min(36, fontSize)),
    };
    if (extra) {
        if (extra.x !== undefined) payload.x = extra.x;
        if (extra.y !== undefined) payload.y = extra.y;
    }
    try {
        await api('POST', '/fill/' + state.batchId + '/adjust/' + state.previewIndex, payload);
        state.selectedField = null;
        document.getElementById('fill-adjust-panel').style.display = 'none';
        const img = document.getElementById('fill-preview-img');
        img.src = '/fill/' + state.batchId + '/preview/' + state.previewIndex + '/' + state.previewPage + '?t=' + Date.now();
        setTimeout(loadFillFields, 300);
    } catch (err) {
        showMsg('fill-error', 'Adjustment failed: ' + err.message, 'error');
    }
}

document.getElementById('fill-preview-img').addEventListener('load', renderFillMarkers);

const fillPreviewWrapper = document.getElementById('fill-preview-wrapper');
fillPreviewWrapper.addEventListener('dragover', e => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
});
fillPreviewWrapper.addEventListener('drop', e => {
    e.preventDefault();
    const column = e.dataTransfer.getData('text/plain');
    if (!column) return;
    const field = state.fillFields.find(f => f.column === column);
    if (!field) return;
    const img = document.getElementById('fill-preview-img');
    if (!img.naturalWidth) return;
    const rect = fillPreviewWrapper.getBoundingClientRect();
    const scaleX = img.naturalWidth / img.clientWidth;
    const scaleY = img.naturalHeight / img.clientHeight;
    const rawX = (e.clientX - rect.left) * scaleX;
    const rawY = (e.clientY - rect.top) * scaleY;
    const pixelX = clamp(rawX, 0, img.naturalWidth);
    const pixelY = clamp(rawY, 0, img.naturalHeight);
    applyFillAdjustment(column, { x: Math.round(pixelX), y: Math.round(pixelY) });
});

document.getElementById('apply-adjust-btn').addEventListener('click', () => {
    if (state.selectedField) {
        applyFillAdjustment(state.selectedField);
    }
});
document.getElementById('adjust-font-size').addEventListener('input', e => {
    const marker = document.querySelector('#fill-preview-wrapper .marker.marker-selected');
    if (!marker) return;
    const val = parseInt(e.target.value) || 11;
    const img = document.getElementById('fill-preview-img');
    if (!img.naturalWidth) return;
    const scaleY = img.clientHeight / img.naturalHeight;
    const ptToPx = 150 / 72;
    marker.style.fontSize = (clamp(val, 6, 36) * ptToPx * scaleY) + 'px';
});
document.getElementById('close-adjust-btn').addEventListener('click', () => {
    state.selectedField = null;
    document.getElementById('fill-adjust-panel').style.display = 'none';
});

document.getElementById('prev-file').addEventListener('click', () => {
    if (state.previewIndex > 1) {
        state.previewIndex--;
        state.previewPage = 1;
        loadFillPreview(state.batchId);
    }
});

document.getElementById('next-file').addEventListener('click', () => {
    if (state.previewIndex < state.batchFiles.length) {
        state.previewIndex++;
        state.previewPage = 1;
        loadFillPreview(state.batchId);
    }
});

document.getElementById('prev-gen-page').addEventListener('click', () => {
    if (state.previewPage > 1) {
        state.previewPage--;
        loadFillPreview(state.batchId);
    }
});

document.getElementById('next-gen-page').addEventListener('click', () => {
    if (state.previewPage < state.previewPageCount) {
        state.previewPage++;
        loadFillPreview(state.batchId);
    }
});

