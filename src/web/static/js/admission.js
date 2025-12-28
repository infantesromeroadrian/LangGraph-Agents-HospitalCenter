/**
 * 🏥 Hospital Virtual AI - Admission Form Handler
 * Maneja el registro de pacientes y genera historia clínica
 */

document.addEventListener('DOMContentLoaded', function() {
    const admissionForm = document.getElementById('admission-form');
    
    if (admissionForm) {
        admissionForm.addEventListener('submit', handleAdmissionSubmit);
        console.log('✅ Admission form initialized');
    }
});

/**
 * Maneja el envío del formulario de admisión
 */
async function handleAdmissionSubmit(event) {
    event.preventDefault();
    
    // Recopilar datos del formulario
    const formData = collectFormData();
    
    // Validar datos
    if (!validateFormData(formData)) {
        return;
    }
    
    // Mostrar indicador de procesamiento
    showProcessingIndicator(true);
    
    try {
        // Generar número de historia clínica
        const medicalRecordNumber = generateMedicalRecordNumber();
        
        // Guardar datos del paciente en localStorage
        const patientData = {
            ...formData,
            medicalRecordNumber: medicalRecordNumber,
            registrationDate: new Date().toISOString(),
            lastVisit: new Date().toISOString()
        };
        
        savePatientData(patientData);
        
        // Redireccionar a la sala de consulta con los datos del paciente
        window.location.href = `/?patient=${medicalRecordNumber}`;
        
    } catch (error) {
        console.error('Error en admisión:', error);
        alert('Hubo un error al procesar tu admisión. Por favor, intenta de nuevo.');
        showProcessingIndicator(false);
    }
}

/**
 * Recopila todos los datos del formulario
 */
function collectFormData() {
    return {
        // Datos personales
        fullName: document.getElementById('full-name').value.trim(),
        age: parseInt(document.getElementById('age').value),
        gender: document.getElementById('gender').value,
        dni: document.getElementById('dni').value.trim(),
        email: document.getElementById('email').value.trim(),
        phone: document.getElementById('phone').value.trim(),
        
        // Información médica
        allergies: document.getElementById('allergies').value.trim() || 'Ninguna conocida',
        medications: document.getElementById('medications').value.trim() || 'Ninguna',
        medicalHistory: document.getElementById('medical-history').value.trim() || 'Sin antecedentes relevantes',
        
        // Motivo de consulta
        urgencyLevel: document.querySelector('input[name="urgencyLevel"]:checked').value,
        symptoms: document.getElementById('symptoms').value.trim(),
        
        // Consentimiento
        consent: document.getElementById('consent').checked
    };
}

/**
 * Valida los datos del formulario
 */
function validateFormData(data) {
    if (!data.fullName) {
        alert('Por favor, ingresa tu nombre completo');
        return false;
    }
    
    if (!data.age || data.age < 0 || data.age > 120) {
        alert('Por favor, ingresa una edad válida');
        return false;
    }
    
    if (!data.gender) {
        alert('Por favor, selecciona tu género');
        return false;
    }
    
    if (!data.urgencyLevel) {
        alert('Por favor, selecciona el nivel de urgencia');
        return false;
    }
    
    if (!data.symptoms) {
        alert('Por favor, describe tus síntomas');
        return false;
    }
    
    if (!data.consent) {
        alert('Debes aceptar los términos y condiciones');
        return false;
    }
    
    return true;
}

/**
 * Genera un número de historia clínica único
 * Formato: HC-YYYY-XXXXXX
 */
function generateMedicalRecordNumber() {
    const year = new Date().getFullYear();
    const random = Math.floor(Math.random() * 1000000).toString().padStart(6, '0');
    return `HC-${year}-${random}`;
}

/**
 * Guarda los datos del paciente en localStorage
 */
function savePatientData(patientData) {
    // Guardar el paciente actual
    localStorage.setItem('currentPatient', JSON.stringify(patientData));
    
    // Obtener historial de pacientes
    const patientsHistory = JSON.parse(localStorage.getItem('patientsHistory') || '[]');
    
    // Añadir nuevo paciente al historial
    patientsHistory.push({
        medicalRecordNumber: patientData.medicalRecordNumber,
        fullName: patientData.fullName,
        registrationDate: patientData.registrationDate,
        lastVisit: patientData.lastVisit
    });
    
    // Guardar historial actualizado
    localStorage.setItem('patientsHistory', JSON.stringify(patientsHistory));
    
    console.log('✅ Patient data saved:', patientData.medicalRecordNumber);
}

/**
 * Muestra/oculta el indicador de procesamiento
 */
function showProcessingIndicator(show) {
    const indicator = document.getElementById('processing-indicator');
    const submitBtn = document.querySelector('button[type="submit"]');
    
    if (indicator) {
        indicator.style.display = show ? 'block' : 'none';
    }
    
    if (submitBtn) {
        submitBtn.disabled = show;
    }
}

/**
 * Recupera los datos del paciente desde localStorage
 */
function getPatientData(medicalRecordNumber) {
    if (medicalRecordNumber) {
        // Buscar por número de historia clínica
        const currentPatient = JSON.parse(localStorage.getItem('currentPatient') || 'null');
        
        if (currentPatient && currentPatient.medicalRecordNumber === medicalRecordNumber) {
            return currentPatient;
        }
    }
    
    // Retornar paciente actual si existe
    return JSON.parse(localStorage.getItem('currentPatient') || 'null');
}

/**
 * Limpia los datos del paciente (logout)
 */
function clearPatientData() {
    localStorage.removeItem('currentPatient');
    console.log('✅ Patient data cleared');
}

// Exportar funciones para uso global
window.getPatientData = getPatientData;
window.clearPatientData = clearPatientData;
window.generateMedicalRecordNumber = generateMedicalRecordNumber;
