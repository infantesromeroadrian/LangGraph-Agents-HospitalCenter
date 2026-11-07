"""Detección determinista de signos de alarma y mensajes de escalada a urgencias.

Diseño:
- Es una función pura sobre texto: no usa LLM, red, estado del grafo ni configuración,
  de modo que ni el modelo ni el texto del paciente pueden desactivarla.
- Se ejecuta antes de cualquier conversación con especialistas (nodo `safety_gate`).
- Prioriza sensibilidad sobre especificidad: ante la duda se escala. Las reglas buscan
  combinaciones clínicas (p. ej. dolor torácico + síntomas vegetativos), no palabras sueltas.
- Cubre solo español. No sustituye el juicio clínico ni es un producto sanitario.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

EMERGENCY_NUMBER = "112"
SUICIDE_LINE = "024"

CHEST_PAIN = "dolor_toracico"
STROKE = "focalidad_neurologica"
SUICIDE = "ideacion_suicida"
INFANT_FEVER = "fiebre_lactante"
ANAPHYLAXIS = "anafilaxia"
RESPIRATORY = "dificultad_respiratoria_grave"
SEIZURE_SYNCOPE = "convulsion_o_inconsciencia"
BLEEDING = "hemorragia_grave"
OVERDOSE = "intoxicacion_sobredosis"

CATEGORIES = (
    CHEST_PAIN,
    STROKE,
    SUICIDE,
    INFANT_FEVER,
    ANAPHYLAXIS,
    RESPIRATORY,
    SEIZURE_SYNCOPE,
    BLEEDING,
    OVERDOSE,
)

_ZERO_WIDTH = dict.fromkeys(
    [0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF, 0x00AD, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E],
    None,
)
_LEET = str.maketrans(
    {"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"}
)


@dataclass(frozen=True)
class RedFlag:
    """Un signo de alarma detectado."""

    category: str
    rule: str


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _deleet_token(match: re.Match[str]) -> str:
    token = match.group(0)
    # Solo tokens que mezclan letras y dígitos ("s0lo", "m0rirm3"); no se tocan "38,5" ni "2 meses".
    if any(c.isalpha() for c in token) and any(c.isdigit() or c in "@$" for c in token):
        return token.translate(_LEET)
    return token


def _join_spaced_letters(text: str) -> str:
    """Une secuencias de letras sueltas separadas por espacios o puntos: 's u i c i d i o'."""
    return re.sub(
        r"(?<![a-z0-9])(?:[a-z][ .\-_]){3,}[a-z](?![a-z0-9])",
        lambda m: re.sub(r"[ .\-_]", "", m.group(0)),
        text,
    )


def normalize(text: str) -> str:
    """Minúsculas, sin acentos ni caracteres invisibles, espacios colapsados."""
    text = text.translate(_ZERO_WIDTH)
    text = _strip_accents(text).casefold()
    text = re.sub(r"[^\w\s@$,.;:!?¿¡%/\-]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _spaced_letters_view(text: str) -> str:
    """Une letras sueltas separadas por un espacio conservando los huecos de 2 o más espacios."""
    stripped = _strip_accents(text.translate(_ZERO_WIDTH)).casefold()
    joined = re.sub(
        r"(?<![^\W_])((?:[^\W_][ .\-_]){2,}[^\W_])(?![^\W_])",
        lambda m: re.sub(r"[ .\-_]", "", m.group(1)),
        stripped,
    )
    return re.sub(r"\s+", " ", joined).strip()


def _views(text: str) -> list[str]:
    """Texto normalizado en varias vistas para resistir ofuscación sencilla."""
    base = normalize(text)
    deleeted = re.sub(r"[\w@$]+", _deleet_token, base)
    joined = _join_spaced_letters(deleeted)
    # Letras alargadas: "suiciiiidio" -> "suicidio"
    squeezed = re.sub(r"([a-z])\1{2,}", r"\1", joined)
    views = [base]
    for candidate in (deleeted, joined, squeezed, _spaced_letters_view(text)):
        if candidate not in views:
            views.append(candidate)
    return views


# --- Utilidades de patrón -------------------------------------------------------------

_W = r"(?:\s+\w+){0,%d}"  # hasta N palabras intermedias


def _near(a: str, b: str, gap: int = 6) -> str:
    """a seguido de b (o b seguido de a) con hasta `gap` palabras entre medias."""
    mid = _W % gap
    return rf"(?:(?:{a}){mid}\s+(?:{b})|(?:{b}){mid}\s+(?:{a}))"


def _re(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern)


# Negación solo si el negador está pegado al término (como mucho un verbo ligero y un determinante).
# Evita que un prefijo del usuario del tipo "NO ESCALES ..." anule la detección.
NEGATION_WINDOW = re.compile(
    r"\b(?:no|nunca|ni|sin|descarto|niego|tampoco|jamas)\s+"
    r"(?:(?:tengo|tiene|tienes|tenemos|siento|noto|presento|hay|existe|sufro|padezco|"
    r"he\s+tenido|ha\s+tenido|con|de|es|esta|ni)\s+)?"
    r"(?:(?:un|una|unos|unas|ningun|ninguna|ningunos|ningunas|el|la|los|las|algun|alguna|mucho|"
    r"mucha|ese|esa|este|esta|mi|su|otro|otra)\s+)?"
    r"(?:(?:ni|ningun|ninguna|un|una)\s+)?$"
)
CHRONIC_MARKERS = _re(
    r"\b(?:desde hace (?:meses|anos|mucho)|hace\s+(?:\w+\s+)?(?:anos|meses)|diagnostic\w+|secuelas?|antiguo|cronic[oa]s?|"
    r"de (?:nino|nina|pequeno|pequena|joven)|ya paso|resuelto|hace tiempo|operacion)\b"
)


def _negated(view: str, start: int) -> bool:
    """¿El término que empieza en `start` está negado justo antes (p. ej. 'no tengo dolor')?"""
    prefix = view[max(0, start - 40) : start]
    return bool(NEGATION_WINDOW.search(prefix))


def _any_unnegated(pattern: re.Pattern[str], view: str) -> bool:
    return any(not _negated(view, m.start()) for m in pattern.finditer(view))


# --- Reglas ----------------------------------------------------------------------------

_CHEST_TERM = (
    r"(?:dolor(?:es)?|opresion|presion|apreton\w*|estruj\w+|estrangul\w+|pinchazos?|punzadas?|molestia|peso|losa|piedra|bloque|garra|aplastamiento|"
    r"quemazon|ardor|quema|tirantez|dolia|duele|duelen|oprime|aprieta|aprieto|apretando|"
    r"oprimiendo)"
)
_CHEST_PLACE = r"(?:pecho|torax|toracic[oa]|esternon|precordial|corazon|retroesternal)"
CHEST_PAIN_RE = _re(
    r"(?:" + _near(_CHEST_TERM, _CHEST_PLACE, 5) + r"|(?:pecho|torax|corazon)\s+(?:me\s+)?"
    r"(?:duele|oprime|aprieta|arde)|elefante\s+(?:sobre|en)\s+(?:el\s+)?pecho|"
    r"(?:se\s+)?(?:agarra|aprieta|coge|sujeta|lleva\s+la\s+mano\s+a)\w*\s+(?:el\s+)?(?:pecho|torax))"
)
CHEST_ASSOCIATED_RE = _re(
    r"\b(?:sudor\w*|empapad\w+\s+en\s+sudor|cara\s+(?:blanca|palida|grisacea)|piel\s+(?:gris\w*|fria|palida)|"
    r"coger\s+(?:el\s+)?aire|me\s+cuesta\s+(?:\w+\s+)?(?:respirar|aire)|sudor(?:acion)?\s+fri[oa]|sudando\s+(?:frio|mucho)|sudor\s+frio|sudoracion|sudo\s+frio|"
    r"suda(?:ndo)?\s+(?:frio|mucho)|nauseas?|vomit\w*|ganas\s+de\s+vomitar|"
    r"falta\s+de\s+(?:aire|aliento)|(?:me|le|te)\s+falta\s+(?:el\s+)?(?:aire|aliento)|ahogo|ahogando|"
    r"dificultad\s+para\s+respirar|no\s+puedo\s+respirar|mare\w+|"
    r"desmay\w*|palid\w+|hormigue\w+|"
    r"(?:irradia|irradiando|baja|sube|se\s+extiende|se\s+va|hacia|al|en\s+el)\s+(?:\w+\s+){0,3}"
    r"(?:brazo|mandibula|cuello|espalda|hombro)|(?:brazo|mandibula|cuello)\s+(?:izquierdo\s+)?"
    r"(?:dormido|duele|con dolor)|palpitaciones|taquicardia|angustia\s+intensa|"
    r"sensacion\s+de\s+muerte|presentimiento\s+de\s+muerte)\b"
)
HEART_ATTACK_SELF_RE = _re(
    r"\b(?:infarto|ataque\s+(?:al\s+)?corazon|ataque\s+cardiaco|angina\s+de\s+pecho)\b"
)
HEART_ATTACK_DENY_RE = _re(
    r"\b(?:antecedentes?|historial|familiar|mi\s+(?:padre|madre|abuelo|abuela|tio|tia|hermano)|"
    r"tuvo|tuve|miedo\s+a|prevenir|prevencion|riesgo|factores?)\b"
)

STROKE_STRONG_RE = _re(
    r"\b(?:"
    r"(?:no\s+articula\w*|dice\s+cosas\s+sin\s+sentido|dice\s+incoherencias|no\s+(?:puede|puedo)\s+cerrar(?:la|lo)?\s+(?:la\s+)?mano)|"
    r"(?:cara|boca|rostro)\s+(?:\w+\s+){0,5}(?:caida|caido|torcida|torcido|desviada|desviado)|"
    r"comisura\s+(?:de\s+)?(?:la\s+)?boca|"
    r"no\s+(?:me\s+|le\s+)?mueve\s+(?:el\s+|la\s+)?(?:brazo|pierna|mano)|"
    r"dejado\s+de\s+poder\s+(?:hablar|mover)|"
    r"empe\w+\s+a\s+no\s+(?:entender|comprender)|"
    r"palabras\s+(?:me\s+)?salen\s+(?:al\s+reves|mal|trabadas|enredadas)|"
    r"habl\w+\s+como\s+(?:un\s+)?(?:borrach\w+|ebri\w+)|"
    r"(?:nublad\w+|borros\w+)\s+(?:la\s+)?vista\s+(?:\w+\s+){0,2}(?:de\s+)?un\s+ojo|"
    r"(?:cara|boca|labio|rostro)\s+(?:\w+\s+){0,2}(?:torcid[ao]|caid[ao]|caida|desviad[ao]|deformad[ao])|"
    r"(?:se\s+me\s+)?(?:ha\s+)?(?:torcido|caido|caida)\s+(?:\w+\s+){0,2}(?:la\s+)?(?:cara|boca)|"
    r"no\s+(?:puedo|consigo|puede|consigue|logra|logro)\s+(?:mover|levantar|sentir)\s+(?:\w+\s+){0,2}"
    r"(?:brazo|pierna|mano|pie|lado)|"
    r"(?:brazo|pierna|mano)\s+(?:\w+\s+){0,3}(?:flojo|floja|sin\s+fuerza|dormid[ao]|paralizad[ao]|"
    r"no\s+(?:me\s+)?responde)|"
    r"(?:debilidad|paralisis|entumecimiento|hormigueo|adormecimiento|falta\s+de\s+fuerza)\s+"
    r"(?:\w+\s+){0,3}(?:un\s+lado|mitad|medio\s+cuerpo|hemicuerpo|lado\s+(?:izquierdo|derecho))|"
    r"(?:no\s+(?:puedo|consigo)\s+hablar|no\s+me\s+salen\s+las\s+palabras|"
    r"hablo\s+(?:raro|mal|enredado|arrastrando)|habla\s+(?:arrastrada|rara|confusa|torpe)|"
    r"lengua\s+(?:trabada|torpe|de\s+trapo)|"
    r"(?:no\s+(?:entiendo|comprendo))\s+(?:lo\s+que|nada\s+de\s+lo\s+que)\s+(?:me\s+)?(?:dicen|hablan|oigo)|"
    r"dificultad\s+(?:\w+\s+){0,2}para\s+(?:hablar|articular|entender))|"
    r"(?:perdida|perdido)\s+(?:\w+\s+){0,2}(?:de\s+)?vision\s+(?:\w+\s+){0,2}(?:brusca|repentina|subita)|"
    r"(?:no\s+veo\s+(?:nada\s+)?(?:con|por|de)\s+un\s+ojo|vision\s+doble\s+(?:de\s+)?(?:repente|subita))|"
    r"(?:ictus|derrame\s+cerebral|accidente\s+cerebrovascular|trombosis\s+cerebral)|"
    r"(?:peor\s+dolor\s+de\s+cabeza\s+(?:de\s+)?(?:mi|toda\s+mi)\s+vida|"
    r"dolor\s+de\s+cabeza\s+(?:\w+\s+){0,2}(?:fulminante|explosivo|como\s+un\s+(?:golpe|trueno|martillazo)))"
    r")\b"
)
STROKE_WEAK_RE = _re(
    r"\b(?:hormigueo|adormecimiento|dormid[ao]|entumecid[ao]|flojo|floja|torpe|mareo\s+intenso)\b"
)
STROKE_SUDDEN_RE = _re(
    r"\b(?:de\s+repente|derrepente|de\s+golpe|subit\w+|brusc\w+|repentin\w+|hace\s+(?:unos\s+)?"
    r"(?:\d+\s+)?(?:minutos?|un\s+rato)|ahora\s+mismo|de\s+pronto|en\s+segundos)\b"
)
STROKE_SIDE_RE = _re(
    r"\b(?:un\s+lado|mitad\s+del\s+cuerpo|brazo\s+(?:izquierdo|derecho)|pierna\s+(?:izquierda|derecha)|"
    r"cara|boca|hablar|palabras)\b"
)

SUICIDE_RE = _re(
    r"\b(?:"
    r"(?:quiero|quisiera|querria|deseo|tengo\s+ganas\s+de|me\s+gustaria)\s+(?:\w+\s+){0,2}"
    r"(?:morir(?:me)?|desaparecer\s+para\s+siempre|no\s+despertar(?:me)?|dejar\s+de\s+existir|"
    r"acabar\s+con\s+(?:mi\s+vida|todo)|terminar\s+con\s+(?:mi\s+vida|todo)|quitarme\s+la\s+vida|"
    r"matarme|suicidarme)|"
    r"me\s+quiero\s+(?:morir|matar)|"
    r"(?:ganas|deseos?|ideas?|pensamientos?)\s+(?:\w+\s+){0,2}(?:de\s+)?(?:morir(?:me)?|matarme|"
    r"suicid\w+|quitarme\s+la\s+vida|acabar\s+con\s+mi\s+vida)|"
    r"no\s+(?:quiero|puedo|aguanto|soporto)\s+(?:\w+\s+){0,2}(?:seguir|continuar)?\s*(?:viviendo|vivir)|"
    r"no\s+quiero\s+estar\s+(?:aqui|vivo|viva)\s+(?:mas|ya)|"
    r"(?:seria|sera|estaria|estaria)\s+mejor\s+(?:\w+\s+){0,1}(?:despertar|morir|muerto|muerta|desaparecer|no\s+existir|no\s+estar\s+aqui)|"
    r"(?:ojala|desearia)\s+(?:\w+\s+){0,2}(?:no\s+despertar|no\s+haber\s+nacido|morir|desaparecer)|"
    r"quit\w+(?:me)?\s+de\s+en\s+medio|"
    r"tirarme\s+(?:por|desde|de)\s+(?:\w+\s+){0,2}(?:ventana|balcon|puente|azotea|terraza|edificio)|"
    r"no\s+quiero\s+seguir\s+(?:aqui|asi|adelante|con\s+esto)|"
    r"no\s+(?:quiero\s+)?volver\s+a\s+despertar(?:me)?|"
    r"prefier\w+\s+(?:estar\s+)?(?:muert\w+|morir(?:se)?)|"
    r"(?:quiero|voy\s+a|ganas\s+de|quiere)\s+(?:\w+\s+){0,1}hacer(?:me|se)\s+(?:dano|mal)(?:\s+(?:de\s+forma\s+)?(?:grave|serio))?|"
    r"(?:cuchilla|navaja)\s+(?:\w+\s+){0,2}(?:preparada|para\s+cortarme)|"
    r"(?:forma|manera|metodo)s?\s+(?:\w+\s+){0,4}(?:quitarse\s+la\s+vida|matarse|suicidarse|morirse)|"
    r"no\s+(?:le\s+)?encuentro\s+(?:ya\s+)?sentido\s+(?:a\s+)?(?:seguir|vivir|la\s+vida|continuar)|"
    r"(?:ya\s+)?no\s+merece\s+(?:la\s+)?pena\s+(?:seguir\s+)?(?:vivir|viviendo|nada)|"
    r"(?:mejor|estarian\s+mejor|estaria\s+mejor)\s+(?:\w+\s+){0,3}sin\s+mi|"
    r"(?:se\s+(?:va\s+a|quiere|ha\s+querido)|va\s+a)\s+(?:matar|suicidar|quitar\s+la\s+vida|morir)(?:se)?|"
    r"(?:quiere|quieren)\s+(?:matarse|morirse|suicidarse|quitarse\s+la\s+vida|acabar\s+con\s+su\s+vida)|"
    r"(?:me\s+voy\s+a|voy\s+a)\s+(?:matar(?:me)?|suicidar(?:me)?|quitarme\s+la\s+vida|acabar\s+con\s+todo)|"
    r"(?:voy\s+a|pienso)\s+(?:\w+\s+){0,2}(?:quitarme\s+la\s+vida|suicidarme)|"
    r"(?:me\s+)?(?:he\s+)?(?:pensado|planeado|decidido)\s+(?:\w+\s+){0,3}(?:suicid\w+|matarme|"
    r"quitarme\s+la\s+vida|acabar\s+con\s+mi\s+vida)|"
    r"(?:suicid(?:io|arme|ar|arse|a|e|ado)|autolesion\w*|hacerme\s+dano|cortarme\s+las\s+venas)|"
    r"(?:como|formas?\s+de|maneras?\s+de|metodos?\s+(?:para|de))\s+(?:\w+\s+){0,2}"
    r"(?:morir(?:me)?|matarme|suicidarme|quitarme\s+la\s+vida|acabar\s+con\s+mi\s+vida)|"
    r"(?:he\s+)?(?:tomado|tragado|ingerido)\s+(?:\w+\s+){0,3}(?:para\s+(?:morir|matarme|acabar\s+con\s+todo))|"
    r"nota\s+de\s+despedida|carta\s+de\s+despedida|despedirme\s+de\s+todos"
    r")\b"
)
SUICIDE_BENIGN_RE = _re(
    r"(?:morir(?:me)?|matar(?:me)?)\s+de\s+(?:verguenza|risa|sueno|hambre|calor|frio|aburrimiento|"
    r"envidia|miedo|pena|ganas|curiosidad|cansancio|sed|vergenza)|"
    r"(?:prevencion|prevenir|protocolo|estadisticas?|noticia|pelicula|serie|novela|libro)\s+"
    r"(?:\w+\s+){0,3}suicid|"
    r"suicid\w*\s+(?:\w+\s+){0,3}(?:estadisticas?|noticia|pelicula|serie|novela|libro|tasa)"
)
SUICIDE_NEGATED_STEM_RE = _re(
    r"\b(?:suicid\w*|matarme|quitarme\s+la\s+vida|autolesion\w*|hacerme\s+dano)\b"
)
SUICIDE_NEGATION_RE = _re(
    r"\b(?:no|nunca|ni|sin|descarto|niego|tampoco|jamas)\b(?:\s+(?!y\b|pero\b|aunque\b)\w+){0,2}\s+"
    r"(?:pensado|pienso|tengo|tenido|hay|existen|existe|quiero|voy\s+a|me\s+planteo|"
    r"idea|ideas|ganas|intencion|intenciones|planes|pensamientos)\b(?:\s+\w+){0,4}\s+"
    r"(?:suicid\w*|matarme|quitarme\s+la\s+vida|autolesion\w*|hacerme\s+dano)\b"
)


_AGE_NUM = (
    r"(?:\d{1,2}|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|"
    r"catorce|quince|veinte|veintiun[oa]?|treinta)"
)
_NUM_WORDS = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13,
    "catorce": 14, "quince": 15, "veinte": 20, "veintiun": 21, "veintiuno": 21, "veintiuna": 21,
    "treinta": 30,
}  # fmt: skip
INFANT_AGE_RE = _re(rf"\b({_AGE_NUM})\s+(dias?|semanas?|meses|mes)\b")
MES_Y_MEDIO_RE = _re(r"\b(?:un\s+)?mes\s+y\s+medio\b")
NACIO_HACE_RE = _re(rf"\bnacio\s+hace\s+({_AGE_NUM})\s+(dias?|semanas?|meses|mes)\b")
JUST_TURNED_MONTH_RE = _re(r"\bacaba\s+de\s+cumplir\s+(?:un|1)\s+mes\b")
NEWBORN_RE = _re(r"\b(?:recien\s+nacid[oa]|neonato|neonatal)\b")
FEVER_RE = _re(
    r"\b(?:fiebre|febril|calentura|fiebron|temperatura\s+alta|esta\s+ardiendo|ardiendo\s+en\s+fiebre)\b"
)
NO_FEVER_RE = _re(
    r"\b(?:sin\s+fiebre|afebril|no\s+(?:tiene|tengo|ha\s+tenido|hay)\s+fiebre|sin\s+calentura)\b"
)
TEMP_RE = _re(r"\b(3[89]|4[0-2])(?:[.,]\d)?\s*(?:grados|gr|c|º|°)?\b")
BABY_TERMS_RE = _re(
    r"\b(?:bebe|bebes|lactante|nene|nena|hijo|hija|nino|nina|pequeno|pequena|nieto|nieta|sobrino|sobrina)\b"
)

ANAPH_STRONG_RE = _re(r"\b(?:anafilax\w*|shock\s+anafilactico|anafilactic\w*)\b")
THROAT_CLOSING_RE = _re(
    r"\b(?:se\s+me\s+|me\s+)?(?:cierra|cerrando|esta\s+cerrando|cierre\s+de)\s+(?:\w+\s+){0,2}(?:la\s+)?garganta\b"
)
ANAPH_SWELL_RE = _re(
    r"(?:\b(?:hinch\w+|inflam\w+|hinchazon|inflamacion|edema)\b\s*(?:\w+\s+){0,4}"
    r"\b(?:lengua|garganta|labios?|glotis|cara|parpados?|ojos|cuello)\b|"
    r"\b(?:lengua|garganta|labios?|glotis|cara|parpados?)\b\s*(?:\w+\s+){0,3}"
    r"\b(?:hinchad\w+|inflamad\w+|hincha\w*|enorm\w+|gigantes?|deformad\w+)\b|"
    r"\b(?:se\s+me\s+)?(?:cierra|cerrando|cerrar)\s+(?:\w+\s+){0,2}(?:la\s+)?garganta\b|"
    r"\bgarganta\s+(?:\w+\s+){0,2}(?:cerrada|cerrando|cierra)\b)"
)
ANAPH_COFACTOR_RE = _re(
    r"\b(?:respirar|respiracion|ahog\w+|tragar|trago|voz\s+(?:ronca|rara)|ronquera|silbidos?|sibilancias|"
    r"entra\s+(?:el\s+)?aire|pitidos?|pica\s+(?:todo|por\s+todo)|ronchas|urticaria|habones|picazon|mareo\w*|desmay\w*|vomit\w*|opresion|falta\s+de\s+aire)\b"
)
ANAPH_SYSTEMIC_RE = _re(
    r"\b(?:urticaria|ronchas|habones|erupcion)\s+(?:\w+\s+){0,2}(?:generalizad\w+|por\s+todo\s+el\s+cuerpo|por\s+todas\s+partes)\b"
)
ANAPH_SYSTEMIC_COFACTOR_RE = _re(
    r"\b(?:voz\s+(?:ronca|rara)|desmay\w+|marea\w*|mareo\w*|falta\s+de\s+aire|respirar|tragar|garganta|opresion|vomit\w+)\b"
)
ANAPH_TRIGGER_RE = _re(
    r"\b(?:alergi\w+|picadura|pico|picado|picada|avispa|abeja|cacahuete\w*|marisco|gambas?|"
    r"frutos\s+secos|nueces|penicilina|amoxicilina|latex|huevo|leche|contraste|medicamento|"
    r"inyeccion|despues\s+de\s+comer|tras\s+comer|he\s+comido|comi)\b"
)
RESP_DISTRESS_RE = _re(
    r"\b(?:no\s+puedo\s+respirar|no\s+(?:consigo|logro)\s+respirar|me\s+ahogo|me\s+estoy\s+ahogando|"
    r"dificultad\s+(?:\w+\s+){0,1}(?:severa|grave|importante|intensa|extrema)\s+(?:\w+\s+){0,2}respirar|"
    r"(?:severa|grave|intensa|extrema)\s+dificultad\s+(?:\w+\s+){0,2}respirar|"
    r"labios\s+(?:morados|azules|amoratados)|cara\s+(?:morada|azulada)|cianosis|"
    r"respira\s+(?:muy\s+)?(?:mal|rapido|con\s+dificultad)\s+(?:\w+\s+){0,3}(?:hundiendo|costillas)|"
    r"se\s+le\s+hunden\s+las\s+costillas|aire\s+no\s+me\s+entra)\b"
)
RESP_BENIGN_RE = _re(
    r"(?:no\s+puedo\s+respirar\s+(?:bien\s+)?(?:por|con)\s+(?:la\s+)?(?:nariz|fosa)|"
    r"me\s+ahogo\s+en\s+un\s+vaso\s+de\s+agua|me\s+ahogo\s+(?:de|con)\s+(?:la\s+)?(?:risa|tos\s+leve)|"
    r"nariz\s+(?:\w+\s+){0,2}tapada)"
)

SEIZURE_RE = _re(
    r"\b(?:esta\s+(?:convulsionando|teniendo\s+(?:una\s+)?(?:convulsion|crisis))|"
    r"(?:ha\s+tenido|acaba\s+de\s+tener|he\s+tenido|tuvo|tengo)\s+(?:una\s+)?(?:convulsion|crisis\s+(?:epileptica|convulsiva)|"
    r"ataque\s+epileptico)|convulsion(?:es)?\s+(?:ahora|ahora\s+mismo|que\s+no\s+para)|"
    r"se\s+ha\s+quedado\s+(?:inconsciente|sin\s+sentido)|esta\s+inconsciente|"
    r"se\s+ha\s+desmayado\s+y\s+no\s+(?:despierta|reacciona|responde)|"
    r"se\s+ha\s+(?:desplomado|caido\s+redond\w+)|"
    r"no\s+(?:despierta|reacciona)\b|"
    r"(?:inconsciente|desmayad\w+|desplomad\w+)\b(?:\s+\w+){0,6}\s+no\s+responde|"
    r"perdida\s+de\s+(?:conciencia|conocimiento)\s+(?:\w+\s+){0,2}(?:ahora|hace\s+(?:un\s+)?(?:rato|minutos?)))\b"
)
BLEEDING_RE = _re(
    r"\b(?:vomit\w*\s+(?:con\s+)?sangre|vomitando\s+sangre|escupiendo\s+sangre|tos\s+con\s+(?:mucha\s+)?sangre|tosiendo\s+(?:con\s+)?(?:mucha\s+)?sangre|"
    r"sangre\s+(?:\w+\s+){0,2}(?:no\s+(?:para|se\s+detiene|cesa|deja\s+de)|a\s+chorros|abundante)|"
    r"hemorragia\s+(?:\w+\s+){0,6}(?:no\s+(?:para|se\s+detiene|cesa)|abundante|grave|intensa)|"
    r"(?:sangrado|sangrando)\s+(?:\w+\s+){0,3}(?:abundante|mucho|no\s+para|sin\s+parar|que\s+no\s+para|que\s+no\s+se\s+detiene)|"
    r"heces\s+(?:negras|con\s+mucha\s+sangre)\s+(?:\w+\s+){0,6}(?:mareo\w*|desmay\w*|debil))\b"
)
OVERDOSE_RE = _re(
    r"\b(?:sobredosis|me\s+he\s+tomado\s+(?:\w+\s+){0,3}(?:todas?|muchas)\s+(?:\w+\s+){0,2}"
    r"(?:pastillas|comprimidos|pildoras|medicacion)|"
    r"(?:se\s+ha|se\s+han|ha|han|me\s+he)\s+(?:tomado|bebido|comido|tragado)\s+(?:\w+\s+){0,2}"
    r"(?:bote|caja|blister|tira|frasco)\s+(?:entero|entera|completo|completa)?\s*(?:de\s+)?(?:pastillas|comprimidos|"
    r"medicacion|medicamentos|jarabe)|"
    r"(?:ha|han)\s+tomado\s+(?:\w+\s+){0,3}(?:todas?|muchas)\s+(?:\w+\s+){0,2}(?:pastillas|comprimidos)|"
    r"(?:ha|han)\s+(?:bebido|ingerido|tragado)\s+(?:\w+\s+){0,3}(?:lejia|disolvente|veneno|detergente|"
    r"producto\s+de\s+limpieza|salfuman|quitaesmaltes)|"
    r"(?:he\s+)?(?:bebido|ingerido|tragado)\s+(?:\w+\s+){0,3}(?:lejia|disolvente|veneno|salfuman)|"
    r"intoxicacion\s+(?:aguda|grave)|envenenamiento)\b"
)


def _infant_age_months(view: str) -> float | None:
    """Edad mínima mencionada en meses (None si no hay edad de lactante)."""
    ages: list[float] = []
    for match in INFANT_AGE_RE.finditer(view):
        raw, unit = match.group(1), match.group(2)
        value = float(raw) if raw.isdigit() else float(_NUM_WORDS.get(raw, 99))
        if unit.startswith("dia"):
            months = value / 30.0
        elif unit.startswith("semana"):
            months = value / 4.3
        else:
            months = value
        ages.append(months)
    if MES_Y_MEDIO_RE.search(view):
        ages.append(1.5)
    if JUST_TURNED_MONTH_RE.search(view):
        ages.append(1.0)
    for match in NACIO_HACE_RE.finditer(view):
        raw, unit = match.group(1), match.group(2)
        value = float(raw) if raw.isdigit() else float(_NUM_WORDS.get(raw, 99))
        ages.append(
            value / 30.0
            if unit.startswith("dia")
            else value / 4.3
            if unit.startswith("semana")
            else value
        )
    return min(ages) if ages else None


def _is_infant_fever(view: str) -> bool:
    if NO_FEVER_RE.search(view):
        return False
    has_fever = bool(FEVER_RE.search(view)) or bool(TEMP_RE.search(view))
    if not has_fever:
        return False
    if NEWBORN_RE.search(view):
        return True
    months = _infant_age_months(view)
    # Se exige una referencia a un bebé/niño o a "tiene N meses" para evitar falsos positivos
    # con duraciones ("fiebre desde hace 2 dias").
    if months is None or months > 3.0:
        return False
    duration_only = (
        None
        if NACIO_HACE_RE.search(view)
        else re.search(
            rf"\b(?:desde\s+hace|durante|hace|llevo|lleva|llevamos|llevan)\s+{_AGE_NUM}\s+(?:dias?|semanas?|meses|mes)\b",
            view,
        )
    )
    has_baby = (
        bool(BABY_TERMS_RE.search(view))
        or bool(NACIO_HACE_RE.search(view))
        or bool(
            re.search(
                rf"\b(?:tiene|con|de|cumple|cumplio)\s+{_AGE_NUM}\s+(?:semanas?|meses|mes|dias?)\b",
                view,
            )
        )
    )
    if duration_only and not re.search(
        rf"\b(?:bebe|lactante|recien)\b|\b(?:tiene|de)\s+{_AGE_NUM}\s+(?:semanas?|meses|mes)\b",
        view,
    ):
        return False
    return has_baby


def _rules(view: str) -> list[RedFlag]:
    flags: list[RedFlag] = []

    # 1. Dolor torácico con cortejo vegetativo / irradiación
    if _any_unnegated(CHEST_PAIN_RE, view) and CHEST_ASSOCIATED_RE.search(view):
        flags.append(RedFlag(CHEST_PAIN, "dolor_toracico+sintomas_asociados"))
    elif (
        HEART_ATTACK_SELF_RE.search(view)
        and not HEART_ATTACK_DENY_RE.search(view)
        and re.search(
            r"\b(?:creo|parece|siento|tengo|me\s+esta\s+dando|me\s+da|sufro|estoy\s+teniendo)\b",
            view,
        )
    ):
        flags.append(RedFlag(CHEST_PAIN, "infarto_autorreferido"))

    # 2. Focalidad neurológica súbita
    chronic = bool(CHRONIC_MARKERS.search(view))
    strong = [m for m in STROKE_STRONG_RE.finditer(view) if not _negated(view, m.start())]
    if strong and not chronic:
        flags.append(RedFlag(STROKE, "focalidad_neurologica"))
    elif (
        not chronic
        and STROKE_WEAK_RE.search(view)
        and STROKE_SUDDEN_RE.search(view)
        and STROKE_SIDE_RE.search(view)
    ):
        flags.append(RedFlag(STROKE, "inicio_subito+lateralidad"))

    # 3. Ideación suicida
    suicide_hit = False
    if not SUICIDE_BENIGN_RE.search(view):
        for match in SUICIDE_RE.finditer(view):
            text = match.group(0)
            if SUICIDE_NEGATED_STEM_RE.search(text):
                window = view[max(0, match.start() - 45) : match.end()]
                if SUICIDE_NEGATION_RE.search(window):
                    continue
            suicide_hit = True
            break
    if suicide_hit:
        flags.append(RedFlag(SUICIDE, "ideacion_suicida"))

    # 4. Fiebre en lactante (< 3 meses)
    if _is_infant_fever(view):
        flags.append(RedFlag(INFANT_FEVER, "fiebre_lactante_menor_3_meses"))

    # 5. Anafilaxia
    if ANAPH_STRONG_RE.search(view) and not re.search(
        r"\b(?:antecedentes?|tuve|tuvo|historial|miedo)\b", view
    ):
        flags.append(RedFlag(ANAPHYLAXIS, "anafilaxia_referida"))
    elif THROAT_CLOSING_RE.search(view):
        flags.append(RedFlag(ANAPHYLAXIS, "cierre_de_garganta"))
    elif (
        ANAPH_SWELL_RE.search(view)
        and ANAPH_COFACTOR_RE.search(view)
        and not re.search(
            r"\b(?:sin|no)\s+(?:dificultad|problema)s?\s+(?:para\s+)?respirar\b", view
        )
    ):
        flags.append(RedFlag(ANAPHYLAXIS, "hinchazon_via_aerea+sintomas"))
    elif ANAPH_SYSTEMIC_RE.search(view) and ANAPH_SYSTEMIC_COFACTOR_RE.search(view):
        flags.append(RedFlag(ANAPHYLAXIS, "urticaria_generalizada+sintomas_sistemicos"))
    elif RESP_DISTRESS_RE.search(view) and ANAPH_TRIGGER_RE.search(view):
        flags.append(RedFlag(ANAPHYLAXIS, "dificultad_respiratoria+desencadenante"))

    # 6. Otros signos de alarma
    if RESP_DISTRESS_RE.search(view) and not RESP_BENIGN_RE.search(view):
        flags.append(RedFlag(RESPIRATORY, "dificultad_respiratoria_grave"))
    if SEIZURE_RE.search(view) and not chronic:
        flags.append(RedFlag(SEIZURE_SYNCOPE, "convulsion_o_inconsciencia"))
    if BLEEDING_RE.search(view):
        flags.append(RedFlag(BLEEDING, "hemorragia_grave"))
    if OVERDOSE_RE.search(view):
        flags.append(RedFlag(OVERDOSE, "intoxicacion_sobredosis"))
    return flags


def detect_red_flags(text: str) -> list[RedFlag]:
    """Devuelve los signos de alarma detectados en `text` (lista vacía si no hay ninguno).

    Función pura y determinista. Ante texto no cadena o vacío devuelve lista vacía.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    found: dict[str, RedFlag] = {}
    for view in _views(text[:20000]):
        for flag in _rules(view):
            found.setdefault(flag.category, flag)
    return list(found.values())


# --- Mensajes de escalada (estáticos; nunca generados por el LLM) ----------------------------

_FOOTER = (
    "Este asistente es una demostración técnica: no puede evaluar tu estado ni sustituir a los "
    "servicios de emergencia."
)

_MESSAGES: dict[str, str] = {
    CHEST_PAIN: (
        f"Lo que describes (dolor en el pecho con otros síntomas) puede ser una urgencia cardíaca.\n\n"
        f"1. Llama ahora al {EMERGENCY_NUMBER} (emergencias en España). No esperes a ver si se pasa.\n"
        "2. No conduzcas tú. Quédate sentado o semisentado y en reposo, y avisa a alguien que esté cerca.\n"
        "3. Cuando llegue la ayuda, cuéntales cuándo empezó el dolor y la medicación que tomas.\n"
    ),
    STROKE: (
        "Lo que describes (síntomas neurológicos de inicio brusco) puede ser un ictus, y cada minuto cuenta.\n\n"
        f"1. Llama ahora al {EMERGENCY_NUMBER} (emergencias en España).\n"
        "2. Anota la hora exacta en la que empezaron los síntomas o la última vez que estabas bien.\n"
        "3. No conduzcas tú, no comas ni bebas y no esperes a que mejore.\n"
    ),
    SUICIDE: (
        "Siento mucho que estés pasando por algo tan doloroso. Gracias por contármelo: lo que sientes "
        "importa y no tienes que afrontarlo a solas.\n\n"
        f"- Si estás en peligro inmediato o ya has hecho algo para hacerte daño, llama ahora al "
        f"{EMERGENCY_NUMBER}.\n"
        f"- Si necesitas hablar con alguien ahora, puedes llamar al {SUICIDE_LINE} (línea de atención "
        "a la conducta suicida en España, gratuita y disponible las 24 horas).\n"
        "- Intenta no quedarte solo o sola: avisa a una persona de confianza y pídele que esté contigo.\n"
        "- Aleja de ti, mientras tanto, cualquier cosa con la que pudieras hacerte daño.\n\n"
        "Pensar en morir es una señal de que sufres mucho, y ese sufrimiento se puede tratar. "
        "Cuando te encuentres un poco más seguro o segura, pide una cita con tu médico de cabecera "
        "o con salud mental.\n"
    ),
    INFANT_FEVER: (
        "Una fiebre en un bebé de menos de 3 meses necesita valoración médica urgente, aunque el bebé "
        "parezca estar bien.\n\n"
        f"1. Llama ahora al {EMERGENCY_NUMBER} o acude de inmediato a urgencias pediátricas.\n"
        "2. No esperes a que pase la noche ni a pedir cita.\n"
        "3. Lleva la temperatura medida y la hora de inicio.\n"
    ),
    ANAPHYLAXIS: (
        "Lo que describes (hinchazón o dificultad para respirar tras un posible desencadenante) puede ser "
        "una reacción alérgica grave.\n\n"
        f"1. Llama ahora al {EMERGENCY_NUMBER} (emergencias en España).\n"
        "2. Si tu médico te ha pautado un autoinyector de adrenalina, úsalo según sus instrucciones y "
        "dilo al llamar.\n"
        "3. Aléjate del desencadenante, túmbate con las piernas elevadas (o sentado si te cuesta respirar) "
        "y no te quedes solo o sola.\n"
    ),
    RESPIRATORY: (
        "Una dificultad grave para respirar es una urgencia.\n\n"
        f"1. Llama ahora al {EMERGENCY_NUMBER}.\n"
        "2. Siéntate erguido, abre ventanas y afloja la ropa; avisa a alguien cercano.\n"
    ),
    SEIZURE_SYNCOPE: (
        "Una convulsión o una pérdida de conciencia es una urgencia.\n\n"
        f"1. Llama ahora al {EMERGENCY_NUMBER}.\n"
        "2. No metas nada en la boca de la persona; colócala de lado y retira objetos con los que "
        "pueda golpearse. Anota cuánto dura.\n"
    ),
    BLEEDING: (
        "Un sangrado abundante o que no se detiene es una urgencia.\n\n"
        f"1. Llama ahora al {EMERGENCY_NUMBER}.\n"
        "2. Mientras llega la ayuda, presiona firmemente la zona con un paño limpio si es una herida visible.\n"
    ),
    OVERDOSE: (
        "Una posible intoxicación o sobredosis es una urgencia.\n\n"
        f"1. Llama ahora al {EMERGENCY_NUMBER} (en España, el Servicio de Información Toxicológica atiende "
        "en el 91 562 04 20, pero ante riesgo vital llama primero al 112).\n"
        "2. No provoques el vómito. Ten a mano el envase o el nombre de lo que se ha tomado.\n"
    ),
}

_PRIORITY = (
    SUICIDE,
    CHEST_PAIN,
    STROKE,
    ANAPHYLAXIS,
    INFANT_FEVER,
    RESPIRATORY,
    SEIZURE_SYNCOPE,
    BLEEDING,
    OVERDOSE,
)

GENERIC_URGENT_MESSAGE = (
    "He detectado una situación que puede requerir atención urgente.\n\n"
    f"1. Si hay riesgo para la vida, llama ahora al {EMERGENCY_NUMBER} (emergencias en España).\n"
    "2. Si no es tan grave pero te preocupa, acude hoy mismo a urgencias o a tu centro de salud.\n"
    "3. Si estás solo o sola, avisa a una persona de confianza.\n"
)


def build_emergency_message(flags: list[RedFlag] | None = None) -> str:
    """Mensaje de escalada estático. Sin `flags`, devuelve la versión genérica con el 112."""
    categories = [f.category for f in flags or []]
    ordered = [c for c in _PRIORITY if c in categories]
    if not ordered:
        return f"{GENERIC_URGENT_MESSAGE}\n{_FOOTER}"
    body = _MESSAGES[ordered[0]]
    extra = [c for c in ordered[1:] if c != SUICIDE]
    if SUICIDE in ordered[1:]:
        body += "\n" + _MESSAGES[SUICIDE]
    if extra:
        body += f"\nAdemás, hay otros signos de alarma: si cualquiera continúa, llama al {EMERGENCY_NUMBER}.\n"
    return f"{body}\n{_FOOTER}"
