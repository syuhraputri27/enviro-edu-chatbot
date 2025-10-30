document.addEventListener("DOMContentLoaded", () => {
    // === 1. MENANGKAP ELEMEN DOM ===
    const sendButton = document.getElementById("send-button");
    const chatInput = document.getElementById("chat-input");
    const historyList = document.getElementById("history-list");
    const chatLog = document.getElementById("chat-log-area");
    const newChatButton = document.querySelector(".new-chat-btn");
    const clearAllButton = document.querySelector(".clear-all"); // <-- TAMBAHAN BARU

    const emptyChatPlaceholder = `
        <div class="empty-chat-placeholder">
            <i class="fa-solid fa-robot"></i>
            <h2>Hello Name</h2>
        </div>
    `;

    // === 2. DATA UTAMA APLIKASI (STATE) ===
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
    
    // <-- LISTENER BARU UNTUK "CLEAR ALL" ---
    clearAllButton.addEventListener("click", (e) => {
        e.preventDefault();
        clearAllConversations();
    });

    // === 4. FUNGSI-FUNGSI UTAMA ===

    /**
     * FUNGSI BARU: Menghapus semua percakapan
     */
    async function clearAllConversations() {
        if (!confirm("Apakah Anda yakin ingin menghapus semua percakapan? Tindakan ini tidak bisa dibatalkan.")) {
            return;
        }

        try {
            const response = await fetch("http://localhost:3001/api/conversations", {
                method: "DELETE",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ userId: currentUserId }) // Kirim userId untuk dihapus
            });

            if (!response.ok) {
                throw new Error("Gagal menghapus history di server.");
            }
            
            // Jika server berhasil, bersihkan state frontend
            conversations = {};
            startNewChat(); // Ini akan membersihkan UI (merender history & chat log)
            
            console.log("Semua percakapan berhasil dihapus.");

        } catch (error) {
            console.error("Error clearing conversations:", error);
            alert("Terjadi kesalahan saat menghapus history.");
        }
    }
    
    // ... (Fungsi getOrCreateUserId, startNewChat, sendMessage, dll. tetap sama persis) ...
    
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
            const response = await fetch("http://localhost:3001/api/chat", {
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
            p.textContent = "Maaf, terjadi kesalahan. Coba lagi.";
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

    // --- Inisialisasi Aplikasi ---
    async function initializeApp() {
        if (!currentUserId) return;
        try {
            const response = await fetch(`http://localhost:3001/api/conversations?userId=${currentUserId}`);
            if (!response.ok) {
                throw new Error("Gagal memuat history");
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