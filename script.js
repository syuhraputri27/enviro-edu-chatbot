document.addEventListener("DOMContentLoaded", () => {
    // === 1. MENANGKAP ELEMEN DOM ===
    const sendButton = document.getElementById("send-button");
    const chatInput = document.getElementById("chat-input");
    const historyList = document.getElementById("history-list");
    const chatLog = document.getElementById("chat-log-area");
    const newChatButton = document.querySelector(".new-chat-btn");

    // Simpan HTML untuk placeholder "chat kosong"
    const emptyChatPlaceholder = `
        <div class="empty-chat-placeholder">
            <i class="fa-solid fa-robot"></i>
            <h2>Hello Name</h2>
        </div>
    `;

    // === 2. DATA UTAMA APLIKASI (STATE) ===
    let conversations = []; // Menyimpan SEMUA percakapan
    let currentConversationId = null; // Melacak chat mana yang sedang AKTIF

    // === 3. EVENT LISTENERS ===

    // Klik tombol "New Chat"
    newChatButton.addEventListener("click", (e) => {
        e.preventDefault(); // Mencegah link <a> me-refresh halaman
        startNewChat();
    });

    // Klik tombol "Send"
    sendButton.addEventListener("click", sendMessage);

    // Tekan "Enter" di input
    chatInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            sendMessage();
        }
    });

    // Klik salah satu item di history
    historyList.addEventListener("click", (e) => {
        const clickedLi = e.target.closest("li"); // Dapatkan elemen <li> yang diklik
        if (clickedLi) {
            const id = Number(clickedLi.dataset.id); // Ambil ID dari data-attribute
            switchConversation(id);
        }
    });

    // === 4. FUNGSI-FUNGSI UTAMA ===

    /**
     * Memulai chat baru (membersihkan area chat)
     */
    function startNewChat() {
        currentConversationId = null; // Set ID chat aktif ke null
        chatInput.value = ""; // Kosongkan input
        renderChatLog(); // Tampilkan placeholder
        renderHistory(); // Perbarui history (untuk hapus highlight 'active')
    }

    /**
     * Mengirim pesan
     */
    function sendMessage() {
        const messageText = chatInput.value.trim();
        if (messageText === "") return;

        let activeConversation;

        if (currentConversationId === null) {
            // Ini adalah chat BARU
            const newId = Date.now(); // Buat ID unik berdasarkan waktu
            activeConversation = {
                id: newId,
                title: messageText.length > 28 ? messageText.substring(0, 28) + "..." : messageText,
                messages: [] // Array pesan untuk chat ini
            };
            conversations.unshift(activeConversation); // Tambahkan ke awal array
            currentConversationId = newId; // Set sebagai chat aktif
            renderHistory(); // Gambar ulang seluruh history list
        } else {
            // Ini adalah chat LAMA
            activeConversation = conversations.find(c => c.id === currentConversationId);
        }

        // Tambahkan pesan user ke data
        activeConversation.messages.push({ sender: "user", text: messageText });

        // Tampilkan pesan di layar
        renderChatLog();
        chatInput.value = ""; // Kosongkan input

        // Simulasikan balasan bot
        simulateBotReply(activeConversation.id, messageText);
    }

    /**
     * Mengganti percakapan yang aktif
     * @param {number} id - ID percakapan yang ingin dibuka
     */
    function switchConversation(id) {
        if (currentConversationId === id) return; // Jangan lakukan apa-apa jika chat sudah aktif

        currentConversationId = id;
        renderChatLog();
        renderHistory();
    }

    /**
     * Menggambar ulang (me-render) seluruh daftar history di sidebar
     */
    function renderHistory() {
        historyList.innerHTML = ""; // Kosongkan list
        conversations.forEach(convo => {
            const li = document.createElement("li");
            li.dataset.id = convo.id; // Simpan ID di data-attribute
            li.innerHTML = `<i class="fa-regular fa-comment-dots"></i> ${convo.title}`;
            
            if (convo.id === currentConversationId) {
                li.classList.add("active"); // Beri highlight jika ini chat aktif
            }
            historyList.appendChild(li);
        });
    }

    /**
     * Menggambar ulang (me-render) seluruh log chat di area kanan
     */
    function renderChatLog() {
        if (currentConversationId === null) {
            // Jika tidak ada chat aktif, tampilkan placeholder
            chatLog.innerHTML = emptyChatPlaceholder;
            return;
        }

        // Cari data percakapan yang aktif
        const activeConversation = conversations.find(c => c.id === currentConversationId);
        if (!activeConversation) {
            // Jika tidak ketemu (seharusnya tidak terjadi), kembali ke state awal
            startNewChat();
            return;
        }

        chatLog.innerHTML = ""; // Kosongkan area chat

        // Loop melalui setiap pesan di percakapan aktif dan buat HTML-nya
        activeConversation.messages.forEach(message => {
            const messageDiv = document.createElement("div");
            messageDiv.classList.add("chat-message", message.sender);

            let avatar = message.sender === "user" ? "AN" : '<i class="fa-solid fa-robot"></i>';
            let name = message.sender === "user" ? "" : "<strong>CHAT A.I+</strong>";

            messageDiv.innerHTML = `
                <div class="avatar">${avatar}</div>
                <div class="message-content">
                    ${name}
                    <p>${message.text}</p>
                </div>
            `;
            chatLog.appendChild(messageDiv);
        });

        // Auto-scroll ke pesan terbaru
        chatLog.scrollTop = chatLog.scrollHeight;
    }

    /**
     * Simulasi balasan bot
     * @param {number} convoId - ID chat mana yang harus dibalas
     * @param {string} userMessage - Pesan dari user (untuk logika balasan)
     */
    function simulateBotReply(convoId, userMessage) {
        let botText = "Maaf, saya tidak mengerti."; // Balasan default

        if (userMessage.toLowerCase().includes("halo")) {
            botText = "Halo juga! Ada yang bisa saya bantu?";
        }

        setTimeout(() => {
            // Cari percakapan yang benar (bisa jadi user sudah pindah chat)
            const conversationToReply = conversations.find(c => c.id === convoId);
            if (conversationToReply) {
                conversationToReply.messages.push({ sender: "bot", text: botText });

                // HANYA render ulang jika chat yang dibalas masih aktif
                if (currentConversationId === convoId) {
                    renderChatLog();
                }
            }
        }, 1000); // Balas setelah 1 detik
    }

    // --- Inisialisasi Aplikasi ---
    startNewChat(); // Mulai aplikasi dalam keadaan "New Chat"
});