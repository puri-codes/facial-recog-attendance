/**
 * Client-side table sorting and search.
 * Auto-applies to any table with class "data-table".
 */
(function () {
    'use strict';

    // Sort table by column
    function sortTable(table, colIndex, ascending) {
        const tbody = table.querySelector('tbody');
        const rows = Array.from(tbody.querySelectorAll('tr'));

        rows.sort((a, b) => {
            const aCell = a.cells[colIndex];
            const bCell = b.cells[colIndex];
            if (!aCell || !bCell) return 0;

            let aVal = aCell.textContent.trim().toLowerCase();
            let bVal = bCell.textContent.trim().toLowerCase();

            // Try numeric sort
            const aNum = parseFloat(aVal.replace(/[^\d.-]/g, ''));
            const bNum = parseFloat(bVal.replace(/[^\d.-]/g, ''));

            if (!isNaN(aNum) && !isNaN(bNum)) {
                return ascending ? aNum - bNum : bNum - aNum;
            }

            return ascending ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
        });

        rows.forEach(row => tbody.appendChild(row));
    }

    // Apply sorting to all data tables
    document.querySelectorAll('.data-table').forEach(table => {
        const headers = table.querySelectorAll('th');
        headers.forEach((th, index) => {
            th.addEventListener('click', () => {
                const isAsc = th.classList.contains('sorted-asc');

                // Reset all
                headers.forEach(h => h.classList.remove('sorted-asc', 'sorted-desc'));

                if (isAsc) {
                    th.classList.add('sorted-desc');
                    sortTable(table, index, false);
                } else {
                    th.classList.add('sorted-asc');
                    sortTable(table, index, true);
                }
            });
        });
    });

    // Client-side search for tables with id
    const searchInputs = document.querySelectorAll('[data-table-search]');
    searchInputs.forEach(input => {
        const tableId = input.getAttribute('data-table-search');
        const table = document.getElementById(tableId);
        if (!table) return;

        input.addEventListener('input', () => {
            const query = input.value.toLowerCase();
            const rows = table.querySelectorAll('tbody tr');
            rows.forEach(row => {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(query) ? '' : 'none';
            });
        });
    });
})();
