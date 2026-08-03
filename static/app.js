document.addEventListener('DOMContentLoaded', () => {
    const customerSelector = document.getElementById('customer-selector');
    const chatArea = document.getElementById('chat-area');
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-button');
    const escalationBanner = document.getElementById('escalation-banner');
    const typingTemplate = document.getElementById('typing-template');

    let currentSessionId = generateUUID();
    let isEscalated = false;

    fetchCustomers();

    customerSelector.addEventListener('change', () => {
        resetChat();
    });

    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    async function fetchCustomers() {
        try {
            const response = await fetch('/api/customers');
            if (response.ok) {
                const customers = await response.json();
                populateCustomerDropdown(customers);
            } else {
                console.error('Failed to fetch customers');
                customerSelector.innerHTML = '<option value="" disabled selected>Failed to load customers</option>';
            }
        } catch (error) {
            console.error('Error fetching customers:', error);
            customerSelector.innerHTML = '<option value="" disabled selected>Error loading customers</option>';
        }
    }

    function populateCustomerDropdown(customers) {
        customerSelector.innerHTML = '<option value="" disabled selected>Select Customer</option>';
        customers.forEach(c => {
            const option = document.createElement('option');
            option.value = c.customer_id;
            option.textContent = c.name;
            customerSelector.appendChild(option);
        });
        
        if (customers.length > 0) {
            customerSelector.selectedIndex = 1;
            resetChat();
        }
    }

    function resetChat() {
        currentSessionId = generateUUID();
        isEscalated = false;
        chatArea.innerHTML = '';
        escalationBanner.classList.add('hidden');
        messageInput.disabled = false;
        sendButton.disabled = false;
        messageInput.value = '';
        messageInput.placeholder = "Type your message...";
        messageInput.focus();
    }

    async function sendMessage() {
        if (isEscalated) return;
        
        const text = messageInput.value.trim();
        const customerId = customerSelector.value;
        
        if (!text || !customerId) return;

        addMessageToUI('user', text);
        messageInput.value = '';
        
        showTypingIndicator();
        scrollToBottom();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: currentSessionId,
                    customer_id: customerId,
                    message: text
                })
            });

            removeTypingIndicator();

            if (response.ok) {
                const data = await response.json();
                addMessageToUI('agent', data.response);
                
                if (data.escalated) {
                    handleEscalation();
                }
            } else {
                addMessageToUI('agent', "I'm sorry, I encountered an error connecting to the server.");
            }
        } catch (error) {
            console.error('Chat error:', error);
            removeTypingIndicator();
            addMessageToUI('agent', "I'm sorry, there was a network error. Please try again later.");
        }
    }

    function addMessageToUI(sender, text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender}-message`;
        
        const bubble = document.createElement('div');
        bubble.className = 'message-bubble';
        
        if (sender === 'agent') {
            bubble.classList.add('glass-card');
            bubble.innerHTML = parseMarkdown(text);
        } else {
            bubble.textContent = text;
        }
        
        messageDiv.appendChild(bubble);
        chatArea.appendChild(messageDiv);
        scrollToBottom();
    }

    function showTypingIndicator() {
        const clone = typingTemplate.content.cloneNode(true);
        chatArea.appendChild(clone);
    }

    function removeTypingIndicator() {
        const indicator = chatArea.querySelector('.typing-indicator-container');
        if (indicator) {
            indicator.remove();
        }
    }

    function scrollToBottom() {
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function handleEscalation() {
        isEscalated = true;
        escalationBanner.classList.remove('hidden');
        messageInput.disabled = true;
        sendButton.disabled = true;
        messageInput.placeholder = "Conversation transferred...";
    }

    function parseMarkdown(text) {
        if (!text) return '';
        
        let html = text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        
        const lines = html.split('\n');
        let inList = false;
        let result = [];
        
        for (let i = 0; i < lines.length; i++) {
            let line = lines[i].trim();
            if (line.startsWith('- ') || line.startsWith('* ')) {
                if (!inList) {
                    result.push('<ul>');
                    inList = true;
                }
                result.push(`<li>${line.substring(2)}</li>`);
            } else {
                if (inList) {
                    result.push('</ul>');
                    inList = false;
                }
                if (line) {
                    result.push(`<p>${line}</p>`);
                }
            }
        }
        
        if (inList) {
            result.push('</ul>');
        }
        
        return result.join('');
    }

    function generateUUID() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0,
                v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }
});
