(() => {
  'use strict';
  const node = document.getElementById('forecast-editor-data');
  if (!node) return;
  const data = JSON.parse(node.textContent), host = document.getElementById('forecast-editor');
  host.style.overflowWrap = 'anywhere';
  const form = document.getElementById('forecast-intake'), output = document.getElementById('id_allocation');
  const uid = prefix => prefix + '-' + crypto.randomUUID();
  const blank = source => ({id: uid('c'), source_id: source.id, amount: source.amount,
    disposition: 'unresolved', category: '', account_id: '', funding_reference: '', overlap_of: '', basis: ''});
  const declarations = () => data.categories.map(row => ({category: row.key, coverage: 'unresolved', basis: ''}));
  let state = data.allocation || {half_sources: [], entities: data.entities.map(entity => ({entity_key: entity.key,
    half_components: [], proposed_components: data.resources.map(blank),
    coverage: {half_estimate: declarations(), proposed: declarations()}}))};
  if (!state || !Array.isArray(state.half_sources) || !Array.isArray(state.entities)) {
    host.textContent = 'The entered schedule could not be restored. Reload this preparation before continuing.';
    form.addEventListener('submit', event => event.preventDefault()); return;
  }
  let activeEntity = data.entities[0].key, page = 1, search = '', column = 'proposed';
  const el = (tag, text, css) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (css) element.className = css;
    return element;
  };
  const button = (text, action, css = 'btn btn-outline-secondary btn-sm') => {
    const result = el('button', text, css); result.type = 'button'; result.style.maxWidth = '100%';
    result.style.whiteSpace = 'normal'; result.addEventListener('click', action); return result;
  };
  const field = (parent, label, row, key, choices = null, type = 'text') => {
    const wrap = el('label', label, 'd-block mb-2');
    const input = el(choices ? 'select' : key === 'basis' ? 'textarea' : 'input');
    input.className = 'form-control';
    if (choices) {
      for (const choice of choices) { const option = el('option', choice.label); option.value = choice.key; input.append(option); }
    } else if (key === 'basis') input.rows = 2;
    else input.type = type;
    input.value = row[key] == null ? '' : row[key];
    if (key === 'amount') input.inputMode = 'decimal';
    if (key === 'basis') input.maxLength = 1600;
    if (key === 'funding_reference') input.maxLength = 255;
    input.addEventListener('input', () => { row[key] = input.value; output.value = JSON.stringify(state); });
    wrap.append(input); parent.append(wrap); return input;
  };
  const save = () => { output.value = JSON.stringify(state); };
  const member = () => state.entities.find(row => row.entity_key === activeEntity);
  const sourceRows = () => column === 'proposed' ? data.resources : state.half_sources;
  const componentRows = () => member()[column === 'proposed' ? 'proposed_components' : 'half_components'];
  const sourceLabel = source => column === 'proposed'
    ? `${source.reference} · ${source.description} · ${source.fund}` : source.reference || 'Second-half worksheet';
  const categories = [{key: '', label: 'Choose receipt category'}, ...data.categories];
  const accounts = () => [{key: '', label: 'Choose original account'}, ...data.accounts.filter(row => row.columns.includes(column)).map(row => ({key: row.id, label: row.label}))];
  const dispositions = [{key: 'unresolved', label: 'Needs classification'}, {key: 'include', label: 'Include forecast'},
    {key: 'overlap', label: 'Overlap an included counterpart'}, {key: 'exclude', label: 'Exclude with basis'}];

  function worksheets(parent) {
    parent.append(el('h2', 'Dated second-half worksheets', 'h4'));
    parent.append(el('p', 'These sources are shared by all entities. Allocate each full amount explicitly; repeated entity schedules do not create extra capacity.'));
    for (const source of state.half_sources) {
      const card = el('div', undefined, 'border rounded p-3 mb-3');
      field(card, 'Worksheet reference', source, 'reference'); field(card, 'Original forecast amount', source, 'amount');
      field(card, 'Observed as of', source, 'as_of', null, 'date'); field(card, 'Dated forecast basis', source, 'basis');
      card.append(button('Update amount in unsplit rows', () => {
        for (const entity of state.entities) {
          const rows = entity.half_components.filter(row => row.source_id === source.id);
          if (rows.length === 1) rows[0].amount = source.amount;
        }
        save(); render();
      }));
      card.append(button('Remove worksheet and its entity components', () => {
        if (!window.confirm('Remove this worksheet and all of its forecast components?')) return;
        state.half_sources = state.half_sources.filter(row => row.id !== source.id);
        for (const entity of state.entities) entity.half_components = entity.half_components.filter(row => row.source_id !== source.id);
        save(); render();
      })); parent.append(card);
    }
    parent.append(button('Add second-half worksheet', () => {
      const source = {id: uid('h'), amount: '', reference: '', as_of: '', basis: ''};
      state.half_sources.push(source);
      for (const entity of state.entities) entity.half_components.push(blank(source));
      save(); render();
    }));
  }

  function componentCard(parent, source, component, index) {
    const card = el('div', undefined, 'border rounded p-3 mb-2');
    card.append(el('h4', `Component ${index + 1}`, 'h6'));
    const choice = field(card, 'Treatment', component, 'disposition', dispositions);
    choice.addEventListener('change', () => {
      if (component.disposition === 'exclude') Object.assign(component, {category: '', account_id: '', funding_reference: '', overlap_of: ''});
      if (component.disposition !== 'overlap') component.overlap_of = '';
      save(); render();
    });
    field(card, 'Component amount', component, 'amount');
    if (component.disposition !== 'exclude') {
      field(card, 'Receipt category', component, 'category', categories);
      field(card, 'Original Accounting account', component, 'account_id', accounts());
      field(card, 'Funding coverage reference', component, 'funding_reference');
    }
    if (component.disposition === 'overlap') {
      const anchors = componentRows().filter(row => row.disposition === 'include' && row.source_id !== source.id);
      const choices = [{key: '', label: 'Choose exact included counterpart'}, ...anchors.map(row => {
        const original = sourceRows().find(item => item.id === row.source_id);
        return {key: row.id, label: `${original ? sourceLabel(original) : 'Missing source'} · ${row.amount} · ${row.funding_reference}`};
      })];
      const select = field(card, 'Included counterpart', component, 'overlap_of', choices);
      select.addEventListener('change', () => {
        const anchor = anchors.find(row => row.id === component.overlap_of);
        if (anchor) Object.assign(component, {amount: anchor.amount, category: anchor.category,
          account_id: anchor.account_id, funding_reference: anchor.funding_reference});
        save(); render();
      });
      card.append(el('p', 'Choosing a counterpart copies its exact amount and mapping. Partition the rest of this source separately and record why the amounts overlap.'));
    }
    field(card, 'Mapping, exclusion or overlap basis', component, 'basis');
    card.append(button('Remove component', () => {
      const rows = componentRows(), position = rows.indexOf(component);
      if (rows.filter(row => row.source_id === source.id).length === 1) return;
      rows.splice(position, 1); save(); render();
    })); parent.append(card);
  }

  function coverage(parent) {
    parent.append(el('h3', 'Complete category declarations', 'h5'));
    const bulk = el('div', undefined, 'border rounded p-3 mb-3');
    const basis = {basis: ''}; field(bulk, 'Basis for confirming the complete category schedule', basis, 'basis');
    bulk.append(button('Confirm mapped estimates and remaining categories with no estimate', () => {
      if (!basis.basis.trim()) { window.alert('Enter the complete category coverage basis first.'); return; }
      for (const row of member().coverage[column]) {
        row.coverage = componentRows().some(item => item.disposition === 'include' && item.category === row.category) ? 'estimate' : 'no_estimate';
        row.basis = basis.basis;
      }
      save(); render();
    }));
    bulk.append(el('p', 'This explicit confirmation includes zero-valued mapped estimates. It does not resolve unclassified components. Review each declaration below.'));
    parent.append(bulk);
    for (const row of member().coverage[column]) {
      const section = el('details', undefined, 'mb-2');
      const label = data.categories.find(item => item.key === row.category);
      section.append(el('summary', `${label ? label.label : row.category} · ${row.coverage.replaceAll('_', ' ')}`));
      field(section, 'Coverage', row, 'coverage', [{key: 'unresolved', label: 'Needs confirmation'},
        {key: 'estimate', label: 'Mapped estimate, including zero'}, {key: 'no_estimate', label: 'No estimate in the complete source schedule'}]);
      field(section, 'Category coverage basis', row, 'basis'); parent.append(section);
    }
  }

  function render() {
    host.replaceChildren(); worksheets(host);
    host.append(el('h2', 'Entity source allocation', 'h4 mt-4'));
    const selection = {entity: activeEntity, column};
    const entityInput = field(host, 'Reporting entity', selection, 'entity', data.entities.map(row => ({key: row.key, label: row.label})));
    entityInput.addEventListener('change', () => { activeEntity = selection.entity; page = 1; render(); });
    const columnInput = field(host, 'Forecast column', selection, 'column', [{key: 'proposed', label: 'Budget-year proposed receipts'},
      {key: 'half_estimate', label: 'Current second-half estimates'}]);
    columnInput.addEventListener('change', () => { column = selection.column; page = 1; render(); });
    if (!member()) { host.append(el('p', 'An entity schedule is missing. Reload the full current source inventory.')); return; }
    const filtered = sourceRows().filter(source => sourceLabel(source).toLocaleLowerCase().includes(search.toLocaleLowerCase()));
    const filter = {search}; const input = field(host, 'Find worksheet or financing source', filter, 'search');
    input.addEventListener('change', () => { search = filter.search; page = 1; render(); });
    const count = Math.max(1, Math.ceil(filtered.length / 25)); page = Math.min(page, count);
    const unresolved = componentRows().filter(row => row.disposition === 'unresolved').length;
    host.append(el('p', `${sourceRows().length} complete sources · ${filtered.length} matching sources · ${unresolved} unresolved components. Paging and search preserve every source and entity in the package.`));
    for (const source of filtered.slice((page - 1) * 25, page * 25)) {
      const section = el('section', undefined, 'border rounded p-3 mb-4');
      section.append(el('h3', sourceLabel(source), 'h5'));
      section.append(el('p', `Original amount: ${source.amount || 'Required'} · ${source.basis || 'Basis required'}`));
      componentRows().filter(row => row.source_id === source.id).forEach((row, index) => componentCard(section, source, row, index));
      section.append(button('Add split component', () => { componentRows().push(blank({id: source.id, amount: '0.00'})); save(); render(); }));
      host.append(section);
    }
    const paging = el('div', undefined, 'mb-4');
    if (page > 1) paging.append(button('Previous sources', () => { page--; render(); }));
    paging.append(el('span', ` Page ${page} of ${count} `));
    if (page < count) paging.append(button('Next sources', () => { page++; render(); }));
    host.append(paging); coverage(host); save();
  }
  form.addEventListener('submit', save); render();
})();
