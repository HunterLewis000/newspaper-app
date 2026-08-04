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
    document.querySelectorAll('.upload-form').forEach(form => form.reset());
    document.querySelectorAll('.file-list').forEach(ul => ul.innerHTML = '');
}

window.addEventListener('click', e => { if (e.target.id === 'fileManagerModal') closeFileManager(); });
window.addEventListener('keydown', e => { if (e.key === 'Escape') closeFileManager(); });

function categorizeFile(filename, fileCategory) {
    const ext = filename.split('.').pop().toLowerCase();
    const docExts = ['doc', 'docx'];
    const photoExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'];

    if (fileCategory === 'unedited' || fileCategory === 'edited') {
        return docExts.includes(ext) ? fileCategory : null;
    } else if (fileCategory === 'photos') {
        return photoExts.includes(ext) ? 'photos' : null;
    }
    return fileCategory;
}

function loadFiles(articleId) {
    const categories = ['unedited', 'edited', 'photos', 'other'];
    categories.forEach(cat => {
        const ul = document.getElementById(`fileList-${cat}`);
        ul.innerHTML = '';
    });

    fetch(`/files/${articleId}`)
        .then(res => res.json())
        .then(data => {
            const files = data.files || [];

            if (files.length === 0) {
                categories.forEach(cat => {
                    const ul = document.getElementById(`fileList-${cat}`);
                    ul.innerHTML = '<li style="color: #999; font-size: 0.9rem;">No files</li>';
                });
                return;
            }

            const categorized = {
                unedited: [],
                edited: [],
                photos: [],
                other: []
            };

            files.forEach(f => {
                const category = f.category || 'other';
                if (categorized[category]) {
                    categorized[category].push(f);
                } else {
                    categorized[category].push(f);
                }
            });

            Object.entries(categorized).forEach(([category, fileList]) => {
                const ul = document.getElementById(`fileList-${category}`);
                ul.innerHTML = '';

                if (fileList.length === 0) {
                    ul.innerHTML = '<li style="color: #999; font-size: 0.9rem;">No files</li>';
                } else {
                    fileList.forEach(f => {
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
                }
            });
        })
        .catch(err => {
            console.error('Failed to load files:', err);
            const categories = ['unedited', 'edited', 'photos', 'other'];
            categories.forEach(cat => {
                const ul = document.getElementById(`fileList-${cat}`);
                ul.innerHTML = '<li style="color: #999;">Failed to load</li>';
            });
        });
}

function deleteFile(fileId) {
    if (!confirm('Delete this file?')) return;
    fetch(`/delete_file/${fileId}`, { method: 'POST' })
        .then(res => res.json())
        .then(data => { if (data.success) document.getElementById(`file-${fileId}`).remove(); });
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.upload-form').forEach(form => {
        form.addEventListener('submit', async e => {
            e.preventDefault();
            if (!currentArticleId) return;

            const fileInput = form.querySelector('.fileInput');
            const category = form.getAttribute('data-category');

            if (!fileInput.files.length) return;

            const file = fileInput.files[0];
            const validatedCategory = categorizeFile(file.name, category);

            if (!validatedCategory) {
                const expected = category === 'unedited' || category === 'edited'
                    ? 'Word documents (.doc, .docx)'
                    : 'image files';
                alert(`Invalid file type. Please upload ${expected}.`);
                return;
            }

            const formData = new FormData();
            formData.append('file', file);
            formData.append('category', validatedCategory);

            const uploadBtn = form.querySelector('button[type="submit"]');
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
});
