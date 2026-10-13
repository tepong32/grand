/* Keep every original share and coverage cell in memory while paging. */
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('spa-editor-data').textContent);
  const form = document.getElementById('spa-intake');
  const parts = data.parts || data.shares.map((share, index) => ({
    key: `spa-${index + 1}`, allocation: share.allocation, amount: share.amount,
    subdivision: 'unresolved', basis: ''
  }));
  const coverage = data.coverage || data.matrix.map(cell => ({
    entity: cell.entity, column: cell.column, subdivision: cell.subdivision,
    coverage: 'missing', basis: ''
  }));
  let nextKey = 1;
  const make = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  const sync = () => {
    document.getElementById('id_parts').value = JSON.stringify(parts);
    document.getElementById('id_coverage').value = JSON.stringify(coverage);
  };
  function field(card, title, value, change, options) {
    const label = make('label', title, 'd-block mb-2');
    const input = make(options ? 'select' : 'input', undefined, 'form-control');
    if (options) for (const [key, text] of options) {
      const option = make('option', text); option.value = key; input.append(option);
    }
    input.value = value;
    input.addEventListener(options ? 'change' : 'input', () => { change(input.value); sync(); });
    label.append(input); card.append(label);
  }
  function pager(root, values, size, draw) {
    let page = 0;
    function render() {
      root.replaceChildren();
      const count = Math.max(1, Math.ceil(values.length / size));
      page = Math.min(page, count - 1);
      const nav = make('nav', undefined, 'd-flex gap-2 align-items-center mb-3');
      nav.setAttribute('aria-label', root.id === 'spa-parts' ? 'SPA share pages' : 'SPA coverage pages');
      for (const [text, delta] of [['Previous', -1], ['Next', 1]]) {
        const button = make('button', text, 'btn btn-outline-secondary'); button.type = 'button';
        button.disabled = delta < 0 ? page === 0 : page === count - 1;
        button.addEventListener('click', () => { page += delta; render(); }); nav.append(button);
      }
      nav.append(make('span', `${values.length} rows · page ${page + 1} of ${count}`)); root.append(nav);
      for (const row of values.slice(page * size, (page + 1) * size)) draw(root, row, render);
    }
    render();
  }
  pager(document.getElementById('spa-parts'), data.shares, 10, (root, share, render) => {
    const card = make('section', undefined, 'card card-body mb-3');
    card.append(make('h3', `${share.entity} · ${share.column}`, 'h5'));
    card.append(make('p', `${share.amount} · reporting code ${share.reporting_code} · ${share.source}`));
    card.append(make('p', `Original share ${share.allocation}`));
    for (const part of parts.filter(row => row.allocation === share.allocation)) {
      const box = make('div', undefined, 'border p-2 mb-2');
      field(box, 'Signed amount', part.amount, value => { part.amount = value; });
      field(box, 'Subdivision', part.subdivision, value => { part.subdivision = value; },
        [['unresolved', 'Unresolved'], ...Object.entries(data.subdivisions)]);
      field(box, 'Original source treatment basis', part.basis, value => { part.basis = value; });
      const remove = make('button', 'Remove part', 'btn btn-outline-secondary'); remove.type = 'button';
      remove.addEventListener('click', () => { parts.splice(parts.indexOf(part), 1); sync(); render(); });
      box.append(remove); card.append(box);
    }
    const add = make('button', 'Add explicit split part', 'btn btn-outline-primary'); add.type = 'button';
    add.addEventListener('click', () => {
      let key; do { key = `spa-added-${nextKey++}`; } while (parts.some(part => part.key === key));
      parts.push({key, allocation: share.allocation, amount: '', subdivision: 'unresolved', basis: ''});
      sync(); render();
    });
    card.append(add); root.append(card);
  });
  pager(document.getElementById('spa-coverage'), data.matrix, 12, (root, cell) => {
    const row = coverage.find(item => item.entity === cell.entity && item.column === cell.column && item.subdivision === cell.subdivision);
    const card = make('section', undefined, 'card card-body mb-2');
    card.append(make('h3', `${cell.entity_label} · ${cell.column_label} · ${cell.label}`, 'h6'));
    card.append(make('p', `Original SPA class control: ${cell.original_control === null ? 'Unknown' : cell.original_control}`));
    if (!row) { card.append(make('p', 'Missing submitted cell. Reload the original source to restore it.')); }
    else {
      field(card, 'Coverage', row.coverage, value => { row.coverage = value; },
        cell.original_control === null ? [['missing', 'Missing original coverage']] : [['missing', 'Missing'], ['complete', 'Complete with evidence']]);
      field(card, 'Coverage evidence basis', row.basis, value => { row.basis = value; });
    }
    root.append(card);
  });
  sync(); form.addEventListener('submit', sync);
})();
