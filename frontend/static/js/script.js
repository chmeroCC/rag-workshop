// Variables globales
let currentDocId = null;
let chatHistory = [];

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    checkBackendHealth();
    setupEventListeners();
});

// Vérifier l'état du backend
async function checkBackendHealth() {
    try {
        const response = await fetch('/health');
        const data = await response.json();
        
        const statusDot = document.querySelector('.status-dot');
        const statusText = document.getElementById('status-text');
        
        if (data.backend === 'healthy') {
            statusDot.style.background = '#10b981';
            statusText.textContent = 'Connecté';
            statusText.style.color = '#047857';
        } else {
            statusDot.style.background = '#ef4444';
            statusText.textContent = 'Backend hors ligne';
            statusText.style.color = '#dc2626';
        }
    } catch (error) {
        console.error('Erreur de connexion:', error);
        updateStatus(false);
    }
}

function updateStatus(isConnected) {
    const statusDot = document.querySelector('.status-dot');
    const statusText = document.getElementById('status-text');
    
    if (isConnected) {
        statusDot.style.background = '#10b981';
        statusText.textContent = 'Connecté';
        statusText.style.color = '#047857';
    } else {
        statusDot.style.background = '#ef4444';
        statusText.textContent = 'Déconnecté';
        statusText.style.color = '#dc2626';
    }
}

// Configuration des écouteurs d'événements
function setupEventListeners() {
    // Upload de fichier
    const fileInput = document.getElementById('pdf-input');
    const uploadArea = document.getElementById('upload-area');
    
    fileInput.addEventListener('change', handleFileUpload);
    
    // Drag and drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = '#667eea';
        uploadArea.style.background = '#f1f5f9';
    });
    
    uploadArea.addEventListener('dragleave', () => {
        uploadArea.style.borderColor = '#cbd5e1';
        uploadArea.style.background = '#f8fafc';
    });
    
    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.style.borderColor = '#cbd5e1';
        uploadArea.style.background = '#f8fafc';
        
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            handleFileUpload();
        }
    });
    
    // Input de question
    const questionInput = document.getElementById('question-input');
    questionInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendQuestion();
        }
    });
}

// Gérer l'upload de fichier
async function handleFileUpload() {
    const fileInput = document.getElementById('pdf-input');
    const file = fileInput.files[0];
    
    if (!file) return;
    
    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showAlert('error', 'Veuillez sélectionner un fichier PDF');
        return;
    }
    
    if (file.size > 10 * 1024 * 1024) { // 10MB limit
        showAlert('error', 'Le fichier est trop volumineux (max 10MB)');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    showLoading('Traitement du PDF...');
    
    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Mettre à jour l'interface
            currentDocId = data.doc_id;
            
            document.getElementById('filename').textContent = data.filename;
            document.getElementById('doc-id').textContent = data.doc_id;
            document.getElementById('file-info').style.display = 'block';
            
            // Activer la zone de chat
            document.getElementById('input-area').style.display = 'block';
            document.getElementById('question-input').focus();
            
            // Vider l'historique
            chatHistory = [];
            clearChat();
            
            showAlert('success', data.message);
            
            // Afficher un message de bienvenue
            addMessage('system', `Document "${data.filename}" chargé avec succès. Posez-moi des questions !`);
        } else {
            showAlert('error', data.error || 'Erreur lors de l\'upload');
        }
    } catch (error) {
        showAlert('error', 'Erreur de connexion au serveur');
    } finally {
        hideLoading();
        fileInput.value = ''; // Réinitialiser l'input
    }
}

// Envoyer une question
async function sendQuestion() {
    const input = document.getElementById('question-input');
    const question = input.value.trim();
    
    if (!question) return;
    
    if (!currentDocId) {
        showAlert('warning', 'Veuillez d\'abord charger un document PDF');
        return;
    }
    
    // Ajouter la question au chat
    addMessage('user', question);
    input.value = '';
    
    // Ajouter à l'historique
    chatHistory.push({ role: 'user', content: question });
    
    showLoading('Recherche dans le document...');
    
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                question: question,
                history: chatHistory.slice(-5) // Derniers 5 messages
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // Ajouter la réponse au chat
            addMessage('bot', data.answer);
            
            // Ajouter à l'historique
            chatHistory.push({ role: 'assistant', content: data.answer });
            
            // Afficher les sources
            if (data.sources && data.sources.length > 0) {
                displaySources(data.sources);
                document.getElementById('sources-section').style.display = 'block';
            }
        } else {
            addMessage('bot', `Désolé, une erreur est survenue: ${data.error}`);
        }
    } catch (error) {
        addMessage('bot', 'Désolé, je ne peux pas répondre pour le moment. Veuillez vérifier votre connexion.');
    } finally {
        hideLoading();
        input.focus();
    }
}

// Ajouter un message au chat
function addMessage(sender, content) {
    const chatMessages = document.getElementById('chat-messages');
    const welcomeMessage = document.querySelector('.welcome-message');
    
    // Masquer le message de bienvenue si c'est le premier message
    if (welcomeMessage && chatMessages.children.length === 1) {
        welcomeMessage.style.display = 'none';
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}-message`;
    
    const now = new Date();
    const timeString = now.toLocaleTimeString('fr-FR', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    
    messageDiv.innerHTML = `
        <div class="message-header">
            <strong>${sender === 'user' ? 'Vous' : 'Assistant'}</strong>
            <span>${timeString}</span>
        </div>
        <div class="message-content">${content}</div>
    `;
    
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Afficher les sources
function displaySources(sources) {
    const container = document.getElementById('sources-container');
    container.innerHTML = '';
    
    sources.forEach((source, index) => {
        const sourceCard = document.createElement('div');
        sourceCard.className = 'source-card';
        
        sourceCard.innerHTML = `
            <div class="source-card-header">
                <span>Page ${source.page_number}</span>
                <span>Source #${index + 1}</span>
            </div>
            <div class="source-content">
                ${source.snippet}
            </div>
        `;
        
        container.appendChild(sourceCard);
    });
}

// Réinitialiser la session
async function resetSession() {
    if (!confirm('Voulez-vous vraiment charger un nouveau document ? L\'historique actuel sera perdu.')) {
        return;
    }
    
    try {
        await fetch('/reset', { method: 'POST' });
        
        // Réinitialiser l'interface
        currentDocId = null;
        chatHistory = [];
        
        document.getElementById('file-info').style.display = 'none';
        document.getElementById('input-area').style.display = 'none';
        document.getElementById('sources-section').style.display = 'none';
        
        clearChat();
        
        showAlert('success', 'Prêt pour un nouveau document');
    } catch (error) {
        showAlert('error', 'Erreur lors de la réinitialisation');
    }
}

// Vider le chat
function clearChat() {
    const chatMessages = document.getElementById('chat-messages');
    const welcomeMessage = document.querySelector('.welcome-message');
    
    chatMessages.innerHTML = '';
    
    if (welcomeMessage) {
        welcomeMessage.style.display = 'block';
        chatMessages.appendChild(welcomeMessage);
    }
}

// Afficher une alerte
function showAlert(type, message) {
    // Créer une alerte temporaire
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type}`;
    alertDiv.textContent = message;
    alertDiv.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 1rem 1.5rem;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 1000;
        animation: slideIn 0.3s ease;
        max-width: 300px;
    `;
    
    if (type === 'success') {
        alertDiv.style.background = '#10b981';
    } else if (type === 'error') {
        alertDiv.style.background = '#ef4444';
    } else if (type === 'warning') {
        alertDiv.style.background = '#f59e0b';
    }
    
    document.body.appendChild(alertDiv);
    
    // Supprimer après 3 secondes
    setTimeout(() => {
        alertDiv.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => alertDiv.remove(), 300);
    }, 3000);
}

// Gestion du chargement
function showLoading(text) {
    const modal = document.getElementById('loading