# 📚 ÍNDICE DE DOCUMENTACIÓN - LangGraph Medical Center

Este directorio contiene **toda la documentación histórica** del proyecto: migraciones, decisiones de arquitectura, resúmenes de sesiones, y planes de desarrollo.

---

## 📋 ESTRUCTURA DE DOCUMENTOS

### **🏗️ ARQUITECTURA Y PLANES**

| Documento | Descripción | Estado |
|-----------|-------------|--------|
| [PLAN-AGENT.md](PLAN-AGENT.md) | Plan maestro de arquitectura multi-agente (Fases 1-5) | ✅ En progreso |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Guía de desarrollo local (setup, comandos, workflows) | ✅ Actualizado |

---

### **🔄 MIGRACIONES TÉCNICAS**

| Documento | Descripción | Fecha | Estado |
|-----------|-------------|-------|--------|
| [FASTAPI_MIGRATION.md](FASTAPI_MIGRATION.md) | Migración Flask→FastAPI (event loop fix) | 27-Dic-2025 | ✅ Completado |
| [DOCKER_UV_MIGRATION.md](DOCKER_UV_MIGRATION.md) | Migración pip→uv en Docker | 27-Dic-2025 | ✅ Completado |
| [MIGRATION_SUMMARY_UV.md](MIGRATION_SUMMARY_UV.md) | Resumen migración uv (package manager) | 27-Dic-2025 | ✅ Completado |
| [MIGRATION_SUMMARY.md](MIGRATION_SUMMARY.md) | Resumen general de migraciones | 27-Dic-2025 | ✅ Completado |

---

### **🎨 MEJORAS DE UX/UI**

| Documento | Descripción | Fecha | Estado |
|-----------|-------------|-------|--------|
| [VISUAL_REDESIGN_SUMMARY.md](VISUAL_REDESIGN_SUMMARY.md) | Rediseño visual hospital theme | 28-Dic-2025 | ✅ Completado |
| [EMERGENCY_AND_ADMISSION_SUMMARY.md](EMERGENCY_AND_ADMISSION_SUMMARY.md) | Botón emergencia + admisión | 28-Dic-2025 | ✅ Completado |

---

### **🏥 SISTEMA DE PACIENTES**

| Documento | Descripción | Fecha | Estado |
|-----------|-------------|-------|--------|
| [PATIENT_REGISTRATION_BACKEND.md](PATIENT_REGISTRATION_BACKEND.md) | Backend API de pacientes (PostgreSQL) | 28-Dic-2025 | ✅ Completado |
| [PATIENT_REGISTRATION_COMPLETE.md](PATIENT_REGISTRATION_COMPLETE.md) | **Sistema completo** (frontend + backend + LLM context) | 28-Dic-2025 | ✅ Completado |

---

### **🔧 CONFIGURACIÓN Y REFACTORS**

| Documento | Descripción | Fecha | Estado |
|-----------|-------------|-------|--------|
| [RENAME_ENV_VARS.md](RENAME_ENV_VARS.md) | Renombrado variables de entorno | 27-Dic-2025 | ✅ Completado |
| [REPOSITORY_STATUS.md](REPOSITORY_STATUS.md) | Estado del repositorio (snapshot) | 27-Dic-2025 | ℹ️ Referencia |

---

### **⚠️ PROBLEMAS CONOCIDOS**

| Documento | Descripción | Estado |
|-----------|-------------|--------|
| [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | Lista de issues abiertos + workarounds | 🔄 Actualizar |

---

## 🗂️ ORGANIZACIÓN POR SESIONES

Si quieres ver la **historia cronológica** completa:

```
historyMD/
├── sessions/           # Logs de sesiones de desarrollo
│   ├── 2025-12-27/
│   └── 2025-12-28/
├── PLAN-AGENT.md       # Master plan
├── FASTAPI_MIGRATION.md
├── PATIENT_REGISTRATION_COMPLETE.md  # ← ÚLTIMO DOCUMENTO IMPORTANTE
└── INDEX.md            # ← Este archivo
```

---

## 🎯 ÚLTIMO CAMBIO IMPORTANTE

**28-Dic-2025:** Sistema de Registro de Pacientes completado.

✅ **¿Qué se hizo?**
- Modal de admisión obligatorio (antesala)
- API REST completa (`/api/patients`)
- Inyección de contexto en LLM (alergias, medicación, antecedentes)
- Persistencia en PostgreSQL con HC autogenerada

📖 **Ver:** [PATIENT_REGISTRATION_COMPLETE.md](PATIENT_REGISTRATION_COMPLETE.md)

---

## 📖 CÓMO USAR ESTE ÍNDICE

1. **Si necesitas entender una migración anterior:** Busca en la sección "Migraciones Técnicas"
2. **Si quieres saber el roadmap:** Lee `PLAN-AGENT.md`
3. **Si necesitas setup local:** Lee `DEVELOPMENT.md`
4. **Si quieres ver el último feature implementado:** Lee `PATIENT_REGISTRATION_COMPLETE.md`

---

## ✅ CHECKLIST DE DOCUMENTACIÓN

Cada vez que implementes un feature importante, crea un documento `.md` en `historyMD/` con:

- [ ] **Título claro** (ej: `FEATURE_XYZ_IMPLEMENTATION.md`)
- [ ] **Fecha** de implementación
- [ ] **Objetivo** (qué problema resuelve)
- [ ] **Cambios realizados** (archivos modificados, líneas de código)
- [ ] **Cómo probar** (instrucciones paso a paso)
- [ ] **Próximos pasos** (mejoras futuras)

---

**Autor:** AI Engineer (Madrid Senior Mode)  
**Última actualización:** 28-Dic-2025  
**Total de documentos:** 14
