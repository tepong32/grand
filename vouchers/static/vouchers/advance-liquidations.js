(() => {
  const button = document.getElementById("advance-add-expense");
  if (!button) return;
  button.addEventListener("click", () => {
    const count = document.getElementById("id_expenses-TOTAL_FORMS");
    const index = Number(count.value);
    if (!Number.isInteger(index) || index >= 100) return;
    const html = document.getElementById("advance-empty-expense").innerHTML.replaceAll("__prefix__", String(index));
    document.getElementById("advance-expenses").insertAdjacentHTML("beforeend", html);
    count.value = String(index + 1);
  });
})();
