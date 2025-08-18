document.addEventListener("DOMContentLoaded", function() {
    // Make fines dropdown searchable
    const fineDropdown = document.querySelector(".fine_dropdown");
    const fineChoices = new Choices(fineDropdown, {
        searchEnabled: true,
        itemSelectText: '',
        shouldSort: false,
        placeholder: true,
        placeholderValue: 'Søg bøder...',
    });

    fineDropdown.addEventListener("change", function() {
        const fine = this.value.split("|~");
        const form = this.closest("form");
        form.querySelector(".fine_id").value = fine[0];
        form.querySelector(".fine_name").value = fine[1];
        form.querySelector(".fine_description").value = fine[2];
        form.querySelector(".fine_amount").value = fine[3];
    });

    // Make players dropdown searchable and multi-select
    const playerDropdown = document.querySelector(".player_dropdown");
    const playerChoices = new Choices(playerDropdown, {
        searchEnabled: true,
        removeItemButton: true, // allow removing selected players
        placeholder: true,
        placeholderValue: 'Søg spillere...',
    });
});


// Custom searchable dropdown for players
document.querySelectorAll(".fine-select-wrapper").forEach(wrapper => {
    const searchInput = wrapper.querySelector(".fine-search");
    const hiddenInput = wrapper.querySelector("input.fine_dropdown"); 
    const options = wrapper.querySelectorAll(".fine-option");

    searchInput.addEventListener("input", function() {
        const query = this.value.toLowerCase();
        options.forEach(opt => {
            opt.style.display = opt.textContent.toLowerCase().includes(query) ? "block" : "none";
        });
    });

    options.forEach(opt => {
        opt.addEventListener("click", function() {
            hiddenInput.value = this.dataset.value;
            searchInput.value = this.textContent;
        });
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
