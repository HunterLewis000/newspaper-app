var currentEditorArticleId = null;
var editorFileIds = { unedited: null, edited: null };

function openEditorTools(articleId) {
    currentEditorArticleId = articleId;
    const modal = document.getElementById('editorToolsModal');
    modal.style.display = 'block';
    modal.setAttribute('aria-hidden', 'false');
    loadEditorFiles(articleId);
}

function closeEditorTools() {
    const modal = document.getElementById('editorToolsModal');
    modal.style.display = 'none';
    modal.setAttribute('aria-hidden', 'true');
    currentEditorArticleId = null;
    editorFileIds = { unedited: null, edited: null };
    document.getElementById('editorUploadForm').reset();
}

window.addEventListener('click', e => {
    if (e.target.id === 'editorToolsModal') closeEditorTools();
});
window.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeEditorTools();
});

function loadEditorFiles(articleId) {
    fetch(`/files/${articleId}`)
        .then(res => res.json())
        .then(data => {
            const files = data.files || [];

            // Find unedited and edited files
            const unedited = files.find(f => f.category === 'unedited');
            const edited = files.find(f => f.category === 'edited');

            // Display unedited file
            const uneditedDisplay = document.getElementById('editorUneditedFile');
            const downloadBtn = document.getElementById('downloadUneditedBtn');

            if (unedited) {
                editorFileIds.unedited = unedited.id;
                uneditedDisplay.innerHTML = `<a href="/download_file/${unedited.id}" target="_blank"><strong>${unedited.filename}</strong></a>`;
                downloadBtn.href = `/download_file/${unedited.id}`;
                downloadBtn.style.display = 'inline-block';
            } else {
                uneditedDisplay.innerHTML = '<p style="color: #999;">No file uploaded</p>';
                downloadBtn.style.display = 'none';
            }

            // Display edited file
            const editedDisplay = document.getElementById('editorEditedFile');
            const compareBtn = document.getElementById('compareBtn');

            if (edited) {
                editorFileIds.edited = edited.id;
                editedDisplay.innerHTML = `<a href="/download_file/${edited.id}" target="_blank"><strong>${edited.filename}</strong></a> <button onclick="deleteEditorFile(${edited.id})" class="delete-btn" style="margin-left: 8px;">Remove</button>`;
                compareBtn.style.display = unedited ? 'block' : 'none';
            } else {
                editedDisplay.innerHTML = '<p style="color: #999;">No file uploaded</p>';
                compareBtn.style.display = 'none';
            }
        })
        .catch(err => console.error('Failed to load editor files:', err));
}

function deleteEditorFile(fileId) {
    if (!confirm('Delete this file?')) return;
    fetch(`/delete_file/${fileId}`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                loadEditorFiles(currentEditorArticleId);
            }
        });
}

function compareFiles() {
    if (!editorFileIds.unedited || !editorFileIds.edited) {
        alert('Please upload both unedited and edited versions to compare.');
        return;
    }

    const editorPanel = document.querySelector('.editor-tools-container');
    const comparisonPanel = document.getElementById('comparisonPanel');
    const comparisonResult = document.getElementById('comparisonResult');

    editorPanel.style.display = 'none';
    comparisonPanel.style.display = 'block';
    comparisonResult.innerHTML = '<p style="color: #999; text-align: center;">Preparing comparison...</p>';

    fetch(`/compare_files/${editorFileIds.unedited}/${editorFileIds.edited}`)
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                displayComparison(data.differences);
            } else {
                comparisonResult.innerHTML = '<p style="color: #d32f2f;">Could not compare files. Make sure both files are accessible.</p>';
            }
        })
        .catch(err => {
            console.error('Comparison failed:', err);
            comparisonResult.innerHTML = '<p style="color: #d32f2f;">Comparison failed. Please try again.</p>';
        });
}

function displayComparison(differences) {
    const comparisonResult = document.getElementById('comparisonResult');

    if (!differences || differences.length === 0) {
        comparisonResult.innerHTML = '<p style="text-align: center; color: #666;">No differences found between files.</p>';
        return;
    }

    let html = '';
    differences.forEach((diff, idx) => {
        if (diff.type === 'added') {
            html += `<div><span class="diff-added">+ ${escapeHtml(diff.text)}</span></div>`;
        } else if (diff.type === 'removed') {
            html += `<div><span class="diff-removed">- ${escapeHtml(diff.text)}</span></div>`;
        } else {
            html += `<div>${escapeHtml(diff.text)}</div>`;
        }
    });

    comparisonResult.innerHTML = html;
}

function backToEditor() {
    const editorPanel = document.querySelector('.editor-tools-container');
    const comparisonPanel = document.getElementById('comparisonPanel');

    editorPanel.style.display = 'grid';
    comparisonPanel.style.display = 'none';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

document.addEventListener('DOMContentLoaded', () => {
    const editorUploadForm = document.getElementById('editorUploadForm');
    const fileInput = editorUploadForm.querySelector('.fileInput');

    editorUploadForm.addEventListener('click', () => fileInput.click());

    editorUploadForm.addEventListener('dragover', e => {
        e.preventDefault();
        editorUploadForm.style.borderColor = '#3b82f6';
        editorUploadForm.style.background = '#eff6ff';
    });

    editorUploadForm.addEventListener('dragleave', () => {
        editorUploadForm.style.borderColor = '#d1d5db';
        editorUploadForm.style.background = 'white';
    });

    editorUploadForm.addEventListener('drop', e => {
        e.preventDefault();
        editorUploadForm.style.borderColor = '#d1d5db';
        editorUploadForm.style.background = 'white';
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            handleEditorUpload();
        }
    });

    editorUploadForm.addEventListener('submit', e => {
        e.preventDefault();
        handleEditorUpload();
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) {
            handleEditorUpload();
        }
    });

    function handleEditorUpload() {
        if (!currentEditorArticleId) return;

        const file = fileInput.files[0];
        const ext = file.name.split('.').pop().toLowerCase();
        const docExts = ['doc', 'docx'];

        if (!docExts.includes(ext)) {
            alert('Please upload a Word document (.doc or .docx)');
            fileInput.value = '';
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('category', 'edited');

        const dropZone = editorUploadForm.querySelector('.drop-zone-content') || editorUploadForm;
        const originalContent = dropZone.innerHTML;
        dropZone.innerHTML = '<span style="color: #6b7280;">Uploading...</span>';

        fetch(`/upload/${currentEditorArticleId}`, {
            method: 'POST',
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                fileInput.value = '';
                loadEditorFiles(currentEditorArticleId);
                dropZone.innerHTML = originalContent;
            } else {
                alert('Upload failed: ' + (data.message || 'Unknown error'));
                dropZone.innerHTML = originalContent;
            }
        })
        .catch(err => {
            alert('Upload failed. Please try again.');
            console.error(err);
            dropZone.innerHTML = originalContent;
        });
    }
});
