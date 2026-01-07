function addOrUpdateRow(data) {
    let row = document.getElementById(`row-${data.id}`);
    const currentStatus = row?.querySelector('.status-button')?.textContent || data.status;
    const currentEditor = row?.querySelector('.editor select')?.value;
    const currentCat = row?.querySelector('.cat select')?.value;

    if (!row) {
        const tbody = document.querySelector('table tbody');
        row = document.createElement('tr');
        row.id = `row-${data.id}`;
        tbody.appendChild(row);
    }

    row.dataset.id = data.id;

    row.innerHTML = `
        <td class="drag-handle" style="cursor: grab;">☰</td>
        <td class="cat">
            <select onchange="updateCat(${data.id}, this.value)" ${currentStatus === 'Published' ? 'disabled' : ''}>
                <option value="F" ${(currentCat || data.cat) === 'F' ? 'selected' : ''}>F</option>
                <option value="N" ${(currentCat || data.cat) === 'N' ? 'selected' : ''}>N</option>
                <option value="O" ${(currentCat || data.cat) === 'O' ? 'selected' : ''}>O</option>
                <option value="S" ${(currentCat || data.cat) === 'S' ? 'selected' : ''}>S</option>
            </select>
        </td>
        <td class="title">${data.title}</td>
        <td class="author">${data.author}</td>
        <td class="status">
            <button class="status-button" onclick="openStatusModal(${data.id}, '${currentStatus}')">
                ${currentStatus}
            </button>
            <button class="status-color ${ (data.status_color === 'red') ? 'red' : (data.status_color === 'yellow' ? 'yellow' : 'white') }" aria-label="Status Color" onclick="cycleStatusColor(${data.id}, event)"></button>
        </td>
        <td class="editor">
            <select onchange="updateEditor(${data.id}, this.value)" ${currentStatus === 'Published' ? 'disabled' : ''}>
                <option value="">-- Select --</option>
                <option value="Copley" ${(currentEditor || data.editor) === 'Copley' ? 'selected' : ''}>Copley</option>
                <option value="Lewis" ${(currentEditor || data.editor) === 'Lewis' ? 'selected' : ''}>Lewis</option>
            </select>
        </td>
        <td class="deadline">${data.deadline || ''}</td>
        <td class="filescol"><button class="file-icon-btn" onclick="openFileManager(${data.id})">Files</button></td>
      <td class="actions">
    ${
        currentStatus === 'Published'
        ? `<button onclick="markComplete(${data.id})" style="color:green;">Mark Complete</button>`
        : `
            <button onclick="toggleEdit(${data.id})" id="edit-btn-${data.id}">Edit</button>
            <button onclick="deleteArticle(${data.id})" style="color:red;">Delete</button>
          `
    }
    </td>


    `;

    if (currentStatus === 'Published') row.classList.add('published');
    else row.classList.remove('published');
}

function toggleEdit(articleId) {
    const row = document.getElementById(`row-${articleId}`);
    const editBtn = document.getElementById(`edit-btn-${articleId}`);

    if (editBtn.textContent === "Edit") {
        const title = row.querySelector('.title').textContent;
        const author = row.querySelector('.author').textContent;
        const deadline = row.querySelector('.deadline').textContent;

        row.querySelector('.title').innerHTML = `<input type="text" value="${title}" id="title-input-${articleId}">`;
        row.querySelector('.author').innerHTML = `<input type="text" value="${author}" id="author-input-${articleId}">`;
        row.querySelector('.deadline').innerHTML = `<input type="date" value="${deadline}" id="deadline-input-${articleId}">`;

        editBtn.textContent = "Done";
    } else {
        const newTitle = document.getElementById(`title-input-${articleId}`).value.trim();
        const newAuthor = document.getElementById(`author-input-${articleId}`).value.trim();
        const newDeadline = document.getElementById(`deadline-input-${articleId}`).value;

        fetch(`/update/${articleId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title: newTitle, author: newAuthor, deadline: newDeadline })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                row.querySelector('.title').textContent = newTitle;
                row.querySelector('.author').textContent = newAuthor;
                row.querySelector('.deadline').textContent = newDeadline;
                editBtn.textContent = "Edit";

                socket.emit('article_updated', { id: articleId, title: newTitle, author: newAuthor, deadline: newDeadline });
            } else alert("Failed to save changes.");
        });
    }
}

function cycleStatusColor(articleId, event) {
    event.stopPropagation();
    event.preventDefault();

    const row = document.getElementById(`row-${articleId}`);
    if (row && row.classList.contains('published')) return;
    if (!row) return;
    const dot = row.querySelector('.status-color');
    if (!dot) return;

    const classes = ['white','red','yellow'];
    const current = classes.find(c => dot.classList.contains(c)) || 'white';
    const next = classes[(classes.indexOf(current) + 1) % classes.length];

    dot.classList.remove('white','red','yellow');
    dot.classList.add(next);

    fetch(`/update_status_color/${articleId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ color: next })
    }).then(res => {
        if (!res.ok) {
            dot.classList.remove('white','red','yellow');
            dot.classList.add(current);
            return res.json().then(j => { throw new Error(j.error || 'update failed'); });
        }
        return res.json();
    }).then(json => {
        if (json.success) {
            socket.emit('status_color_updated', { id: articleId, status_color: next });
        }
    }).catch(err => {
        console.error('Failed to update status color', err);
    });
}

function updateCat(articleId, cat) {
    fetch(`/update_cat/${articleId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cat })
    }).then(res => res.json())
      .then(data => {
          if (!data.success) alert('Error updating category!');
          else socket.emit('cat_updated', { id: articleId, cat });
      });
}

function updateEditor(articleId, editor) {
    fetch(`/update_editor/${articleId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ editor })
    }).then(res => res.json())
      .then(data => {
          if (!data.success) alert('Error updating editor!');
          else socket.emit('editor_updated', { id: articleId, editor });
      });
}

function deleteArticle(articleId) {
    if (!confirm("Are you sure you want to delete this article?")) return;
    fetch(`/delete/${articleId}`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                const row = document.getElementById(`row-${articleId}`);
                if (row) row.remove();
                socket.emit('article_deleted', { id: articleId });
            } else alert('Error deleting article!');
        });
}

function markComplete(articleId) {
    fetch(`/archive/${articleId}`, { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                const row = document.getElementById(`row-${articleId}`);
                if (row) row.remove();
            } else {
                alert("Failed to archive article.");
            }
        });
}
