// Search and filter the actual server-rendered rows, without changing job data.
document.querySelectorAll("[data-filter-region]").forEach((region) => {
  const search = region.querySelector("[data-search]");
  const stateFilter = region.querySelector("[data-state-filter]");
  const rows = [...region.querySelectorAll("[data-search-row]")];
  const empty = region.querySelector("[data-filter-empty]");
  const filter = () => {
    const query = search.value.trim().toLocaleLowerCase();
    const state = stateFilter.value;
    let count = 0;
    rows.forEach((row) => {
      const matches = row.textContent.toLocaleLowerCase().includes(query)
        && (!state || row.dataset.state === state);
      row.hidden = !matches;
      if (matches) count++;
    });
    empty.hidden = count > 0;
  };
  search.addEventListener("input", filter);
  stateFilter.addEventListener("change", filter);
  empty.setAttribute("role", "status");
});
