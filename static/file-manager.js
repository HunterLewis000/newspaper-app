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
    document.querySelectorAll('.upload-drop-zone').forEach(form => form.reset());
    document.querySelectorAll('.file-list-modern').forEach(ul => ul.innerHTML = '');
}

window.addEventListener('click', e => { if (e.target.id === 'fileManagerModal') closeFileManager(); });
window.addEventListener('keydown', e => { if (e.key === 'Escape') closeFileManager(); });

function categorizeFile(filename, fileCategory) {
    const ext = filename.split('.').pop().toLowerCase();
    const docExts = ['doc', 'docx'];
    const photoExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'];

    if (fileCategory === 'unedited' || fileCategory === 'edited') {
        return docExts.includes(ext) ? fileCategory : null;
    } else if (fileCategory === 'media') {
        return 'other';
    }
    return fileCategory;
}

function loadFiles(articleId) {
    const categories = ['unedited', 'edited', 'photos', 'other'];
    categories.forEach(cat => {
        const ul = document.getElementById(`fileList-${cat}`);
        if (ul) ul.innerHTML = '';
    });

    fetch(`/files/${articleId}`)
        .then(res => res.json())
        .then(data => {
            const files = data.files || [];

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

            // Combine photos and other into media for display
            const mediaFiles = [...(categorized.photos || []), ...(categorized.other || [])];

            // Check if unedited has files
            const uneditedFiles = categorized.unedited || [];
            const hasUnedited = uneditedFiles.length > 0;

            // Display unedited and edited
            ['unedited', 'edited'].forEach(category => {
                const ul = document.getElementById(`fileList-${category}`);
                if (!ul) return;
                ul.innerHTML = '';

                const fileList = categorized[category] || [];
                fileList.forEach(f => {
                    const li = createFileItem(f, category);
                    ul.appendChild(li);
                });

                // Hide/show upload zone for single-file categories
                const form = document.querySelector(`.upload-drop-zone[data-category="${category}"]`);
                if (form) {
                    if (fileList.length > 0) {
                        form.style.display = 'none';
                    } else {
                        form.style.display = 'block';
                    }

                    // Disable edited if no unedited file
                    if (category === 'edited') {
                        const editedStep = document.getElementById('edited-step');
                        if (!hasUnedited) {
                            editedStep.classList.add('disabled-section');
                            form.disabled = true;
                            form.querySelectorAll('input').forEach(input => input.disabled = true);
                        } else {
                            editedStep.classList.remove('disabled-section');
                            form.disabled = false;
                            form.querySelectorAll('input').forEach(input => input.disabled = false);
                        }
                    }
                }
            });

            // Display media files combined
            const mediaList = document.getElementById('fileList-photos');
            if (mediaList) {
                mediaList.innerHTML = '';
                mediaFiles.forEach(f => {
                    const li = createFileItem(f, 'media');
                    mediaList.appendChild(li);
                });
            }

            // Hide other files list since we combined it
            const otherList = document.getElementById('fileList-other');
            if (otherList) {
                otherList.style.display = 'none';
            }
        })
        .catch(err => {
            console.error('Failed to load files:', err);
        });
}

function createFileItem(f, category) {
    const li = document.createElement('li');
    li.id = `file-${f.id}`;

    li.innerHTML = `
        <div class="file-actions">
            <a href="/download_file/${f.id}" target="_blank">
                <button class="download-btn">${f.filename}</button>
            </a>
            <button onclick="deleteFile(${f.id}, '${category}')" class="delete-btn">Remove</button>
        </div>
    `;
    return li;
}

function deleteFile(fileId, category) {
    if (!confirm('Delete this file?')) return;
    fetch(`/delete_file/${fileId}`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                loadFiles(currentArticleId);
            }
        });
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.upload-drop-zone').forEach(form => {
        const fileInput = form.querySelector('.fileInput');
        const category = form.getAttribute('data-category');

        form.addEventListener('click', () => fileInput.click());

        form.addEventListener('dragover', e => {
            e.preventDefault();
            form.style.borderColor = '#3b82f6';
            form.style.background = '#eff6ff';
        });

        form.addEventListener('dragleave', () => {
            form.style.borderColor = '#d1d5db';
            form.style.background = 'white';
        });

        form.addEventListener('drop', e => {
            e.preventDefault();
            form.style.borderColor = '#d1d5db';
            form.style.background = 'white';
            if (e.dataTransfer.files.length) {
                fileInput.files = e.dataTransfer.files;
                handleUpload(form, category);
            }
        });

        form.addEventListener('submit', e => {
            e.preventDefault();
            handleUpload(form, category);
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files.length) {
                handleUpload(form, category);
            }
        });
    });

    function handleUpload(form, category) {
        if (!currentArticleId) return;

        const fileInput = form.querySelector('.fileInput');
        if (!fileInput.files.length) return;

        // Check if category allows only 1 file
        if (category === 'unedited' || category === 'edited') {
            const fileList = document.getElementById(`fileList-${category}`);
            if (fileList.children.length > 0) {
                alert(`You can only upload one ${category} article. Please delete the existing file first.`);
                fileInput.value = '';
                return;
            }
        }

        const file = fileInput.files[0];
        const validatedCategory = categorizeFile(file.name, category);

        if (!validatedCategory) {
            const expected = category === 'unedited' || category === 'edited'
                ? 'Word documents (.doc, .docx)'
                : 'any file type';
            alert(`Invalid file type. Please upload ${expected}.`);
            fileInput.value = '';
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('category', validatedCategory);

        const dropZone = form.querySelector('.drop-zone-content') || form;
        const originalContent = dropZone.innerHTML;
        dropZone.innerHTML = '<span style="color: #6b7280;">Uploading...</span>';

        fetch(`/upload/${currentArticleId}`, {
            method: 'POST',
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                fileInput.value = '';
                loadFiles(currentArticleId);
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
