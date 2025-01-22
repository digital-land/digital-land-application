const table = document.querySelector(".app-table--sortable");
const tableHeads = Array.from(document.querySelectorAll("thead th[data-sort]"));

tableHeads.forEach((tableHead, index) =>
  tableHead.addEventListener("click", e =>
    sortTable(index, e.target, tableHead.dataset.sort)
  )
);

function sortTable(index, target, dir) {
  const tableBody = table.querySelector("tbody");
  const rows = Array.from(table.querySelectorAll("tbody tr"));
  const dataCols = rows.map(row => row.querySelectorAll("td")[index]);
  const fragment = document.createDocumentFragment();

  const sortedRows = dataCols
    .sort((last, next) =>
      dir === "desc"
        ? next.textContent.localeCompare(last.textContent)
        : last.textContent.localeCompare(next.textContent)
    )
    .map(col => col.parentNode);

  sortedRows.forEach(row => fragment.appendChild(row));
  tableBody.innerHTML = "";
  tableBody.appendChild(fragment);

  tableHeads.forEach(tableHead =>
    tableHead === target
      ? (tableHead.dataset.sort = dir === "desc" ? "asc" : "desc")
      : (tableHead.dataset.sort = "none")
  );
}
