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