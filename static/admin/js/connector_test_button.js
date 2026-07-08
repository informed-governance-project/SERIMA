function getCsrfToken() {
    const input = document.querySelector("input[name=csrfmiddlewaretoken]");
    if (input) {
        return input.value;
    }
    return document.cookie.match(/csrftoken=([^;]+)/)?.[1] ?? "";
}


function testConnectorConnection(url) {
    const result = document.getElementById("connector-test-result");
    result.textContent = gettext("Testing…");
    result.style.color = "#666";
    fetch(url, {
        method: "POST",
        headers: {
            "X-CSRFToken": getCsrfToken(),
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
    const button = event.target.closest(".connector-test-btn");
    if (!button) return;

    const url = button.dataset.url;
    testConnectorConnection(url);
});
