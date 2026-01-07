var currentArticleId = null;

function openFileManager(articleId) {
    currentArticleId = articleId;
    const modal = document.getElementById('fileManagerModal');
    modal.style.display = 'block';
    modal.setAttribute('aria-hidden', 'false');
    loadFiles(articleId);
}

function closeFileManager() {
    const modal = document.getElementById('fileManagerModal');
    modal.style.display = 'none';
    modal.setAttribute('aria-hidden', 'true');
    currentArticleId = null;
    document.getElementById('fileList').innerHTML = '';
    document.getElementById('uploadForm').reset();
}

window.addEventListener('click', e => { if (e.target.id === 'fileManagerModal') closeFileManager(); });
window.addEventListener('keydown', e => { if (e.key === 'Escape') closeFileManager(); });

function loadFiles(articleId) {
    const ul = document.getElementById('fileList');

    ul.innerHTML = '<li class="loading">Loading…</li>';

    fetch(`/files/${articleId}`)
        .then(res => res.json())
        .then(data => {
            ul.innerHTML = '';

            (data.files || []).forEach(f => {
                const li = document.createElement('li');
                li.id = `file-${f.id}`;
                li.innerHTML = `
                    <div class="file-actions">
                        <a href="/download_file/${f.id}" target="_blank">
                            <button class="download-btn">${f.filename}</button>
                        </a>
                        <button onclick="deleteFile(${f.id})" class="delete-btn">Delete</button>
                    </div>
                `;
                ul.appendChild(li);
            });
        })
        .catch(() => {
            ul.innerHTML = '<li class="error">Failed to load files</li>';
        });
}

function deleteFile(fileId) {
    if (!confirm('Delete this file?')) return;
    fetch(`/delete_file/${fileId}`, { method: 'POST' })
        .then(res => res.json())
        .then(data => { if (data.success) document.getElementById(`file-${fileId}`).remove(); });
}

document.addEventListener('DOMContentLoaded', () => {
    document.getElementById('uploadForm').addEventListener('submit', async e => {
        e.preventDefault();
        if (!currentArticleId) return;

        const fileInput = document.getElementById('fileInput');
        if (!fileInput.files.length) return;

        const formData = new FormData(e.target);

        const uploadBtn = e.target.querySelector('button[type="submit"]');
        uploadBtn.disabled = true;
        uploadBtn.textContent = "Wait...";

        try {
            const res = await fetch(`/upload/${currentArticleId}`, {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            if (data.success) {
                fileInput.value = "";
                loadFiles(currentArticleId);
            } else {
                alert("Upload failed: " + (data.message || "Unknown error"));
            }
        } catch (err) {
            alert("Upload failed. Please try again.");
            console.error(err);
        } finally {
            uploadBtn.disabled = false;
            uploadBtn.textContent = "Upload";
        }
    });
});
