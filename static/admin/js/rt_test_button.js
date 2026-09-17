function testRTConnection(url) {
    const result = document.getElementById("rt-test-result");
    result.textContent = gettext("Testing…");
    result.style.color = "#666";

    fetch(url, {
        method: "POST",
        headers: {
            "X-CSRFToken": document.querySelector("input[name=csrfmiddlewaretoken]").value,
        },
    })
    .then(r => r.json())
    .then(data => {
        result.textContent = data.message;
        result.style.color = data.success ? "green" : "red";
    })
    .catch(() => {
        result.textContent = gettext("Request failed.");
        result.style.color = "red";
    });
}


document.addEventListener("click", function (event) {
    const button = event.target.closest(".rt-test-btn");
    if (!button) return;

    const url = button.dataset.url;
    testRTConnection(url);
});
