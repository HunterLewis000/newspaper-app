document.addEventListener("DOMContentLoaded", () => {
    const tbody = document.getElementById("articles-tbody");

    new Sortable(tbody, {
        handle: ".drag-handle",  
        animation: 150,
        onEnd: () => {
            const order = [...tbody.querySelectorAll("tr")].map(row => row.dataset.id);
            
            fetch("/update_order", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ order })
            })
            .then(res => res.json())
            .then(data => {
                if (data.success) {
                    socket.emit("update_article_order", { order });
                }
            });
        }
    });
});
