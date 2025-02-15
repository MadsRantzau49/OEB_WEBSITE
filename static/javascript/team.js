document.querySelectorAll(".fine_dropdown").forEach(dropdown => {
    dropdown.addEventListener("change", function() {
        const fine = this.value.split("|~");
        const row = this.closest("tr"); // Find the closest table row
        
        row.querySelector(".fine_id").value = fine[0];
        row.querySelector(".fine_name").value = fine[1];
        row.querySelector(".fine_description").value = fine[2];
        row.querySelector(".fine_amount").value = fine[3];
    });
});


document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("table").forEach((table) => {
        let headers = table.querySelectorAll("th");
        
        headers.forEach((header, columnIndex) => {
            let asc = false; // Start with descending order
            header.style.cursor = "pointer";
            header.addEventListener("click", () => {
                let tbody = table.querySelector("tbody");
                let rows = Array.from(tbody.querySelectorAll("tr"));
                
                rows.sort((rowA, rowB) => {
                    let cellA = rowA.cells[columnIndex].querySelector("input[type='submit']") ? rowA.cells[columnIndex].querySelector("input[type='submit']").value.trim() : rowA.cells[columnIndex].innerText.trim();
                    let cellB = rowB.cells[columnIndex].querySelector("input[type='submit']") ? rowB.cells[columnIndex].querySelector("input[type='submit']").value.trim() : rowB.cells[columnIndex].innerText.trim();
                    
                    if (!isNaN(cellA) && !isNaN(cellB)) {
                        return asc ? cellA - cellB : cellB - cellA;
                    }
                    return asc ? cellA.localeCompare(cellB) : cellB.localeCompare(cellA);
                });
                
                asc = !asc;
                tbody.innerHTML = "";
                rows.forEach(row => tbody.appendChild(row));
            });
        });
        
        let searchBox = document.createElement("input");
        searchBox.type = "text";
        searchBox.placeholder = "Søg...";
        searchBox.style.marginBottom = "10px";
        table.parentElement.insertBefore(searchBox, table);
        
        searchBox.addEventListener("input", () => {
            let filter = searchBox.value.toLowerCase();
            let rows = table.querySelectorAll("tbody tr");
            
            rows.forEach(row => {
                let text = row.innerText.toLowerCase() + Array.from(row.querySelectorAll("input[type='submit']")).map(input => input.value.toLowerCase()).join(" ");
                row.style.display = text.includes(filter) ? "" : "none";
            });
        });
    });
});
