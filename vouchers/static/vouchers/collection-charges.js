(() => {
  const button = document.getElementById('add-collection-charge');
  const total = document.getElementById('id_charges-TOTAL_FORMS');
  const maximum = document.getElementById('id_charges-MAX_NUM_FORMS');
  const rows = document.getElementById('collection-charges');
  const template = document.getElementById('collection-charge-template');
  if (!button || !total || !rows || !template) return;
  button.addEventListener('click', () => {
    const index = Number(total.value);
    if (maximum && index >= Number(maximum.value)) return;
    const fragment = template.content.cloneNode(true);
    fragment.querySelectorAll('[name], [id], label[for]').forEach(element => {
      ['name', 'id', 'for'].forEach(attribute => {
        const value = element.getAttribute(attribute);
        if (value) element.setAttribute(attribute, value.replaceAll('__prefix__', String(index)));
      });
    });
    rows.appendChild(fragment);
    total.value = String(index + 1);
    button.disabled = Boolean(maximum && index + 1 >= Number(maximum.value));
  });
})();
