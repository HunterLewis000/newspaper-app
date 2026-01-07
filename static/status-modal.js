const STATUS_OPTIONS = ['Not Started', 'In Progress', 'Needs Edit', 'Edited', 'Published'];
var currentStatusArticleId = null;

function openStatusModal(articleId, currentStatus) {
    currentStatusArticleId = articleId;
    const modal = document.getElementById('statusModal');
    modal.style.display = 'flex';
    modal.setAttribute('aria-hidden', 'false');
    loadStatusHistory(articleId);
}

function closeStatusModal() {
    const modal = document.getElementById('statusModal');
    modal.style.display = 'none';
    modal.setAttribute('aria-hidden', 'true');
    currentStatusArticleId = null;
}

window.addEventListener('click', e => { 
    if (e.target.id === 'statusModal') closeStatusModal(); 
});

window.addEventListener('keydown', e => { 
    if (e.key === 'Escape' && document.getElementById('statusModal').style.display === 'flex') {
        closeStatusModal(); 
    }
});

async function loadStatusHistory(articleId) {
    const timeline = document.getElementById('statusTimeline');
    timeline.innerHTML = '<div style="text-align: center; padding: 20px;">Loading...</div>';
    
    try {
        const res = await fetch(`/status_history/${articleId}`);
        const data = await res.json();
        renderStatusTimeline(data.history, articleId);
    } catch (err) {
        timeline.innerHTML = '<div style="text-align: center; padding: 20px; color: #f44336;">Failed to load status history</div>';
        console.error('Failed to load status history:', err);
    }
}

function renderStatusTimeline(history, articleId) {
    const timeline = document.getElementById('statusTimeline');
    timeline.innerHTML = '';
    
    const statusMap = {};
    history.forEach(h => {
        if (!statusMap[h.status] || new Date(h.timestamp) > new Date(statusMap[h.status].timestamp)) {
            statusMap[h.status] = h;
        }
    });
    
    const currentStatusIndex = history.length > 0 ? 
        STATUS_OPTIONS.indexOf(history[history.length - 1].status) : -1;
    
    STATUS_OPTIONS.forEach((status, index) => {
        const item = document.createElement('div');
        item.className = 'status-timeline-item';
        
        const historyEntry = statusMap[status];
        const isActive = historyEntry && history[history.length - 1]?.status === status;
        
        const currentStatus = history.length > 0 ? history[history.length - 1].status : null;
        const isPublished = currentStatus === 'Published';
        
        const isCompleted = historyEntry !== undefined;
        const isSkipped = !isCompleted && index > 0 && index < currentStatusIndex;
        const shouldShowGreen = isCompleted || isSkipped;
        
        const line = document.createElement('div');
        line.className = 'status-timeline-line';
        if (index < currentStatusIndex || shouldShowGreen) {
            line.classList.add('active');
            line.style.animationDelay = `${index * 0.1}s`;
        }
        if (isPublished && shouldShowGreen) {
            line.classList.add('published');
        }
        
        const dot = document.createElement('div');
        dot.className = 'status-timeline-dot';
        if (isActive) {
            dot.classList.add('active');
        } else if (shouldShowGreen) {
            dot.classList.add('completed');
        }
        dot.style.animationDelay = `${index * 0.1 + 0.4}s`;
        if (isPublished && shouldShowGreen) {
            dot.classList.remove('active', 'completed');
            dot.classList.add('published');
        }
        
        const statusLabel = document.createElement('div');
        statusLabel.className = 'status-timeline-status';
        if (isActive) {
            statusLabel.classList.add('active');
        }
        if (isPublished && isActive) {
            statusLabel.classList.remove('active');
            statusLabel.classList.add('published');
        }
        statusLabel.textContent = status;
        statusLabel.onclick = () => changeStatus(articleId, status);
        
        const meta = document.createElement('div');
        meta.className = 'status-timeline-meta';
        
        if (historyEntry) {
            const utcTimestamp = historyEntry.timestamp.endsWith('Z') ? historyEntry.timestamp : historyEntry.timestamp + 'Z';
            const date = new Date(utcTimestamp);
            const dateStr = date.toLocaleString('en-US', { 
                month: 'short', 
                day: 'numeric', 
                year: 'numeric',
                hour: 'numeric',
                minute: '2-digit',
                hour12: true
            });
            
            meta.innerHTML = `
                <div><strong>Updated by:</strong> ${historyEntry.user_name}</div>
                <div><strong>Date:</strong> ${dateStr}</div>
            `;
        }
        
        item.appendChild(line);
        item.appendChild(dot);
        item.appendChild(statusLabel);
        if (historyEntry) {
            item.appendChild(meta);
        }
        
        timeline.appendChild(item);
    });
}

async function updateStatusTimelineInPlace(articleId) {
    try {
        const res = await fetch(`/status_history/${articleId}`);
        const data = await res.json();
        const history = data.history;
        
        const statusMap = {};
        history.forEach(h => {
            if (!statusMap[h.status] || new Date(h.timestamp) > new Date(statusMap[h.status].timestamp)) {
                statusMap[h.status] = h;
            }
        });
        
        const currentStatusIndex = history.length > 0 ? 
            STATUS_OPTIONS.indexOf(history[history.length - 1].status) : -1;
        
        const currentStatus = history.length > 0 ? history[history.length - 1].status : null;
        const isPublished = currentStatus === 'Published';
        
        const timeline = document.getElementById('statusTimeline');
        const items = timeline.querySelectorAll('.status-timeline-item');
        
        STATUS_OPTIONS.forEach((status, index) => {
            const item = items[index];
            if (!item) return;
            
            const historyEntry = statusMap[status];
            const isActive = historyEntry && history[history.length - 1]?.status === status;
            const isCompleted = historyEntry !== undefined;
            const isSkipped = !isCompleted && index > 0 && index < currentStatusIndex;
            const shouldShowGreen = isCompleted || isSkipped;
            
            const line = item.querySelector('.status-timeline-line');
            if (line) {
                line.classList.remove('active', 'published');
                if (index < currentStatusIndex || shouldShowGreen) {
                    line.classList.add('active');
                }
                if (isPublished && shouldShowGreen) {
                    line.classList.add('published');
                }
            }
            
            const dot = item.querySelector('.status-timeline-dot');
            if (dot) {
                dot.classList.remove('active', 'completed', 'published');
                if (isActive) {
                    dot.classList.add('active');
                } else if (shouldShowGreen) {
                    dot.classList.add('completed');
                }
                if (isPublished && shouldShowGreen) {
                    dot.classList.remove('active', 'completed');
                    dot.classList.add('published');
                }
            }
            
            const statusLabel = item.querySelector('.status-timeline-status');
            if (statusLabel) {
                statusLabel.classList.remove('active', 'published');
                if (isActive) {
                    statusLabel.classList.add('active');
                }
                if (isPublished && isActive) {
                    statusLabel.classList.remove('active');
                    statusLabel.classList.add('published');
                }
            }
            
            let meta = item.querySelector('.status-timeline-meta');
            if (!meta) {
                meta = document.createElement('div');
                meta.className = 'status-timeline-meta';
                item.appendChild(meta);
            }
            
            if (historyEntry) {
                const utcTimestamp = historyEntry.timestamp.endsWith('Z') ? historyEntry.timestamp : historyEntry.timestamp + 'Z';
                const date = new Date(utcTimestamp);
                const dateStr = date.toLocaleString('en-US', { 
                    month: 'short', 
                    day: 'numeric', 
                    year: 'numeric',
                    hour: 'numeric',
                    minute: '2-digit',
                    hour12: true
                });
                
                meta.innerHTML = `
                    <div><strong>Updated by:</strong> ${historyEntry.user_name}</div>
                    <div><strong>Date:</strong> ${dateStr}</div>
                `;
                meta.style.display = 'block';
            } else {
                meta.innerHTML = '';
                meta.style.display = 'none';
            }
        });
    } catch (err) {
        console.error('Failed to update status timeline:', err);
    }
}

async function changeStatus(articleId, newStatus) {
    try {
        const historyRes = await fetch(`/status_history/${articleId}`);
        const historyData = await historyRes.json();
        const history = historyData.history;
        
        const currentStatusIndex = history.length > 0 ? 
            STATUS_OPTIONS.indexOf(history[history.length - 1].status) : -1;
        const newStatusIndex = STATUS_OPTIONS.indexOf(newStatus);
        
        if (currentStatusIndex > newStatusIndex) {
            const confirmed = confirm(`Are you sure you want to revert to "${newStatus}"?`);
            if (!confirmed) {
                return;
            }
        }
        
        const res = await fetch(`/update_status/${articleId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        
        const data = await res.json();
        if (data.success) {
            await updateStatusTimelineInPlace(articleId);
            
            const row = document.getElementById(`row-${articleId}`);
            if (row) {
                const statusBtn = row.querySelector('.status-button');
                if (statusBtn) {
                    statusBtn.textContent = newStatus;
                }
                
                if (newStatus === 'Published') {
                    row.classList.add('published');
                } else {
                    row.classList.remove('published');
                }
                
                const catSelect = row.querySelector('.cat select');
                const editorSelect = row.querySelector('.editor select');
                if (newStatus === 'Published') {
                    if (catSelect) catSelect.disabled = true;
                    if (editorSelect) editorSelect.disabled = true;
                } else {
                    if (catSelect) catSelect.disabled = false;
                    if (editorSelect) editorSelect.disabled = false;
                }
                
                const actionsCell = row.querySelector('.actions');
                if (newStatus === 'Published') {
                    actionsCell.innerHTML = `<button onclick="markComplete(${articleId})" style="color:green;">Mark Complete</button>`;
                } else {
                    actionsCell.innerHTML = `
                        <button onclick="toggleEdit(${articleId})" id="edit-btn-${articleId}">Edit</button>
                        <button onclick="deleteArticle(${articleId})" style="color:red;">Delete</button>
                    `;
                }
            }
        } else {
            alert('Failed to update status');
        }
    } catch (err) {
        console.error('Error updating status:', err);
        alert('Failed to update status');
    }
}
