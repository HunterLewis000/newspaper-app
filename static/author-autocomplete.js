const authorInput = document.getElementById('authorInput');
const suggestionsList = document.getElementById('authorSuggestions');
let selectedSuggestion = -1;

authorInput.addEventListener('input', () => {
    const query = authorInput.value.trim();
    selectedSuggestion = -1;

    if (query.length < 1) {
        suggestionsList.innerHTML = '';
        return;
    }

    fetch(`/api/users/search?q=${encodeURIComponent(query)}&limit=5`)
        .then(r => r.json())
        .then(users => {
            if (users.length === 0) {
                suggestionsList.innerHTML = '';
                return;
            }

            suggestionsList.innerHTML = users.map((user, idx) => `
                <li data-index="${idx}" data-name="${user.name}" onclick="selectAuthor(this)">
                    <div class="suggestion-name">${highlightMatch(user.name, query)}</div>
                    <div class="suggestion-email">${user.email}</div>
                </li>
            `).join('');
        })
        .catch(err => console.error('Autocomplete error:', err));
});

authorInput.addEventListener('keydown', (e) => {
    const items = suggestionsList.querySelectorAll('li');

    if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedSuggestion = Math.min(selectedSuggestion + 1, items.length - 1);
        updateSelection(items);
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedSuggestion = Math.max(selectedSuggestion - 1, -1);
        updateSelection(items);
    } else if (e.key === 'Enter') {
        if (selectedSuggestion >= 0 && items[selectedSuggestion]) {
            e.preventDefault();
            selectAuthor(items[selectedSuggestion]);
        }
    } else if (e.key === 'Escape') {
        suggestionsList.innerHTML = '';
    }
});

function updateSelection(items) {
    items.forEach((item, idx) => {
        if (idx === selectedSuggestion) {
            item.classList.add('selected');
            item.scrollIntoView({ block: 'nearest' });
        } else {
            item.classList.remove('selected');
        }
    });
}

function selectAuthor(element) {
    const name = element.getAttribute('data-name');
    authorInput.value = name;
    suggestionsList.innerHTML = '';
    selectedSuggestion = -1;
}

function highlightMatch(text, query) {
    const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    return text.replace(regex, '<strong>$1</strong>');
}

document.addEventListener('click', (e) => {
    if (e.target !== authorInput && !suggestionsList.contains(e.target)) {
        suggestionsList.innerHTML = '';
    }
});
