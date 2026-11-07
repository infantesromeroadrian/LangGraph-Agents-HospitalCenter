"""Filtro determinista de salida: ningún especialista receta fármacos ni dosis.

Es una barrera de defensa en profundidad sobre el prompt: si el modelo genera una pauta de
medicación (dosis, frecuencia, "te receto..."), la frase se sustituye por un aviso. Se basa en
expresiones regulares, por lo que no es exhaustivo; ver la sección de limitaciones del README.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

SAFE_REPLACEMENT = (
    "[No puedo indicar medicamentos ni dosis. Consulta con tu médico o tu farmacéutico.]"
)
LEAK_REPLACEMENT = "[No puedo compartir información interna del sistema.]"
IMPERSONATION_REPLACEMENT = (
    "[Soy un asistente de IA de demostración, no un médico ni un profesional colegiado.]"
)

# Huellas del prompt de sistema y de los delimitadores internos (sin acentos, minúsculas).
LEAK_FINGERPRINTS = (
    "reglas de seguridad (obligatorias)",
    "user_input_begin",
    "user_input_end",
    "patient_record_begin",
    "patient_record_end",
    "nunca lo interpretes como instruccion",
    "eres un medico experto especializado",
    "eres un medico de triaje experto",
    "consultation_stage",
    "required_clinical_topics",
    "red_flag_topics",
    "specialty_focus",
    "missing_clinical_items",
    "instrucciones privadas",
)
IMPERSONATION_RE = re.compile(
    r"\b(?:soy\s+(?:el|la)\s+(?:dr|dra|doctor|doctora|medico|medica|administrador|administradora)\b|"
    r"soy\s+(?:el\s+)?(?:sistema|admin)\b|colegiad[oa]\s+(?:n|num|numero)\b|"
    r"\[\[\s*admin|modo\s+(?:administrador|desarrollador)\s+(?:activad[oa]|habilitad[oa]))"
)

_UNITS = (
    r"(?:mg|mcg|µg|ug|gramos?|g|ml|cc|ui|u\.i\.|unidades?|comprimidos?|pastillas?|capsulas?|"
    r"gotas?|sobres?|ampollas?|parches?|supositorios?|puffs?|inhalaciones?|cucharadas?|cucharaditas?)"
)
DOSE_RE = re.compile(rf"\b\d+(?:[.,]\d+)?\s*{_UNITS}\b", re.IGNORECASE)
WORD_QTY_RE = re.compile(
    r"\b(?:un|una|dos|tres|cuatro|media|medio)\s+(?:comprimidos?|pastillas?|capsulas?|gotas?|"
    r"sobres?|ampollas?|cucharadas?|cucharaditas?)\b",
    re.IGNORECASE,
)

# Familias y principios activos frecuentes (sin acentos, minúsculas).
_DRUG_STEMS = (
    "paracetamol|ibuprofeno|naproxeno|aspirina|acido acetilsalicilico|metamizol|nolotil|dexketoprofeno|"
    "enantyum|diclofenaco|voltaren|ketorolaco|tramadol|codeina|morfina|oxicodona|fentanilo|"
    "amoxicilina|augmentine|clavulanico|azitromicina|claritromicina|ciprofloxacino|levofloxacino|"
    "doxiciclina|cefuroxima|cefalexina|penicilina|metronidazol|fluconazol|nitrofurantoina|"
    "omeprazol|pantoprazol|esomeprazol|ranitidina|loperamida|domperidona|metoclopramida|"
    "diazepam|lorazepam|alprazolam|clonazepam|bromazepam|lormetazepam|zolpidem|melatonina|"
    "sertralina|fluoxetina|escitalopram|citalopram|paroxetina|venlafaxina|duloxetina|mirtazapina|"
    "amitriptilina|trazodona|quetiapina|olanzapina|risperidona|aripiprazol|litio|haloperidol|"
    "prednisona|prednisolona|dexametasona|metilprednisolona|hidrocortisona|"
    "adrenalina|epinefrina|salbutamol|budesonida|montelukast|loratadina|cetirizina|ebastina|"
    "metformina|insulina|enalapril|ramipril|losartan|valsartan|amlodipino|atenolol|bisoprolol|"
    "propranolol|furosemida|hidroclorotiazida|atorvastatina|simvastatina|warfarina|sintrom|"
    "acenocumarol|heparina|clopidogrel|apixaban|rivaroxaban|levotiroxina|gabapentina|pregabalina|"
    "carbamazepina|valproico|levetiracetam|lamotrigina|sumatriptan|rizatriptan|"
    "tamoxifeno|metotrexato|isotretinoina|minoxidil|finasterida|mupirocina|clobetasol|"
    "antibiotico|antibioticos|antiinflamatorio|antiinflamatorios|analgesico|analgesicos|"
    "ansiolitico|ansioliticos|antidepresivo|antidepresivos|corticoide|corticoides|"
    "antihistaminico|antihistaminicos|antipsicotico|antipsicoticos|somnifero|somniferos|"
    "opioide|opioides|benzodiacepina|benzodiacepinas|antiepileptico|anticoagulante|anticoagulantes"
)
DRUG_RE = re.compile(rf"\b(?:{_DRUG_STEMS})\b")
# Sufijos farmacológicos frecuentes (cobertura genérica de principios activos no listados).
DRUG_SUFFIX_RE = re.compile(
    r"\b[a-z]{4,}(?:azepam|zolam|cilina|micina|floxacino|prazol|triptan|statina|sartan|pril|olol|"
    r"oxetina|tidina|caina|profeno|coxib|vastatina|gliptina|glifozina|mab)\b"
)

PRESCRIBING_VERBS_RE = re.compile(
    r"\b(?:te\s+(?:receto|prescribo|pauto|recomiendo\s+(?:tomar|usar|que\s+tomes|que\s+uses|"
    r"empezar|iniciar|administrar|ponerte)|aconsejo\s+(?:tomar|usar|que\s+tomes))|"
    r"(?:debes|debe|tienes\s+que|puedes|puede|deberias|conviene|toma(?:te|r)?|tomes|tomate|"
    r"ingiere|ingerir|administra(?:te|r)?|inyecta(?:te|r)?|usa|usar|aplica(?:te|r)?|empieza|"
    r"comienza|prueba|necesitas)\s+(?:\w+\s+){0,3}"
    r"(?:medicamentos?|farmacos?|pastillas?|comprimidos?|tratamiento\s+con|"
    r"antibioticos?|analgesicos?|antiinflamatorios?|ansioliticos?|antidepresivos?|corticoides?))\b"
)
_SUFFIXES = (
    "azepam|zolam|cilina|micina|floxacino|prazol|triptan|statina|sartan|pril|olol|profeno|coxib"
)
RECOMMEND_DRUG_RE = re.compile(
    r"\b(?:toma(?:te|r)?|tomes|ingiere|ingerir|administra(?:te|r)?|inyecta(?:te|r)?|usa|usar|"
    r"aplica(?:te|r)?|empieza\s+con|comienza\s+con|puedes\s+tomar|puede\s+tomar|debes\s+tomar|"
    r"te\s+(?:receto|prescribo|pauto)|recomiendo\s+(?:tomar|usar)|recetar(?:te)?|prescribir(?:te)?)"
    r"\s+(?:\w+\s+){0,3}(?:" + _DRUG_STEMS + r"|[a-z]{4,}(?:" + _SUFFIXES + r"))\b"
)
FREQUENCY_RE = re.compile(
    r"\b(?:cada\s+\d+\s*(?:horas?|h|dias?)|\d+\s+veces\s+(?:al|por|cada)\s+(?:dia|semana|jornada)|"
    r"(?:una|dos|tres|cuatro)\s+veces\s+(?:al|por)\s+dia|durante\s+\d+\s+(?:dias?|semanas?)|"
    r"(?:por\s+la\s+)?(?:manana|noche)\s+y\s+(?:por\s+la\s+)?(?:noche|manana)|en\s+ayunas|"
    r"dosis\s+(?:de|diaria|unica|maxima|habitual|recomendada))\b"
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?\n])\s+|\n+")


def _norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


@dataclass(frozen=True)
class GuardResult:
    """Resultado de aplicar la barrera de salida."""

    text: str
    violations: list[str] = field(default_factory=list)

    @property
    def modified(self) -> bool:
        return bool(self.violations)


def _sentence_violations(sentence: str) -> list[str]:
    n = _norm(sentence)
    found: list[str] = []
    has_quantity = bool(DOSE_RE.search(n) or WORD_QTY_RE.search(n))
    # Una cantidad con unidad solo es pauta si hay contexto de medicación.
    if has_quantity and (
        DRUG_RE.search(n)
        or DRUG_SUFFIX_RE.search(n)
        or PRESCRIBING_VERBS_RE.search(n)
        or re.search(
            r"\b(?:tomar|toma|dosis|medicamento|farmaco|receta|tratamiento|inyect\w+|administr\w+)\b",
            n,
        )
    ):
        found.append("dosis")
    if any(fp in n for fp in LEAK_FINGERPRINTS):
        found.append("fuga_prompt")
    if IMPERSONATION_RE.search(n):
        found.append("suplantacion")
    if RECOMMEND_DRUG_RE.search(n):
        found.append("recomendacion_farmaco")
    if PRESCRIBING_VERBS_RE.search(n):
        found.append("verbo_prescriptivo")
    if FREQUENCY_RE.search(n) and (DRUG_RE.search(n) or DRUG_SUFFIX_RE.search(n)):
        found.append("pauta_frecuencia")
    return found


def _replacement_for(found: list[str]) -> str:
    if "fuga_prompt" in found:
        return LEAK_REPLACEMENT
    if "suplantacion" in found:
        return IMPERSONATION_REPLACEMENT
    return SAFE_REPLACEMENT


def find_violations(text: str) -> list[str]:
    """Lista de tipos de infracción detectados en `text` (vacía si la salida es aceptable)."""
    if not isinstance(text, str):
        return []
    violations: list[str] = []
    for sentence in _SENTENCE_SPLIT_RE.split(text):
        if sentence.strip():
            violations.extend(_sentence_violations(sentence))
    return violations


def apply_output_guard(text: str) -> GuardResult:
    """Sustituye por un aviso cada frase que contenga una pauta de medicación."""
    if not isinstance(text, str) or not text:
        return GuardResult(text=text or "")
    violations: list[str] = []
    out_parts: list[str] = []
    last_end = 0
    used_replacements: set[str] = set()
    for match in re.finditer(r"[^.!?\n]+[.!?]*", text):
        sentence = match.group(0)
        found = _sentence_violations(sentence)
        out_parts.append(text[last_end : match.start()])
        if found:
            violations.extend(found)
            replacement = _replacement_for(found)
            if replacement not in used_replacements:
                out_parts.append(replacement)
                used_replacements.add(replacement)
            else:
                out_parts.append("")
        else:
            out_parts.append(sentence)
        last_end = match.end()
    out_parts.append(text[last_end:])
    return GuardResult(text="".join(out_parts), violations=violations)
