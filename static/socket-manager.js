const socket = io();

socket.on('article_added', addOrUpdateRow);

socket.on('article_updated', data => {
    const row = document.getElementById(`row-${data.id}`);
    if (row) {
        row.querySelector('.title').textContent = data.title;
        row.querySelector('.author').textContent = data.author;
        row.querySelector('.deadline').textContent = data.deadline || '';
    } else addOrUpdateRow(data);
});

socket.on('status_updated', data => {
    const row = document.getElementById(`row-${data.id}`);
    if (row) {
        const statusBtn = row.querySelector('.status-button');
        if (statusBtn) {
            statusBtn.textContent = data.status;
        }

        row.classList.toggle('published', data.status === 'Published');

        const catSelect = row.querySelector('.cat select');
        const editorSelect = row.querySelector('.editor select');
        if (data.status === 'Published') {
            if (catSelect) catSelect.disabled = true;
            if (editorSelect) editorSelect.disabled = true;
        } else {
            if (catSelect) catSelect.disabled = false;
            if (editorSelect) editorSelect.disabled = false;
        }

        const actionsCell = row.querySelector('.actions');
        if (data.status === 'Published') {
            actionsCell.innerHTML = `<button onclick="markComplete(${data.id})" style="color:green;">Mark Complete</button>`;
        } else {
            actionsCell.innerHTML = `
                <button onclick="toggleEdit(${data.id})" id="edit-btn-${data.id}">Edit</button>
                <button onclick="deleteArticle(${data.id})" style="color:red;">Delete</button>
            `;
        }
        
        if (currentStatusArticleId === data.id) {
            updateStatusTimelineInPlace(data.id);
        }
    }
});

socket.on('status_color_updated', data => {
    const row = document.getElementById(`row-${data.id}`);
    if (!row) return;
    const dot = row.querySelector('.status-color');
    if (!dot) return;
    dot.classList.remove('white','red','yellow');
    dot.classList.add(data.status_color || 'white');
});

socket.on('editor_updated', data => {
    const row = document.getElementById(`row-${data.id}`);
    if (row) row.querySelector('.editor select').value = data.editor;
});

socket.on('cat_updated', data => {
    const row = document.getElementById(`row-${data.id}`);
    if (row) row.querySelector('.cat select').value = data.cat;
});

socket.on('article_deleted', data => {
    const row = document.getElementById(`row-${data.id}`);
    if (row) row.remove();
});

socket.on('file_uploaded', data => { 
    if (currentArticleId === data.articleId) loadFiles(currentArticleId); 
});

socket.on('file_deleted', data => { 
    const li = document.getElementById(`file-${data.file_id}`); 
    if (li) li.remove(); 
});

socket.on('article_archived', data => {
    const row = document.getElementById(`row-${data.id}`);
    if (row) row.remove();
});

socket.on('article_activated', data => {
    fetch(`/article/${data.id}`)
        .then(res => res.json())
        .then(article => addOrUpdateRow(article));
});

socket.on('update_article_order', (data) => {
    const tbody = document.querySelector('#articles-tbody');
    data.order.forEach(id => {
        const row = tbody.querySelector(`tr[data-id="${id}"]`);
        tbody.appendChild(row);
    });
});
