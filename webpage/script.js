function send_query(event){
    event.preventDefault();
    const input = document.getElementById("query");
    const queryValue = input.value.trim();
    input.value = ""
    add_user_message(queryValue)
    if (queryValue === "") {
        return;
    }

    const params = new URLSearchParams({ query: queryValue.toLowerCase() });
    fetch("http://127.0.0.1:1616/?"+ params.toString(), {
        method: "GET"
    })
        .then(response => response.json())
        .then(data => {
            const message = data.response;
            add_bot_message(message)
            const chatContainer = document.querySelector(".chat-container");
            chatContainer.scrollTop = chatContainer.scrollHeight;
        })
        .catch(error => console.error("Hata oluştu:", error));
}

function add_bot_message(response){
    const container = document.querySelector(".message-container");

    const messageDiv = document.createElement("div");
    messageDiv.className = "chat-message";

    const icon = document.createElement("i");
    icon.className = "fa-solid fa-robot";

    const messageText = document.createElement("p");
    messageText.innerHTML = marked.parse(response); // JSON'dan gelen metni ekle
    // Yapıyı birleştir
    messageDiv.appendChild(icon);
    messageDiv.appendChild(messageText);
    container.appendChild(messageDiv); 
}


function add_user_message(response){
    const container = document.querySelector(".message-container");

    const messageDiv = document.createElement("div");
    messageDiv.className = "user-message";

    const icon = document.createElement("i");
    icon.className = "fa-solid fa-user";

    const messageText = document.createElement("p");
    messageText.textContent = response; // JSON'dan gelen metni ekle

    // Yapıyı birleştir
    messageDiv.appendChild(icon);
    messageDiv.appendChild(messageText);
    container.appendChild(messageDiv); 
}