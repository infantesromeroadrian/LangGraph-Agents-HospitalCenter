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
let currentPatient = null;
let pendingImageAttachments = [];
const DEFAULT_IMAGE_MESSAGE = 'He adjuntado una imagen para valoración clínica.';
let admissionFormInitialized = false;
let uiEventListenersInitialized = false;
const DEBUG_UI = false;

function debugLog(...args) {
    if (DEBUG_UI) {
        console.log(...args);
    }
}

function debugWarn(...args) {
    if (DEBUG_UI) {
        console.warn(...args);
    }
}

const CONNECTION_STATES = {
    idle: {
        label: 'Pendiente de admisión',
        iconClass: 'text-warning',
        detail: 'Completa la admisión para iniciar la consulta.'
    },
    connecting: {
        label: 'Preparando sesión segura',
        iconClass: 'text-warning pulse-dot',
        detail: 'Estamos creando tu sesión clínica y verificando la conexión.'
    },
    connected: {
        label: 'Consulta conectada',
        iconClass: 'text-success pulse-dot',
        detail: 'La conversación está activa y lista para recibir mensajes.'
    },
    reconnecting: {
        label: 'Reconectando',
        iconClass: 'text-warning pulse-dot',
        detail: 'Estamos restaurando la conexión sin perder el contexto.'
    },
    disconnected: {
        label: 'Conexión interrumpida',
        iconClass: 'text-danger',
        detail: 'No se pudo mantener la conexión. Puedes reintentar en unos segundos.'
    },
    auth: {
        label: 'Sesión expirada',
        iconClass: 'text-danger',
        detail: 'Necesitamos verificar de nuevo tu acceso para continuar.'
    },
    error: {
        label: 'Atención requerida',
        iconClass: 'text-danger',
        detail: 'Se ha producido un error. Revisa el aviso mostrado en pantalla.'
    }
};

// Initialize application
document.addEventListener('DOMContentLoaded', async function() {
    debugLog('🚀 Initializing Medical System (FastAPI)...');
    updateConnectionStatus('idle');
    setupAdmissionFormHandler();
    setupEventListeners();
    initializeEmergencyButton();

    const patientLoaded = await loadCurrentPatient();

    if (!patientLoaded) {
        showAdmissionModal('Completa tu admisión para iniciar una consulta segura.');
        return;
    }

    await initializeSystemWithPatient();
});

/**
 * ✅ NUEVO: Inicializa el sistema CON datos del paciente cargados
 */
async function initializeSystemWithPatient() {
    debugLog('✅ Initializing system with verified patient context');
    clearFeedbackMessage();
    updateConnectionStatus('connecting');

    // Create new session (asociada al paciente)
    const sessionCreated = await createSession();
    if (!sessionCreated) {
        return;
    }

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

    debugLog('✅ System initialized with patient data');
}

/**
 * Carga el paciente actual a partir de la cookie segura.
 */
async function loadCurrentPatient() {
    try {
        debugLog('📡 Fetching current patient data from API');

        const response = await fetch('/api/patients/me');

        if (response.status === 204) {
            return false;
        }

        if (!response.ok) {
            debugWarn('❌ Current patient lookup failed (HTTP', response.status, ')');
            return false;
        }

        const patient = await response.json();

        // Almacenar globalmente
        currentPatient = patient;
        window.currentPatient = patient; // Para acceso desde otros scripts

        // Actualizar UI con datos minimizados del paciente
        updatePatientBadge(patient);
        updateConnectionStatus('idle', 'Paciente verificado. Estamos listos para abrir una nueva consulta.');

        return true;

    } catch (error) {
        console.error('❌ Error loading current patient data:', error);
        return false;
    }
}

/**
 * ✅ NUEVO: Mostrar modal de admisión (no se puede cerrar sin completar)
 */
function showAdmissionModal(message) {
    const modalElement = document.getElementById('admissionModal');

    if (!modalElement) {
        console.error('❌ Admission modal not found in DOM');
        return;
    }

    setupAdmissionFormHandler();
    resetAdmissionFormState();

    if (message) {
        showAdmissionFeedback(message, 'info');
    }

    const modal = new bootstrap.Modal(modalElement, {
        backdrop: 'static',  // No cerrar al hacer click fuera
        keyboard: false      // No cerrar con ESC
    });

    modal.show();

    debugLog('📋 Admission modal displayed - registration required before access');
}

function resetAdmissionFormState() {
    const form = document.getElementById('admission-form');
    const processingIndicator = document.getElementById('admission-processing');
    const submitBtn = form ? form.querySelector('button[type="submit"]') : null;

    clearAdmissionFeedback();
    clearAdmissionValidation();

    if (processingIndicator) {
        processingIndicator.style.display = 'none';
    }

    if (submitBtn) {
        submitBtn.disabled = false;
    }
}

function showAdmissionFeedback(message, tone = 'danger') {
    const feedback = document.getElementById('admission-feedback');
    if (!feedback) return;

    feedback.className = `alert alert-${tone}`;
    feedback.classList.remove('d-none');
    feedback.innerHTML = `<i class="fas fa-circle-info me-2"></i>${escapeHtml(message)}`;
}

function clearAdmissionFeedback() {
    const feedback = document.getElementById('admission-feedback');
    if (!feedback) return;

    feedback.className = 'alert alert-danger d-none';
    feedback.innerHTML = '';
}

function clearAdmissionValidation() {
    const form = document.getElementById('admission-form');
    if (!form) return;

    form.querySelectorAll('.is-invalid').forEach((field) => field.classList.remove('is-invalid'));
    const consentError = document.getElementById('consent-error');
    if (consentError) {
        consentError.style.display = 'none';
    }
}

function markAdmissionFieldInvalid(fieldId, message, options = {}) {
    const field = document.getElementById(fieldId);
    if (!field) return;

    field.classList.add('is-invalid');
    if (fieldId === 'consent') {
        const consentError = document.getElementById('consent-error');
        if (consentError) {
            consentError.textContent = message;
            consentError.style.display = 'block';
        }
    } else if (options.feedbackSelector) {
        const feedback = field.parentElement && field.parentElement.querySelector(options.feedbackSelector);
        if (feedback) {
            feedback.textContent = message;
        }
    }
}

function validateAdmissionForm() {
    clearAdmissionValidation();

    const fullName = document.getElementById('full-name');
    const age = document.getElementById('age');
    const gender = document.getElementById('gender');
    const consent = document.getElementById('consent');

    if (!fullName || !fullName.value.trim()) {
        markAdmissionFieldInvalid('full-name', 'Indica tu nombre completo.', { feedbackSelector: '.invalid-feedback' });
        fullName && fullName.focus();
        return { valid: false, message: 'Necesitamos tu nombre completo para abrir la consulta.' };
    }

    const numericAge = age ? parseInt(age.value, 10) : NaN;
    if (!age || Number.isNaN(numericAge) || numericAge < 0 || numericAge > 120) {
        markAdmissionFieldInvalid('age', 'Indica una edad válida entre 0 y 120 años.', { feedbackSelector: '.invalid-feedback' });
        age && age.focus();
        return { valid: false, message: 'Revisa la edad indicada antes de continuar.' };
    }

    if (!gender || !gender.value) {
        markAdmissionFieldInvalid('gender', 'Selecciona una opción para continuar.', { feedbackSelector: '.invalid-feedback' });
        gender && gender.focus();
        return { valid: false, message: 'Selecciona tu género o la opción de preferencia.' };
    }

    if (!consent || !consent.checked) {
        markAdmissionFieldInvalid('consent', 'Debes aceptar el consentimiento informado para continuar.');
        consent && consent.focus();
        return { valid: false, message: 'Debes aceptar el consentimiento informado para iniciar la consulta.' };
    }

    return { valid: true };
}

/**
 * ✅ NUEVO: Configurar event handler del formulario de admisión
 */
function setupAdmissionFormHandler() {
    const form = document.getElementById('admission-form');

    if (!form) {
        debugWarn('⚠️ Admission form not found');
        return;
    }

    if (admissionFormInitialized) {
        return;
    }

    admissionFormInitialized = true;

    form.addEventListener('submit', async function(e) {
        e.preventDefault();

        debugLog('📤 Submitting admission form...');

        const validation = validateAdmissionForm();
        if (!validation.valid) {
            showAdmissionFeedback(validation.message);
            return;
        }

        clearAdmissionFeedback();

        // Preparar datos del paciente
        const patientData = {
            full_name: document.getElementById('full-name').value.trim(),
            age: parseInt(document.getElementById('age').value, 10),
            gender: document.getElementById('gender').value,
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

    debugLog('✅ Admission form handler configured');
}

/**
 * ✅ NUEVO: Enviar formulario de admisión al backend
 */
async function submitAdmissionForm(patientData) {
    try {
        debugLog('📡 Sending patient data to API');

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

        // Almacenar globalmente
        currentPatient = patient;
        window.currentPatient = patient;

        // Actualizar UI
        updatePatientBadge(patient);

        // Mostrar confirmación
        showSuccessMessage('Admisión completada. Ya puedes iniciar tu consulta médica.');

        return true;

    } catch (error) {
        console.error('❌ Error submitting admission form:', error);
        showAdmissionFeedback(error.message || 'No se pudo completar la admisión. Revisa los datos e inténtalo de nuevo.');
        return false;
    }
}

function getPatientShortName(fullName) {
    if (!fullName) return 'Paciente verificado';

    const parts = fullName.trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return 'Paciente verificado';

    return parts[0];
}

function maskMedicalRecordNumber(medicalRecordNumber) {
    if (!medicalRecordNumber) return 'Pendiente';

    const visibleTail = medicalRecordNumber.slice(-4);
    return `HC •••• ${visibleTail}`;
}

/**
 * ✅ NUEVO: Actualizar badge con nombre del paciente
 */
function updatePatientBadge(patient) {
    // Buscar el badge en el header (definido en base.html)
    const badge = document.getElementById('patient-badge');
    const hasVerifiedPatient = Boolean(patient && patient.full_name && patient.medical_record_number);

    if (badge) {
        badge.style.display = hasVerifiedPatient ? 'inline-block' : 'none';

        const nameElement = badge.querySelector('#patient-name');
        if (nameElement && hasVerifiedPatient) {
            nameElement.textContent = `Paciente verificado: ${getPatientShortName(patient.full_name)}`;
        }
    }

    // También actualizar el modal de sesión si existe
    const modalPatientName = document.getElementById('modal-patient-name');
    if (modalPatientName) {
        modalPatientName.textContent = hasVerifiedPatient
            ? `${getPatientShortName(patient.full_name)} · ${maskMedicalRecordNumber(patient.medical_record_number)}`
            : 'Perfil pendiente de verificación';
        modalPatientName.className = hasVerifiedPatient ? 'text-success fw-bold' : 'text-muted';
    }

    // ✅ NUEVO: Actualizar panel de información del paciente (sidebar)
    const hcDisplay = document.getElementById('hc-display');
    const nameDisplay = document.getElementById('name-display');

    if (hcDisplay) {
        hcDisplay.textContent = hasVerifiedPatient
            ? maskMedicalRecordNumber(patient.medical_record_number)
            : 'Pendiente';
    }

    if (nameDisplay) {
        nameDisplay.textContent = hasVerifiedPatient ? getPatientShortName(patient.full_name) : 'Sin verificar';
    }
}

/**
 * ✅ NUEVO: Mostrar mensaje de éxito
 */
function showSuccessMessage(message) {
    showFeedbackMessage(message, 'success');
}

function showFeedbackMessage(message, tone = 'danger', options = {}) {
    const { persist = false } = options;
    const region = document.getElementById('chat-feedback-region');

    if (!region) {
        return;
    }

    const alert = document.createElement('div');
    alert.className = `alert alert-${tone} alert-dismissible fade show`;
    alert.setAttribute('role', tone === 'success' ? 'status' : 'alert');
    alert.innerHTML = `
        <i class="fas ${tone === 'success' ? 'fa-check-circle' : 'fa-circle-exclamation'} me-2"></i>
        ${escapeHtml(message)}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Cerrar aviso"></button>
    `;

    region.innerHTML = '';
    region.appendChild(alert);

    if (!persist) {
        window.setTimeout(() => {
            alert.remove();
        }, 6000);
    }
}

function clearFeedbackMessage() {
    const region = document.getElementById('chat-feedback-region');
    if (region) {
        region.innerHTML = '';
    }
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

    debugLog(`📡 Connecting to WebSocket: ${wsUrl}`);

    try {
        ws = new WebSocket(wsUrl);

        // Connection opened
        ws.onopen = function(event) {
            void event;
            debugLog('✅ WebSocket connected');
            clearFeedbackMessage();
            updateConnectionStatus('connected');
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
            debugLog('❌ WebSocket disconnected');

            if (event.code === 4401 || event.code === 4403) {
                handleSessionExpired('Tu sesión segura ha expirado o ya no está autorizada. Completa la admisión de nuevo para continuar.');
                return;
            }

            // Attempt reconnection
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 10000);
                updateConnectionStatus(
                    'reconnecting',
                    `Intentando recuperar la conexión (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`
                );

                debugLog(`🔄 Reconnecting in ${delay}ms (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);

                setTimeout(function() {
                    initializeWebSocket();
                }, delay);
            } else {
                updateConnectionStatus('disconnected');
                showError('Se perdió la conexión clínica. Recarga la página para volver a intentarlo.');
            }
        };

        // Connection error
        ws.onerror = function(error) {
            console.error('❌ WebSocket error:', error);
            updateConnectionStatus('error', 'No pudimos estabilizar la conexión en tiempo real.');
        };

    } catch (error) {
        console.error('❌ Error creating WebSocket:', error);
        showError('No se pudo establecer la conexión en tiempo real.', { affectsConnection: true });
    }
}

/**
 * Handle incoming WebSocket messages
 * ✅ NUEVO: Reemplaza los event handlers de Socket.IO
 */
function handleWebSocketMessage(data) {
    debugLog('📨 WebSocket message received:', data);

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
            debugWarn('⚠️ Unknown message type:', data.type);
    }
}

/**
 * Handle "thinking" event (agent is processing)
 */
function handleThinking(data) {
    debugLog('🤔 Agent thinking:', data.agent_name);

    // Show thinking indicator
    const agentName = data.agent_name || 'Sistema';
    showThinkingIndicator(agentName);
}

/**
 * Handle graph update event
 */
function handleGraphUpdate(data) {
    debugLog('📊 Graph update:', data);

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
    debugLog('💬 Agent response:', data);

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
    if (data.retry_after) {
        showError(`${data.message} Puedes volver a intentarlo en ${data.retry_after} segundos.`);
    } else {
        showError(data.message || 'Se ha producido un error en la consulta.');
    }
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
    indicator.setAttribute('role', 'status');
    indicator.setAttribute('aria-live', 'polite');
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
            <strong>${escapeHtml(specialistName)}</strong>
            <small class="text-muted ms-2">${timestamp}</small>
        </div>
        <div class="message-content">
            ${escapeHtml(message.content || '').replace(/\n/g, '<br>')}
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
        const requestBody = {
            patient_info: {}
        };

        const response = await fetch('/api/sessions', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestBody)
        });

        if (!response.ok) {
            if (response.status === 401 || response.status === 403) {
                handleSessionExpired('Tu sesión verificada ya no es válida. Completa la admisión de nuevo para continuar.');
                return false;
            }

            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || 'No se pudo crear la sesión clínica.');
        }

        const data = await response.json();

        if (data.success) {
            sessionId = data.session_id;
            threadId = data.thread_id;

            debugLog('✅ Session created:', sessionId);

            // Update UI
            updateSessionInfo();
            return true;

        } else {
            throw new Error(data.error || 'No se pudo crear la sesión clínica.');
        }

    } catch (error) {
        console.error('❌ Error creating session:', error);
        showError('No se pudo abrir la sesión clínica. Inténtalo de nuevo en unos instantes.', { affectsConnection: true });
        return false;
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
        showError('La conexión clínica todavía no está lista. Espera un momento o recarga la página.');
        return;
    }

    const outboundMessage = message || DEFAULT_IMAGE_MESSAGE;
    const attachmentsToSend = pendingImageAttachments.map((attachment) => ({ ...attachment }));

    debugLog('📤 Sending message:', outboundMessage, 'attachments:', attachmentsToSend.length);

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
        showError('No se pudo enviar tu mensaje. Inténtalo de nuevo.');
    }
}

/**
 * Update connection status indicator
 */
function updateConnectionStatus(state, detail) {
    const statusEl = document.getElementById('connection-status');
    const statusNote = document.getElementById('consultation-status-note');
    const config = CONNECTION_STATES[state] || CONNECTION_STATES.error;

    if (statusEl) {
        statusEl.className = `connection-status-badge status-${state}`;
        statusEl.innerHTML = `<i class="fas fa-circle ${config.iconClass}"></i><span class="d-none d-lg-inline ms-2">${config.label}</span>`;
    }

    if (statusNote) {
        statusNote.textContent = detail || config.detail;
    }
}

function handleSessionExpired(message) {
    ws = null;
    sessionId = null;
    threadId = null;
    currentPatient = null;
    window.currentPatient = null;

    updatePatientBadge({ full_name: '', medical_record_number: '' });
    updateConnectionStatus('auth', message);
    showError(message);
    showAdmissionModal('Necesitamos verificar de nuevo tu perfil antes de continuar con la consulta.');
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
    if (uiEventListenersInitialized) {
        return;
    }

    uiEventListenersInitialized = true;

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
function showError(message, options = {}) {
    const { affectsConnection = false } = options;
    showFeedbackMessage(message, 'danger', { persist: true });
    if (affectsConnection) {
        updateConnectionStatus('error', message);
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
    const statusNote = document.getElementById('consultation-status-note');

    if (!specialistStatusEl) return;

    // Parse node name to get specialist
    let specialistName = 'Sistema de Triaje';
    let specialistIcon = 'fa-user-md';
    let statusText = 'Listo para atenderte';
    let statusIcon = 'fa-circle text-success';
    let detailText = 'Estamos listos para recibir la siguiente actualización clínica.';

    if (nodeName) {
        const normalized = nodeName.toLowerCase().replace(/_/g, '_');
        specialistName = getSpecialistDisplayName(normalized);
        specialistIcon = getSpecialistIcon(normalized);
        statusText = 'Analizando tu caso...';
        statusIcon = 'fa-circle text-warning pulse-dot';

        if (normalized.includes('emerg')) {
            detailText = 'Protocolo urgente activo. Si existe peligro inmediato, llama al 911 sin esperar la respuesta del chat.';
        } else if (normalized.includes('triage')) {
            detailText = 'El sistema de triaje está clasificando la urgencia y el especialista más adecuado.';
        } else {
            detailText = 'El especialista está revisando tu caso con el contexto clínico disponible.';
        }
    }

    specialistStatusEl.innerHTML = `
        <i class="fas ${statusIcon} me-1"></i>
        <span>${specialistName} - ${statusText}</span>
    `;

    if (statusNote) {
        statusNote.textContent = detailText;
    }
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
        if (emergencyBtn.dataset.bound === 'true') {
            return;
        }

        emergencyBtn.dataset.bound = 'true';
        emergencyBtn.addEventListener('click', function() {
            activateEmergencyMode();
        });
        debugLog('✅ Emergency button initialized');
    }
}

function activateEmergencyMode() {
    updateConnectionStatus('connected', 'Has activado el protocolo de orientación urgente. Si hay riesgo vital, llama al 911 ahora mismo.');
    showEmergencyModal();

    debugLog('🚨 Emergency mode activated');
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
                            <p class="mb-0">Este sistema solo puede ofrecer orientación inicial y no sustituye una ambulancia, una guardia ni un servicio de emergencias.</p>
                        </div>

                        <h6 class="mb-3">Activa este protocolo si presentas señales como:</h6>
                        <ul class="mb-3">
                            <li>Dolor de pecho intenso o dificultad respiratoria severa</li>
                            <li>Pérdida de conciencia, desorientación o debilidad repentina</li>
                            <li>Sangrado abundante, convulsiones o reacción alérgica grave</li>
                        </ul>

                        <div id="emergency-feedback" class="alert alert-danger d-none" role="alert" aria-live="assertive" aria-atomic="true"></div>

                        <div class="bg-light p-3 rounded">
                            <p class="mb-2"><strong>Describe tu emergencia:</strong></p>
                            <textarea id="emergency-description" class="form-control" rows="3"
                                placeholder="Ejemplo: Dolor de pecho intenso, dificultad para respirar..." aria-label="Describe tu emergencia"></textarea>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <a href="tel:911" class="btn btn-outline-danger">
                            <i class="fas fa-phone-volume me-2"></i>
                            Llamar al 911
                        </a>
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                        <button type="button" class="btn btn-danger" id="send-emergency-btn">
                            <i class="fas fa-ambulance me-2"></i>
                            Enviar orientación urgente
                        </button>
                    </div>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        // Event listener para el botón de enviar emergencia
        document.getElementById('send-emergency-btn').addEventListener('click', function() {
            const description = document.getElementById('emergency-description').value.trim();
            const feedback = document.getElementById('emergency-feedback');

            if (feedback) {
                feedback.classList.add('d-none');
                feedback.textContent = '';
            }

            if (description) {
                // Enviar mensaje de emergencia
                const sent = sendEmergencyMessage(description);
                if (!sent) {
                    if (feedback) {
                        feedback.textContent = 'No pudimos enviar tu emergencia porque la conexión clínica no está disponible.';
                        feedback.classList.remove('d-none');
                    }
                    return;
                }

                // Cerrar modal
                const modalInstance = bootstrap.Modal.getInstance(modal);
                modalInstance.hide();

                // Auto-focus en el input de chat
                const messageInput = document.getElementById('message-input');
                if (messageInput) {
                    messageInput.focus();
                }
            } else {
                if (feedback) {
                    feedback.textContent = 'Describe brevemente qué está ocurriendo para priorizar tu consulta.';
                    feedback.classList.remove('d-none');
                }
            }
        });
    }

    // Mostrar modal
    const modalInstance = new bootstrap.Modal(modal);
    const descriptionField = document.getElementById('emergency-description');
    const feedback = document.getElementById('emergency-feedback');
    if (descriptionField) {
        descriptionField.value = '';
    }
    if (feedback) {
        feedback.classList.add('d-none');
        feedback.textContent = '';
    }
    modalInstance.show();
}

function sendEmergencyMessage(description) {
    const emergencyMessage = `🚨 EMERGENCIA MÉDICA: ${description}`;

    if (!ws || ws.readyState !== WebSocket.OPEN) {
        showError('No pudimos activar la orientación urgente porque la conexión no está disponible. Si hay peligro inmediato, llama al 911.');
        return false;
    }

    // Mostrar mensaje en el chat
    if (typeof addMessageToChat === 'function') {
        addMessageToChat({
            role: 'user',
            content: emergencyMessage,
            specialist_type: 'emergencias'
        });
    }

    showFeedbackMessage('Protocolo urgente enviado. Si empeoras o hay riesgo vital, llama al 911 sin esperar respuesta del chat.', 'warning', { persist: true });
    updateActiveSpecialist('emergencias');

    // Enviar por WebSocket
    ws.send(JSON.stringify({
        message: emergencyMessage,
        timestamp: new Date().toISOString()
    }));

    // Mostrar indicador de procesamiento
    if (typeof showTypingIndicator === 'function') {
        showTypingIndicator('Protocolo urgente');
    }

    return true;
}
