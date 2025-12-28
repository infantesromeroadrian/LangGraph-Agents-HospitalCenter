/**
 * LangGraph Medical Center - Chat Functionality
 * 
 * ✅ MIGRADO A WEBSOCKET NATIVO (FastAPI)
 * Ya no usa Socket.IO, ahora WebSocket estándar W3C
 */

let isProcessing = false;

/**
 * Initialize chat socket handlers
 * ✅ ACTUALIZADO: Ya no necesitamos esto, los handlers están en main.js
 */
function initializeChatHandlers() {
    console.log('✅ Chat handlers initialized (WebSocket nativo)');
    // Los event handlers ahora están en handleWebSocketMessage() en main.js
}

/**
 * Display message in chat (public function llamada desde main.js)
 */
function displayMessage(data) {
    addMessageToUI({
        role: data.role || 'assistant',
        content: data.content || data.message,
        specialist: data.specialist_type,
        timestamp: data.timestamp || new Date().toISOString()
    });
    
    // Mark as done processing if it's the final response
    if (data.is_final || data.role === 'assistant') {
        isProcessing = false;
        updateSendButton(true);
    }
}

/**
 * Add message to UI
 */
function addMessageToUI(message) {
    const chatMessages = document.getElementById('chat-messages');
    
    if (!chatMessages) return;
    
    // Remove typing indicator
    removeTypingIndicator();
    
    // Create message element
    const messageEl = document.createElement('div');
    messageEl.className = `message ${message.role}`;
    
    const timestamp = message.timestamp ? new Date(message.timestamp) : new Date();
    const timeStr = formatTimestamp(timestamp);
    
    if (message.role === 'user') {
        // User message
        messageEl.innerHTML = `
            <div class="message-bubble user-message">
                <div class="message-content">${escapeHtml(message.content)}</div>
                <div class="message-time">${timeStr}</div>
            </div>
        `;
    } else {
        // Assistant/Specialist message
        const specialist = message.specialist || 'Sistema';
        const specialistNormalized = specialist.toLowerCase().replace(/\s+/g, '_');
        const specialistDisplay = getSpecialistDisplayName(specialistNormalized);
        const specialistIcon = getSpecialistIcon(specialistNormalized);
        const specialistColor = getSpecialistColor(specialistNormalized);
        
        messageEl.innerHTML = `
            <div class="message-bubble assistant-message" style="border-left: 4px solid ${specialistColor}">
                <div class="specialist-header">
                    <i class="fas ${specialistIcon}" style="color: ${specialistColor}"></i>
                    <strong>${escapeHtml(specialistDisplay)}</strong>
                </div>
                <div class="message-content">${formatMessageContent(message.content)}</div>
                <div class="message-time">${timeStr}</div>
            </div>
        `;
    }
    
    // Append to chat
    chatMessages.appendChild(messageEl);
    
    // Scroll to bottom
    scrollToBottom();
}

/**
 * Show typing indicator
 */
function showTypingIndicator(agentName) {
    // Remove existing indicator
    removeTypingIndicator();
    
    const chatMessages = document.getElementById('chat-messages');
    
    if (!chatMessages) return;
    
    const indicator = document.createElement('div');
    indicator.id = 'typing-indicator';
    indicator.className = 'message assistant';
    indicator.innerHTML = `
        <div class="message-bubble assistant-message typing">
            <div class="specialist-header">
                <i class="fas fa-stethoscope"></i>
                <strong>${escapeHtml(agentName || 'Agent')}</strong>
            </div>
            <div class="typing-dots">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    
    chatMessages.appendChild(indicator);
    scrollToBottom();
}

/**
 * Remove typing indicator
 */
function removeTypingIndicator() {
    const indicator = document.getElementById('typing-indicator');
    
    if (indicator) {
        indicator.remove();
    }
}

/**
 * Update send button state
 */
function updateSendButton(enabled) {
    const sendBtn = document.getElementById('send-btn');
    const messageInput = document.getElementById('message-input');
    
    if (sendBtn) {
        sendBtn.disabled = !enabled;
        
        if (enabled) {
            sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
        } else {
            sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        }
    }
    
    if (messageInput) {
        messageInput.disabled = !enabled;
    }
}

/**
 * Scroll chat to bottom
 */
function scrollToBottom() {
    const chatMessages = document.getElementById('chat-messages');
    
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
}

/**
 * Format message content (support markdown-like formatting)
 */
function formatMessageContent(content) {
    if (!content) return '';
    
    // Escape HTML first
    let formatted = escapeHtml(content);
    
    // Convert **bold** to <strong>
    formatted = formatted.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    
    // Convert *italic* to <em>
    formatted = formatted.replace(/\*([^*]+)\*/g, '<em>$1</em>');
    
    // Convert newlines to <br>
    formatted = formatted.replace(/\n/g, '<br>');
    
    // Convert links
    formatted = formatted.replace(
        /\[([^\]]+)\]\(([^)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener">$1</a>'
    );
    
    return formatted;
}

/**
 * Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Format timestamp (reuse from main.js if exists)
 */
function formatTimestamp(date) {
    if (!date) date = new Date();
    
    if (typeof date === 'string') {
        date = new Date(date);
    }
    
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    
    return `${hours}:${minutes}`;
}

/**
 * Get specialist display name (copy from main.js for standalone usage)
 */
function getSpecialistDisplayName(specialty) {
    const names = {
        'general_medicine': 'Medicina General',
        'cardiology': 'Cardiología',
        'neurology': 'Neurología',
        'pediatrics': 'Pediatría',
        'dermatology': 'Dermatología',
        'orthopedics': 'Traumatología',
        'psychiatry': 'Psiquiatría',
        'oncology': 'Oncología',
        'triage': 'Triaje',
        'consensus': 'Consenso'
    };
    
    return names[specialty] || specialty;
}

/**
 * Get specialist icon
 */
function getSpecialistIcon(specialty) {
    const icons = {
        'general_medicine': 'fa-user-md',
        'cardiology': 'fa-heartbeat',
        'neurology': 'fa-brain',
        'pediatrics': 'fa-child',
        'dermatology': 'fa-hand-sparkles',
        'orthopedics': 'fa-bone',
        'psychiatry': 'fa-head-side-virus',
        'oncology': 'fa-ribbon',
        'triage': 'fa-clipboard-list',
        'consensus': 'fa-users'
    };
    
    return icons[specialty] || 'fa-stethoscope';
}

/**
 * Get specialist color
 */
function getSpecialistColor(specialty) {
    const colors = {
        'general_medicine': '#6c757d',
        'cardiology': '#dc3545',
        'neurology': '#6f42c1',
        'pediatrics': '#fd7e14',
        'dermatology': '#20c997',
        'orthopedics': '#0dcaf0',
        'psychiatry': '#0d6efd',
        'oncology': '#d63384',
        'triage': '#ffc107',
        'consensus': '#198754'
    };
    
    return colors[specialty] || '#6c757d';
}

/**
 * Clear chat history
 */
function clearChat() {
    const chatMessages = document.getElementById('chat-messages');
    
    if (chatMessages) {
        chatMessages.innerHTML = '';
    }
}

/**
 * Export chat history
 */
async function exportChat() {
    if (!sessionId) return;
    
    try {
        const response = await fetch(`/api/sessions/${sessionId}/export`);
        const data = await response.json();
        
        if (data.success) {
            // Create downloadable file
            const blob = new Blob([JSON.stringify(data.messages, null, 2)], {
                type: 'application/json'
            });
            
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `chat-${sessionId}-${Date.now()}.json`;
            
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            
            URL.revokeObjectURL(url);
        }
        
    } catch (error) {
        console.error('❌ Error exporting chat:', error);
        showError('Failed to export chat');
    }
}

/**
 * Quick query buttons
 */
function quickQuery(query) {
    const messageInput = document.getElementById('message-input');
    
    if (messageInput) {
        messageInput.value = query;
        messageInput.focus();
    }
}
