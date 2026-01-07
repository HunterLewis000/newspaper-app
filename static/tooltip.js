(function(){
  const HOVER_DELAY = 800;
  let hoverTimer = null;
  let currentCell = null;

  const tooltip = document.createElement('div');
  tooltip.className = 'title-tooltip';
  document.body.appendChild(tooltip);

  function showTooltipFor(cell) {
    const text = cell.textContent?.trim();
    if (!text) return;
    tooltip.textContent = text;
    tooltip.style.display = 'block';

    requestAnimationFrame(() => {
      const rect = cell.getBoundingClientRect();
      const ttRect = tooltip.getBoundingClientRect();
  
      let top = rect.top - ttRect.height - 8;
      if (top < 8) top = rect.bottom + 8;

      let left = rect.left;
      if (left + ttRect.width > window.innerWidth - 8) {
        left = Math.max(8, window.innerWidth - ttRect.width - 8);
      }
      tooltip.style.top = `${Math.round(top)}px`;
      tooltip.style.left = `${Math.round(left)}px`;
    });
  }

  function hideTooltip() {
    tooltip.style.display = 'none';
    tooltip.textContent = '';
  }

  document.addEventListener('mouseover', (e) => {
    const cell = e.target.closest('td.title, th.title');
    if (!cell) return;
    
    const isOverflowing = cell.scrollWidth > cell.clientWidth;
    if (!isOverflowing) return;
    currentCell = cell;
    hoverTimer = setTimeout(() => {
      showTooltipFor(cell);
      hoverTimer = null;
    }, HOVER_DELAY);
  });

  document.addEventListener('mouseout', (e) => {
    const related = e.relatedTarget;
    const cell = e.target.closest('td.title, th.title');
    if (hoverTimer) { clearTimeout(hoverTimer); hoverTimer = null; }
    if (cell && (!related || !related.closest || !related.closest('td.title, th.title'))) {
      hideTooltip();
      currentCell = null;
    }
  });

  ['scroll','resize','touchstart'].forEach(evt => {
    window.addEventListener(evt, () => {
      if (hoverTimer) { clearTimeout(hoverTimer); hoverTimer = null; }
      hideTooltip();
    }, { passive: true });
  });

  document.addEventListener('focusin', (e) => {
    const cell = e.target.closest && e.target.closest('td.title, th.title');
    if (!cell) return;
    const isOverflowing = cell.scrollWidth > cell.clientWidth;
    if (!isOverflowing) return;
    hoverTimer = setTimeout(() => showTooltipFor(cell), 350);
  });

  document.addEventListener('focusout', (e) => {
    if (hoverTimer) { clearTimeout(hoverTimer); hoverTimer = null; }
    hideTooltip();
  });
})();
