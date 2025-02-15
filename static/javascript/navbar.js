document.addEventListener("DOMContentLoaded", function () {
    const container = document.querySelector(".container");
    const dividers = document.querySelectorAll(".divider");
    const nav = document.createElement("nav");
    nav.classList.add("dynamic-nav");

    const menuToggle = document.createElement("div");
    menuToggle.classList.add("menu-toggle");
    menuToggle.innerHTML = "☰";

    const ul = document.createElement("ul");

    dividers.forEach((divider, index) => {
        const title = divider.querySelector("h2");
        if (title) {
            const li = document.createElement("li");
            const a = document.createElement("a");
            const id = `section-${index}`;

            divider.setAttribute("id", id);
            a.href = `#${id}`;
            a.textContent = title.textContent;

            a.addEventListener("click", (event) => {
                event.preventDefault();
                document.getElementById(id).scrollIntoView({ behavior: "smooth" });
                ul.classList.remove("show"); // Close menu on selection
            });

            li.appendChild(a);
            ul.appendChild(li);
        }
    });

    menuToggle.addEventListener("click", () => {
        ul.classList.toggle("show"); // Toggle mobile menu
    });

    nav.appendChild(menuToggle);
    nav.appendChild(ul);
    document.body.insertBefore(nav, container);
});
