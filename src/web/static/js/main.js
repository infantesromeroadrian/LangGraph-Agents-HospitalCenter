/**
 * LangGraph Medical Center - Main JavaScript
 *
 * ✅ MIGRADO A WEBSOCKET NATIVO (FastAPI)
 * Reemplaza Socket.IO con WebSocket estándar W3C
 */

// Global variables
let ws = null;
let sessionId = null;
let threadId = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;
let currentPatient = null; // ✅ NUEVO: Almacena datos del paciente actual
let pendingImageAttachments = [];
const DEFAULT_IMAGE_MESSAGE = 'He adjuntado una imagen para valoración clínica.';

// Initialize application
document.addEventListener('DOMContentLoaded', async function() {
    console.log('🚀 Initializing Medical System (FastAPI)...');

    // ✅ PASO 1: VERIFICAR SI EXISTE PACIENTE REGISTRADO (ANTES DE TODO)
    const medicalRecordNumber = localStorage.getItem('medical_record_number');

    if (!medicalRecordNumber) {
        // No hay paciente → Mostrar modal de admisión (ANTESALA)
        console.log('📋 No patient found - showing admission modal');
        showAdmissionModal();
        return; // ⚠️ DETENER inicialización hasta que se complete el registro
    }

    // ✅ PASO 2: PACIENTE EXISTE → Cargar datos desde PostgreSQL
    console.log('📋 Patient found in localStorage:', medicalRecordNumber);
    const patientLoaded = await loadPatientData(medicalRecordNumber);

    if (!patientLoaded) {
        // Paciente no encontrado en BD → Re-registrar
        console.warn('⚠️ Patient not found in database - re-registration required');
        localStorage.removeItem('medical_record_number');
        showAdmissionModal();
        return;
    }

    // ✅ PASO 3: Continuar inicialización normal (SOLO si paciente está cargado)
    await initializeSystemWithPatient();
});

/**
 * ✅ NUEVO: Inicializa el sistema CON datos del paciente cargados
 */
async function initializeSystemWithPatient() {
    console.log('✅ Initializing system with patient context:', currentPatient.medical_record_number);

    // Create new session (asociada al paciente)
    await createSession();

    // Initialize WebSocket connection
    initializeWebSocket();

    // Initialize chat handlers
    if (typeof initializeChatHandlers === 'function') {
        initializeChatHandlers();
    }

    // Initialize graph visualization
    if (typeof initializeGraphVisualization === 'function') {
        initializeGraphVisualization();
    }

    // Setup event listeners
    setupEventListeners();

    // Setup admission form handler
    setupAdmissionFormHandler();

    console.log('✅ System initialized with patient data');
}

/**
 * ✅ NUEVO: Cargar datos del paciente desde la API
 */
async function loadPatientData(medicalRecordNumber) {
    try {
        console.log('📡 Fetching patient data from API:', medicalRecordNumber);

        const response = await fetch(`/api/patients/${medicalRecordNumber}`);

        if (!response.ok) {
            console.warn('❌ Patient not found in database (HTTP', response.status, ')');
            return false;
        }

        const patient = await response.json();

        // Almacenar globalmente
        currentPatient = patient;
        window.currentPatient = patient; // Para acceso desde otros scripts

        // Actualizar UI con nombre del paciente
        updatePatientBadge(patient);

        console.log('✅ Patient loaded:', patient.full_name, '(HC:', patient.medical_record_number + ')');
        console.log('   - Alergias:', patient.allergies);
        console.log('   - Medicación:', patient.medications);

        return true;

    } catch (error) {
        console.error('❌ Error loading patient data:', error);
        return false;
    }
}

/**
 * ✅ NUEVO: Mostrar modal de admisión (no se puede cerrar sin completar)
 */
function showAdmissionModal() {
    const modalElement = document.getElementById('admissionModal');

    if (!modalElement) {
        console.error('❌ Admission modal not found in DOM');
        return;
    }

    // Configurar el handler del formulario ANTES de mostrar el modal
    setupAdmissionFormHandler();

    const modal = new bootstrap.Modal(modalElement, {
        backdrop: 'static',  // No cerrar al hacer click fuera
        keyboard: false      // No cerrar con ESC
    });

    modal.show();

    console.log('📋 Admission modal displayed - registration required before access');
}

/**
 * ✅ NUEVO: Configurar event handler del formulario de admisión
 */
function setupAdmissionFormHandler() {
    const form = document.getElementById('admission-form');

    if (!form) {
        console.warn('⚠️ Admission form not found');
        return;
    }

    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        console.log('📤 Submitting admission form...');

        // Validar campos requeridos
        const fullName = document.getElementById('full-name').value.trim();
        const age = parseInt(document.getElementById('age').value);
        const gender = document.getElementById('gender').value;
        const consent = document.getElementById('consent').checked;

        if (!fullName || !age || !gender || !consent) {
            alert('Por favor, completa todos los campos obligatorios y acepta el consentimiento.');
            return;
        }

        // Preparar datos del paciente
        const patientData = {
            full_name: fullName,
            age: age,
            gender: gender,
            dni: document.getElementById('dni').value.trim() || null,
            email: document.getElementById('email').value.trim() || null,
            phone: document.getElementById('phone').value.trim() || null,
            allergies: document.getElementById('allergies').value.trim() || 'Ninguna conocida',
            medications: document.getElementById('medications').value.trim() || 'Ninguna',
            medical_history: document.getElementById('medical-history').value.trim() || 'Sin antecedentes relevantes'
        };

        // Mostrar indicador de procesamiento
        const processingIndicator = document.getElementById('admission-processing');
        const submitBtn = form.querySelector('button[type="submit"]');

        if (processingIndicator) processingIndicator.style.display = 'block';
        if (submitBtn) submitBtn.disabled = true;

        // Enviar a la API
        const success = await submitAdmissionForm(patientData);

        if (success) {
            // Cerrar modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('admissionModal'));
            if (modal) modal.hide();

            // Inicializar sistema con el paciente registrado
            await initializeSystemWithPatient();

        } else {
            // Error: reactivar formulario
            if (processingIndicator) processingIndicator.style.display = 'none';
            if (submitBtn) submitBtn.disabled = false;
        }
    });

    console.log('✅ Admission form handler configured');
}

/**
 * ✅ NUEVO: Enviar formulario de admisión al backend
 */
async function submitAdmissionForm(patientData) {
    try {
        console.log('📡 Sending patient data to API:', patientData);

        const response = await fetch('/api/patients', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(patientData)
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Error al crear paciente');
        }

        const patient = await response.json();

        console.log('✅ Patient created successfully:', patient.medical_record_number);

        // Guardar en localStorage (solo el ID, no todos los datos)
        localStorage.setItem('medical_record_number', patient.medical_record_number);

        // Almacenar globalmente
        currentPatient = patient;
        window.currentPatient = patient;

        // Actualizar UI
        updatePatientBadge(patient);

        // Mostrar confirmación
        showSuccessMessage(`¡Bienvenido/a, ${patient.full_name}! Tu historia clínica es: ${patient.medical_record_number}`);

        return true;

    } catch (error) {
        console.error('❌ Error submitting admission form:', error);
        alert('Error al registrar paciente: ' + error.message);
        return false;
    }
}

/**
 * ✅ NUEVO: Actualizar badge con nombre del paciente
 */
function updatePatientBadge(patient) {
    // Buscar el badge en el header (definido en base.html)
    const badge = document.getElementById('patient-badge');

    if (badge) {
        badge.style.display = 'inline-block';

        const nameElement = badge.querySelector('#patient-name');
        if (nameElement) {
            nameElement.textContent = patient.full_name;
        }

        console.log('✅ Patient badge updated:', patient.full_name);
    }

    // También actualizar el modal de sesión si existe
    const modalPatientName = document.getElementById('modal-patient-name');
    if (modalPatientName) {
        modalPatientName.textContent = `${patient.full_name} (${patient.medical_record_number})`;
        modalPatientName.className = 'text-success fw-bold';
    }

    // ✅ NUEVO: Actualizar panel de información del paciente (sidebar)
    const hcDisplay = document.getElementById('hc-display');
    const nameDisplay = document.getElementById('name-display');

    if (hcDisplay) {
        hcDisplay.textContent = patient.medical_record_number;
    }

    if (nameDisplay) {
        nameDisplay.textContent = patient.full_name;
    }
}

/**
 * ✅ NUEVO: Mostrar mensaje de éxito
 */
function showSuccessMessage(message) {
    const alert = document.createElement('div');
    alert.className = 'alert alert-success alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3';
    alert.style.zIndex = '9999';
    alert.setAttribute('role', 'alert');
    alert.innerHTML = `
        <i class="fas fa-check-circle me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    document.body.appendChild(alert);

    // Auto-dismiss después de 5 segundos
    setTimeout(() => {
        alert.remove();
    }, 5000);
}

/**
 * Initialize WebSocket connection (native W3C WebSocket)
 * ✅ NO MÁS SOCKET.IO - WebSocket puro
 */
function initializeWebSocket() {
    if (!sessionId) {
        console.error('❌ Cannot initialize WebSocket: No session ID');
        return;
    }

    // Construct WebSocket URL
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/${sessionId}`;

    console.log(`📡 Connecting to WebSocket: ${wsUrl}`);

    try {
        ws = new WebSocket(wsUrl);

        // Connection opened
        ws.onopen = function(event) {
            console.log('✅ WebSocket connected');
            updateConnectionStatus(true);
            reconnectAttempts = 0;
        };

        // Listen for messages
        ws.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            } catch (error) {
                console.error('❌ Error parsing WebSocket message:', error);
            }
        };

        // Connection closed
        ws.onclose = function(event) {
            console.log('❌ WebSocket disconnected');
            updateConnectionStatus(false);

            // Attempt reconnection
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);

                console.log(`🔄 Reconnecting in ${delay}ms (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);

                setTimeout(function() {
                    initializeWebSocket();
                }, delay);
            } else {
                showError('Connection lost. Please reload the page.');
            }
        };

        // Connection error
        ws.onerror = function(error) {
            console.error('❌ WebSocket error:', error);
            updateConnectionStatus(false);
        };

    } catch (error) {
        console.error('❌ Error creating WebSocket:', error);
        showError('Failed to establish WebSocket connection');
    }
}

/**
 * Handle incoming WebSocket messages
 * ✅ NUEVO: Reemplaza los event handlers de Socket.IO
 */
function handleWebSocketMessage(data) {
    console.log('📨 WebSocket message received:', data);

    switch (data.type) {
        case 'thinking':
            handleThinking(data);
            break;

        case 'graph_update':
            handleGraphUpdate(data);
            break;

        case 'agent_response':
            handleAgentResponse(data);
            break;

        case 'error':
            handleError(data);
            break;

        default:
            console.warn('⚠️ Unknown message type:', data.type);
    }
}

/**
 * Handle "thinking" event (agent is processing)
 */
function handleThinking(data) {
    console.log('🤔 Agent thinking:', data.agent_name);

    // Show thinking indicator
    const agentName = data.agent_name || 'Sistema';
    showThinkingIndicator(agentName);
}

/**
 * Handle graph update event
 */
function handleGraphUpdate(data) {
    console.log('📊 Graph update:', data);

    // Update graph visualization
    if (typeof highlightActiveNode === 'function' && data.node) {
        highlightActiveNode(data.node);
    }

    // Update active specialist display
    updateActiveSpecialist(data.node);

    // Update evaluations if available
    if (data.data && data.data.evaluations) {
        updateEvaluationsList(data.data.evaluations);
    }

    // Hide thinking indicator
    hideThinkingIndicator();
}

/**
 * Handle agent response event
 */
function handleAgentResponse(data) {
    console.log('💬 Agent response:', data);

    // Hide thinking indicator
    hideThinkingIndicator();

    // Display message in chat
    if (typeof displayMessage === 'function') {
        displayMessage(data);
    } else {
        // Fallback: display message directly
        addMessageToChat({
            role: data.role || 'assistant',
            content: data.content,
            specialist_type: data.specialist_type,
            metadata: data.metadata
        });
    }
}

/**
 * Handle error event
 */
function handleError(data) {
    console.error('❌ Server error:', data.message);
    showError(data.message || 'An error occurred');
    hideThinkingIndicator();
}

/**
 * Show thinking indicator
 */
function showThinkingIndicator(agentName) {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;

    // Remove existing thinking indicator
    const existing = document.getElementById('thinking-indicator');
    if (existing) existing.remove();

    // Create new thinking indicator
    const indicator = document.createElement('div');
    indicator.id = 'thinking-indicator';
    indicator.className = 'message assistant-message mb-3';
    indicator.innerHTML = `
        <div class="message-content">
            <div class="d-flex align-items-center">
                <div class="spinner-border spinner-border-sm me-2" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
                <span class="text-muted">${agentName} está procesando...</span>
            </div>
        </div>
    `;

    chatMessages.appendChild(indicator);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Hide thinking indicator
 */
function hideThinkingIndicator() {
    const indicator = document.getElementById('thinking-indicator');
    if (indicator) {
        indicator.remove();
    }
}

/**
 * Add message to chat (fallback if displayMessage not available)
 */
function addMessageToChat(message) {
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) return;

    const messageEl = document.createElement('div');
    messageEl.className = `message ${message.role}-message mb-3`;

    const specialistName = message.specialist_type ?
        getSpecialistDisplayName(message.specialist_type) :
        (message.role === 'user' ? 'Tú' : 'Asistente');

    const timestamp = formatTimestamp(new Date());
    const attachmentsHtml = renderInlineAttachments(message.attachments || []);

    messageEl.innerHTML = `
        <div class="message-header">
            <strong>${specialistName}</strong>
            <small class="text-muted ms-2">${timestamp}</small>
        </div>
        <div class="message-content">
            ${message.content}
        </div>
        ${attachmentsHtml}
    `;

    chatMessages.appendChild(messageEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Create new medical session
 * ✅ ACTUALIZADO: Asocia la sesión con el paciente si está disponible
 */
async function createSession() {
    try {
        // ✅ NUEVO: Incluir medical_record_number si el paciente está cargado
        const requestBody = {
            patient_info: {}
        };

        if (currentPatient && currentPatient.medical_record_number) {
            requestBody.medical_record_number = currentPatient.medical_record_number;
            console.log('📋 Creating session for patient:', currentPatient.medical_record_number);
        }

        const response = await fetch('/api/sessions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        const data = await response.json();

        if (data.success) {
            sessionId = data.session_id;
            threadId = data.thread_id;

            console.log('✅ Session created:', sessionId);

            if (currentPatient) {
                console.log('   - Associated with patient:', currentPatient.full_name);
            }

            // Update UI
            updateSessionInfo();

        } else {
            throw new Error(data.error);
        }

    } catch (error) {
        console.error('❌ Error creating session:', error);
        showError('Failed to create session');
    }
}

/**
 * Send message to server
 * ✅ ACTUALIZADO: Usa WebSocket nativo en vez de Socket.IO
 */
function sendMessage() {
    const messageInput = document.getElementById('message-input');
    if (!messageInput) return;

    const message = messageInput.value.trim();
    if (!message && !pendingImageAttachments.length) return;

    if (!ws || ws.readyState !== WebSocket.OPEN) {
        showError('WebSocket not connected. Please wait or reload the page.');
        return;
    }

    const outboundMessage = message || DEFAULT_IMAGE_MESSAGE;
    const attachmentsToSend = pendingImageAttachments.map((attachment) => ({ ...attachment }));

    console.log('📤 Sending message:', outboundMessage, 'attachments:', attachmentsToSend.length);

    // Display user message immediately
    addMessageToChat({
        role: 'user',
        content: outboundMessage,
        attachments: attachmentsToSend
    });

    // Send via WebSocket
    try {
        ws.send(JSON.stringify({
            message: outboundMessage,
            attachments: attachmentsToSend
        }));

        // Clear input
        messageInput.value = '';
        pendingImageAttachments = [];
        renderPendingImagePreviews();

    } catch (error) {
        console.error('❌ Error sending message:', error);
        showError('Failed to send message');
    }
}

/**
 * Update connection status indicator
 */
function updateConnectionStatus(connected) {
    const statusEl = document.getElementById('connection-status');

    if (statusEl) {
        if (connected) {
            statusEl.innerHTML = '<i class="fas fa-circle text-success"></i> Connected';
        } else {
            statusEl.innerHTML = '<i class="fas fa-circle text-danger"></i> Disconnected';
        }
    }
}

/**
 * Update session info display
 */
function updateSessionInfo() {
    const modalSessionId = document.getElementById('modal-session-id');
    const modalThreadId = document.getElementById('modal-thread-id');

    if (modalSessionId) modalSessionId.textContent = sessionId;
    if (modalThreadId) modalThreadId.textContent = threadId;
}

/**
 * Setup global event listeners
 */
function setupEventListeners() {
    // Enter key in message input
    const messageInput = document.getElementById('message-input');

    if (messageInput) {
        messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
    }

    // Send button
    const sendBtn = document.getElementById('send-btn');

    if (sendBtn) {
        sendBtn.addEventListener('click', sendMessage);
    }

    const attachBtn = document.getElementById('attach-image-btn');
    const imageInput = document.getElementById('image-input');

    if (attachBtn && imageInput) {
        attachBtn.addEventListener('click', function() {
            imageInput.click();
        });
        imageInput.addEventListener('change', handleImageSelection);
    }
}

async function handleImageSelection(event) {
    const imageInput = event.target;
    const files = Array.from(imageInput.files || []);
    if (!files.length) return;

    const maxImages = parseInt(imageInput.dataset.maxImages || '3', 10);
    const maxImageMb = parseInt(imageInput.dataset.maxImageMb || '5', 10);
    const maxBytes = maxImageMb * 1024 * 1024;
    const remainingSlots = maxImages - pendingImageAttachments.length;

    if (remainingSlots <= 0) {
        showError(`Solo puedes adjuntar hasta ${maxImages} imágenes por consulta.`);
        imageInput.value = '';
        return;
    }

    const selectedFiles = files.slice(0, remainingSlots);

    for (const file of selectedFiles) {
        if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
            showError('Formato no soportado. Usa JPEG, PNG o WEBP.');
            continue;
        }

        if (file.size > maxBytes) {
            showError(`La imagen ${file.name} supera ${maxImageMb} MB.`);
            continue;
        }

        const dataUrl = await readFileAsDataUrl(file);
        pendingImageAttachments.push({
            type: 'image',
            filename: file.name,
            media_type: file.type,
            data_url: dataUrl,
            size_bytes: file.size
        });
    }

    renderPendingImagePreviews();
    imageInput.value = '';
}

function readFileAsDataUrl(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(reader.result);
        reader.onerror = () => reject(new Error(`No se pudo leer ${file.name}`));
        reader.readAsDataURL(file);
    });
}

function renderPendingImagePreviews() {
    const previewStrip = document.getElementById('attachment-preview-strip');
    if (!previewStrip) return;

    if (!pendingImageAttachments.length) {
        previewStrip.innerHTML = '';
        previewStrip.style.display = 'none';
        return;
    }

    previewStrip.style.display = 'flex';
    previewStrip.innerHTML = pendingImageAttachments.map((attachment, index) => `
        <div class="attachment-chip">
            <button type="button" class="attachment-remove-btn" onclick="removePendingImage(${index})" aria-label="Eliminar imagen">×</button>
            <img src="${attachment.data_url}" alt="${escapeHtml(attachment.filename)}">
            <span class="attachment-chip-name">${escapeHtml(attachment.filename)}</span>
        </div>
    `).join('');
}

function removePendingImage(index) {
    pendingImageAttachments.splice(index, 1);
    renderPendingImagePreviews();
}

/**
 * Show error message
 */
function showError(message) {
    // Create alert element
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger alert-dismissible fade show';
    alert.setAttribute('role', 'alert');
    alert.innerHTML = `
        <i class="fas fa-exclamation-circle me-2"></i>
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

    // Insert at top of chat messages
    const chatMessages = document.getElementById('chat-messages');

    if (chatMessages) {
        chatMessages.insertBefore(alert, chatMessages.firstChild);

        // Auto-dismiss after 5 seconds
        setTimeout(function() {
            alert.remove();
        }, 5000);
    }
}

/**
 * Format timestamp
 */
function formatTimestamp(date) {
    if (!date) date = new Date();

    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');

    return `${hours}:${minutes}`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Get specialist display name
 */
function getSpecialistDisplayName(specialty) {
    const names = {
        'general_medicine': 'Medicina General',
        'cardiology': 'Cardiología',
        'neurology': 'Neurología',
        'pediatrics': 'Pediatría',
        'dermatology': 'Dermatología',
        'ginecologia': 'Ginecología',
        'orthopedics': 'Traumatología',
        'psychiatry': 'Psiquiatría',
        'oncology': 'Oncología',
        'triage': 'Triaje',
        'consensus': 'Consenso',
        'emergencias': 'Emergencias'
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
        'ginecologia': 'fa-venus',
        'orthopedics': 'fa-bone',
        'psychiatry': 'fa-head-side-virus',
        'oncology': 'fa-ribbon',
        'triage': 'fa-clipboard-list',
        'consensus': 'fa-users',
        'emergencias': 'fa-triangle-exclamation'
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
        'ginecologia': '#c2185b',
        'orthopedics': '#0dcaf0',
        'psychiatry': '#0d6efd',
        'oncology': '#d63384',
        'triage': '#ffc107',
        'consensus': '#198754',
        'emergencias': '#E74C3C'
    };

    return colors[specialty] || '#6c757d';
}

function renderInlineAttachments(attachments) {
    if (!attachments || !attachments.length) return '';

    const images = attachments
        .filter((attachment) => attachment && attachment.data_url)
        .map((attachment) => `
            <a href="${attachment.data_url}" target="_blank" rel="noopener">
                <img
                    src="${attachment.data_url}"
                    alt="${escapeHtml(attachment.filename || 'Adjunto clínico')}"
                    class="message-attachment-image"
                >
            </a>
        `)
        .join('');

    if (!images) return '';
    return `<div class="message-attachments">${images}</div>`;
}

/**
 * ✅ UPDATED: Update active specialist display (compatible con nuevo diseño)
 */
function updateActiveSpecialist(nodeName) {
    const specialistStatusEl = document.getElementById('specialist-status');

    if (!specialistStatusEl) return;

    // Parse node name to get specialist
    let specialistName = 'Sistema de Triaje';
    let specialistIcon = 'fa-user-md';
    let statusText = 'Listo para atenderte';
    let statusIcon = 'fa-circle text-success';

    if (nodeName) {
        const normalized = nodeName.toLowerCase().replace(/_/g, '_');
        specialistName = getSpecialistDisplayName(normalized);
        specialistIcon = getSpecialistIcon(normalized);
        statusText = 'Analizando tu caso...';
        statusIcon = 'fa-circle text-warning pulse-dot';
    }

    specialistStatusEl.innerHTML = `
        <i class="fas ${statusIcon} me-1"></i>
        <span>${specialistName} - ${statusText}</span>
    `;
}

/**
 * Update evaluations list
 */
function updateEvaluationsList(evaluations) {
    const evaluationsListEl = document.getElementById('evaluations-list');

    if (!evaluationsListEl || !evaluations || !Array.isArray(evaluations)) return;

    // Clear existing
    evaluationsListEl.innerHTML = '';

    // Sort by relevance score
    const sorted = [...evaluations].sort((a, b) => (b.relevance_score || 0) - (a.relevance_score || 0));

    // Add each evaluation
    sorted.forEach(evaluation => {
        const specialty = evaluation.specialist_type || evaluation.specialty || 'unknown';
        const score = evaluation.relevance_score || 0;
        const reasoning = evaluation.reasoning || 'Sin evaluación disponible';

        const specialistName = getSpecialistDisplayName(specialty);
        const specialistIcon = getSpecialistIcon(specialty);
        const specialistColor = getSpecialistColor(specialty);

        // Color based on score
        let scoreClass = 'secondary';
        if (score >= 75) scoreClass = 'success';
        else if (score >= 50) scoreClass = 'warning';
        else if (score >= 25) scoreClass = 'info';

        const item = document.createElement('div');
        item.className = 'list-group-item';
        item.innerHTML = `
            <div class="d-flex justify-content-between align-items-center mb-2">
                <strong style="color: ${specialistColor}">
                    <i class="fas ${specialistIcon} me-2"></i>
                    ${specialistName}
                </strong>
                <span class="badge bg-${scoreClass}">${score}%</span>
            </div>
            <small class="text-muted">${reasoning.substring(0, 100)}${reasoning.length > 100 ? '...' : ''}</small>
        `;

        evaluationsListEl.appendChild(item);
    });
}

// Export for use in other modules
window.sendMessage = sendMessage;

/**
 * 🚨 EMERGENCY BUTTON HANDLER
 * Activa modo emergencia cuando el usuario hace click
 */
function initializeEmergencyButton() {
    const emergencyBtn = document.getElementById('emergency-btn');

    if (emergencyBtn) {
        emergencyBtn.addEventListener('click', function() {
            activateEmergencyMode();
        });
        console.log('✅ Emergency button initialized');
    }
}

function activateEmergencyMode() {
    // Mostrar modal de emergencia
    showEmergencyModal();

    // Enviar mensaje de emergencia al sistema
    const emergencyMessage = "🚨 MODO EMERGENCIA ACTIVADO - Requiero atención médica urgente inmediata";

    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'emergency',
            message: emergencyMessage,
            priority: 'CRITICAL'
        }));
    }

    // Scroll al chat para ver respuesta
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    console.log('🚨 Emergency mode activated');
}

function showEmergencyModal() {
    // Crear modal de emergencia si no existe
    let modal = document.getElementById('emergency-modal');

    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'emergency-modal';
        modal.className = 'modal fade';
        modal.innerHTML = `
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content border-danger">
                    <div class="modal-header bg-danger text-white">
                        <h5 class="modal-title">
                            <i class="fas fa-exclamation-triangle me-2"></i>
                            MODO EMERGENCIA ACTIVADO
                        </h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="alert alert-danger mb-3">
                            <h6><i class="fas fa-phone-alt me-2"></i>Si es una emergencia REAL, llama al 911</h6>
                            <p class="mb-0">Este sistema proporciona orientación médica, pero NO sustituye atención de emergencia.</p>
                        </div>

                        <h6 class="mb-3">Tu consulta tiene máxima prioridad:</h6>
                        <ul class="mb-3">
                            <li>✅ Todos los especialistas están alerta</li>
                            <li>✅ Tiempo de respuesta: &lt;30 segundos</li>
                            <li>✅ Evaluación acelerada activada</li>
                        </ul>

                        <div class="bg-light p-3 rounded">
                            <p class="mb-2"><strong>Describe tu emergencia:</strong></p>
                            <textarea id="emergency-description" class="form-control" rows="3"
                                placeholder="Ejemplo: Dolor de pecho intenso, dificultad para respirar..."></textarea>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                        <button type="button" class="btn btn-danger" id="send-emergency-btn">
                            <i class="fas fa-ambulance me-2"></i>
                            Enviar Emergencia
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        // Event listener para el botón de enviar emergencia
        document.getElementById('send-emergency-btn').addEventListener('click', function() {
            const description = document.getElementById('emergency-description').value.trim();

            if (description) {
                // Enviar mensaje de emergencia
                sendEmergencyMessage(description);

                // Cerrar modal
                const modalInstance = bootstrap.Modal.getInstance(modal);
                modalInstance.hide();

                // Auto-focus en el input de chat
                const messageInput = document.getElementById('message-input');
                if (messageInput) {
                    messageInput.focus();
                }
            } else {
                alert('Por favor, describe tu emergencia');
            }
        });
    }

    // Mostrar modal
    const modalInstance = new bootstrap.Modal(modal);
    modalInstance.show();
}

function sendEmergencyMessage(description) {
    const emergencyMessage = `🚨 EMERGENCIA MÉDICA: ${description}`;

    // Mostrar mensaje en el chat
    if (typeof addMessageToChat === 'function') {
        addMessageToChat('user', emergencyMessage, null);
    }

    // Enviar por WebSocket
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'message',
            message: emergencyMessage,
            priority: 'EMERGENCY',
            timestamp: new Date().toISOString()
        }));
    }

    // Mostrar indicador de procesamiento
    if (typeof showTypingIndicator === 'function') {
        showTypingIndicator();
    }
}

// Inicializar botón de emergencia cuando cargue el DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeEmergencyButton);
} else {
    initializeEmergencyButton();
}
