document.addEventListener("DOMContentLoaded", () => {
    // === 1. CATCHING DOM ELEMENTS ===
    const sendButton = document.getElementById("send-button");
    const chatInput = document.getElementById("chat-input");
    const historyList = document.getElementById("history-list");
    const chatLog = document.getElementById("chat-log-area");
    const newChatButton = document.querySelector(".new-chat-btn");
    const clearAllButton = document.querySelector(".clear-all"); 

    const emptyChatPlaceholder = `
        <div class="empty-chat-placeholder">
            <i class="fa-solid fa-robot"></i>
            <h2>Hello! I am your Enviro-Edu Assistant. How may I assist you today?</h2>
        </div>
    `;

    // === 2. APPLICATION MAIN DATA (STATE) ===
    let conversations = {};
    let currentConversationId = null;
    let currentUserId = getOrCreateUserId();

    // === 3. EVENT LISTENERS ===
    newChatButton.addEventListener("click", (e) => {
        e.preventDefault();
        startNewChat();
    });
    sendButton.addEventListener("click", sendMessage);
    chatInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    });
    historyList.addEventListener("click", (e) => {
        const clickedLi = e.target.closest("li");
        if (clickedLi) {
            const id = clickedLi.dataset.id;
            switchConversation(id);
        }
    });
    
    // <-- NEW LISTENER FOR “CLEAR ALL” ---
    clearAllButton.addEventListener("click", (e) => {
        e.preventDefault();
        clearAllConversations();
    });

    // === 4. MAIN FUNCTIONS ===

    /**
     * NEW FEATURE: Delete all conversations
     */
    async function clearAllConversations() {
        if (!confirm("Are you sure you want to delete all conversations? This action cannot be undone.")) {
            return;
        }

        try {
            const response = await fetch("http://localhost:5000/api/conversations", {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ userId: currentUserId }) // Send userID to be deleted
            });

            if (!response.ok) {
                throw new Error("Failed to delete history on the server.");
            }
            
            // If the server is successful, clear the frontend state
            conversations = {};
            startNewChat(); // This will clear the UI (render history & chat log).
            
            console.log("All conversations have been successfully deleted.");

        } catch (error) {
            console.error("Error clearing conversations:", error);
            alert("An error occurred while deleting history.");
        }
    }
    
    // ... (The functions getOrCreateUserId, startNewChat, sendMessage, etc. remain exactly the same) ...
    
    function getOrCreateUserId() {
        let userId = localStorage.getItem('anonymousUserId');
        if (!userId) {
            userId = 'anon-' + Date.now() + '-' + Math.floor(Math.random() * 1000);
            localStorage.setItem('anonymousUserId', userId);
        }
        return userId;
    }

    function startNewChat() {
        currentConversationId = null;
        chatInput.value = "";
        renderChatLog();
        renderHistory();
    }

    async function sendMessage() {
        const messageText = chatInput.value.trim();
        if (messageText === "") return;

        let conversationIdToSend = currentConversationId; 
        let tempId = null;
        let activeConversation;

        if (currentConversationId === null) {
            const title = messageText.length > 28 ? messageText.substring(0, 28) + "..." : messageText;
            tempId = "temp-" + Date.now();
            activeConversation = {
                id: tempId,
                title: title,
                messages: []
            };
            conversations[tempId] = activeConversation;
            currentConversationId = tempId;
        } else {
            activeConversation = conversations[currentConversationId];
        }

        activeConversation.messages.push({ role: "user", content: messageText });
        renderChatLog();
        renderHistory();
        chatInput.value = "";
        
        const loadingDiv = addMessageToLog("assistant", "...");
        chatLog.scrollTop = chatLog.scrollHeight;
        
        try {
            const response = await fetch("http://localhost:5000/api/chat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    message: messageText,
                    userId: currentUserId,
                    conversationId: conversationIdToSend
                })
            });

            if (!response.ok) throw new Error("Network response was not ok.");
            const data = await response.json();
            if (data.error) throw new Error(data.error);

            const botText = data.answer;
            const realConversationId = data.conversationId;

            activeConversation.messages.push({ role: "assistant", content: botText });
            const p = loadingDiv.querySelector(".message-content p");
            p.textContent = botText;

            if (currentConversationId === tempId) {
                activeConversation.id = realConversationId;
                conversations[realConversationId] = activeConversation;
                delete conversations[tempId];
                currentConversationId = realConversationId;
                renderHistory();
            }
            
        } catch (error) {
            console.error("Error sending message:", error);
            const p = loadingDiv.querySelector(".message-content p");
            p.textContent = "Sorry, an error occurred. Please try again.";
        }
        
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    function switchConversation(id) {
        if (currentConversationId === id) return; 
        currentConversationId = id;
        renderChatLog();
        renderHistory();
    }
    
    function renderHistory() {
        historyList.innerHTML = "";
        
        const sortedConversations = Object.values(conversations).sort((a, b) => {
             const lastMsgA = a.messages[a.messages.length - 1]?.timestamp || a.id;
             const lastMsgB = b.messages[b.messages.length - 1]?.timestamp || b.id;
             return new Date(lastMsgB) - new Date(lastMsgA);
        });

        sortedConversations.forEach(convo => {
            const li = document.createElement("li");
            li.dataset.id = convo.id;
            li.innerHTML = `<i class="fa-regular fa-comment-dots"></i> ${convo.title}`;
            if (convo.id === currentConversationId) {
                li.classList.add("active");
            }
            historyList.appendChild(li);
        });
    }

    function renderChatLog() {
        if (currentConversationId === null) {
            chatLog.innerHTML = emptyChatPlaceholder;
            return;
        }

        const activeConversation = conversations[currentConversationId];
        if (!activeConversation) {
            startNewChat();
            return;
        }

        chatLog.innerHTML = "";
        activeConversation.messages.forEach(message => {
            addMessageToLog(message.role, message.content); 
        });
        chatLog.scrollTop = chatLog.scrollHeight;
    }
    
    function addMessageToLog(role, text) {
        const messageDiv = document.createElement("div");
        messageDiv.classList.add("chat-message", role);

        let avatar = role === "user" ? "AN" : '<i class="fa-solid fa-robot"></i>';
        let name = role === "user" ? "" : "<strong>CHAT A.I+</strong>";

        messageDiv.innerHTML = `
            <div class="avatar">${avatar}</div>
            <div class="message-content">
                ${name}
                <p>${text}</p>
            </div>
        `;
        chatLog.appendChild(messageDiv);
        return messageDiv;
    }

    // --- Application Initialization ---
    async function initializeApp() {
        if (!currentUserId) return;
        try {
            const response = await fetch(`http://localhost:5000/api/conversations?userId=${currentUserId}`);
            if (!response.ok) {
                throw new Error("Failed to load history");
            }
            const data = await response.json(); 
            conversations = {};
            data.forEach(convo => {
                conversations[convo.id] = convo;
            });
            renderHistory();
            startNewChat();
        } catch (error) {
            console.error("Error initializing app:", error);
            startNewChat();
        }
    }

    initializeApp();
});