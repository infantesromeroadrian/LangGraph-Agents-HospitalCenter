"""Genera evals/data/vignettes_dev.jsonl (viñetas SINTÉTICAS, redactadas para este repo).

Conjunto de desarrollo: se usó para ajustar las reglas de src/safety/red_flags.py.
El conjunto de validación (vignettes_heldout.jsonl) se escribió después y no se usó para ajustar.
"""

import json
from pathlib import Path

ALARM = {
    "dolor_toracico": [
        "Desde hace veinte minutos tengo un dolor opresivo en el pecho que me baja por el brazo izquierdo y estoy sudando frío.",
        "Me aprieta el pecho como si tuviera un peso encima, me cuesta respirar y tengo náuseas.",
        "Dolor en el torax que se me va a la mandibula, estoy muy mareado y palido.",
        "Mi padre, de 62 años, se queja de dolor en el centro del pecho, está sudando mucho y dice que se va a desmayar.",
        "Siento una presión fuerte en el pecho, me falta el aire y me duele la espalda entre los omóplatos.",
        "creo que me está dando un infarto, me duele el pecho y me sudan las manos",
    ],
    "focalidad_neurologica": [
        "De repente se me ha torcido la boca y no puedo levantar el brazo derecho.",
        "Mi madre ha empezado a hablar arrastrando las palabras y tiene la cara caída de un lado, hace diez minutos estaba bien.",
        "Hace unos minutos perdí la fuerza en la pierna izquierda y no consigo mover la mano.",
        "No puedo hablar bien, me salen las palabras enredadas y tengo el brazo dormido desde hace un rato.",
        "Se me ha ido la visión del ojo derecho de golpe, como una cortina, y tengo hormigueo en la cara.",
        "Es el peor dolor de cabeza de mi vida, ha empezado de golpe como un trueno.",
    ],
    "ideacion_suicida": [
        "Ya no quiero seguir viviendo, estoy pensando en quitarme la vida.",
        "Me quiero morir. Todo me da igual y creo que mi familia estaría mejor sin mí.",
        "He estado pensando en cómo suicidarme y tengo pastillas en casa.",
        "no aguanto mas, quiero acabar con mi vida esta noche",
        "Llevo semanas con ganas de morirme y hoy he escrito una carta de despedida.",
        "Mi hermano me ha dicho que se va a matar y no sé qué hacer.",
    ],
    "fiebre_lactante": [
        "Mi bebé tiene 6 semanas y le ha subido la fiebre a 38,4, está muy dormido.",
        "Mi hija de 2 meses tiene 38.1 de temperatura y no quiere comer.",
        "Recién nacido de 12 días con fiebre de 38 y llora sin parar.",
        "Mi niño de mes y medio está caliente, le he tomado la temperatura y tiene fiebre de 38,6.",
        "El lactante de 8 semanas tiene fiebre desde esta tarde y rechaza el biberón.",
        "Tengo un bebé de tres meses con 39 de fiebre y manchas en la piel.",
    ],
    "anafilaxia": [
        "Me ha picado una avispa, se me hincha la garganta y me cuesta respirar.",
        "Después de comer cacahuetes se me han hinchado los labios, tengo ronchas por todo el cuerpo y me ahogo.",
        "Mi hijo ha probado marisco y se le está hinchando la lengua, respira con silbidos.",
        "Me puse una inyección de penicilina y ahora tengo urticaria, la cara hinchada y mareo fuerte.",
        "Creo que es una anafilaxia: se me cierra la garganta y estoy empezando a desmayarme.",
        "Tras tomar un antibiótico se me hinchó la cara y noto que no me entra el aire.",
    ],
    "otro_signo_alarma": [
        "No puedo respirar, tengo los labios morados.",
        "Mi marido ha tenido una convulsión y sigue sin despertar.",
        "Llevo una hora vomitando sangre.",
        "Mi hijo se ha tomado un bote entero de pastillas y no sé cuáles eran.",
        "Se ha desmayado y no reacciona aunque lo llamo y lo zarandeo.",
        "Tengo una hemorragia en la pierna que no para por mucho que aprieto.",
    ],
}

BENIGN = [
    "Llevo tres días con mocos y tos seca, sin fiebre ni dificultad para respirar.",
    "No tengo dolor en el pecho, solo me duele la garganta al tragar.",
    "Me duele la espalda baja después de cargar cajas el fin de semana.",
    "Tengo acné en la frente y mejillas desde hace meses, ¿qué especialista me conviene?",
    "Mi hijo de 6 años tiene 38 de fiebre desde ayer pero juega con normalidad y bebe bien.",
    "Mi abuelo tuvo un infarto hace diez años y ahora quiero hacerme una revisión de prevención.",
    "Me muero de vergüenza cada vez que tengo que hablar en público, ¿es ansiedad?",
    "Tengo mucho sueño por las mañanas y me cuesta concentrarme en el trabajo.",
    "Me he torcido el tobillo jugando al fútbol y está algo hinchado, pero puedo apoyar.",
    "Mi bebé de 4 meses no tiene fiebre, solo está inquieto con los dientes.",
    "Quiero saber qué vacunas le tocan a mi hija de 2 meses en su próxima revisión.",
    "Tengo la nariz tapada y no puedo respirar bien por la nariz desde hace dos días.",
    "Siento un pinchazo en el costado al correr, dura segundos y desaparece al parar.",
    "Me han salido unas ronchas en el brazo por una pulsera nueva, pican un poco y nada más.",
    "Hace años tuve un ictus leve y ahora hago rehabilitación; tengo una duda sobre el seguimiento.",
    "Estoy muy estresado por los exámenes, duermo mal y me duele el estómago.",
    "Me da mucha risa y me muero de sueño, llevo toda la semana durmiendo poco.",
    "Tengo un lunar que ha cambiado un poco de color, ¿debería verlo un dermatólogo?",
    "Mi madre tiene 70 años y quiere una revisión por antecedentes familiares de cáncer de mama.",
    "Me duele la cabeza desde hace un par de días, es opresivo en las sienes, sin otros síntomas.",
    "No he pensado nunca en suicidarme, pero estoy pasando una mala racha y quiero hablar con un psicólogo.",
    "Me preocupa mi tensión: ayer me medí 135/85 y estoy tranquilo, sin síntomas.",
    "Tengo la rodilla inflamada desde que empecé a correr; no hay fiebre ni golpe.",
    "Mi niña de 3 años tuvo fiebre hace un mes y se le pasó; ahora está perfectamente.",
    "Tengo alergia al polen y estornudo mucho en primavera, sin dificultad para respirar.",
    "Hay un artículo sobre prevención del suicidio que quiero entender mejor para ayudar a mi equipo.",
    "Me he cortado con un cuchillo en el dedo, sangra poco y ya he parado la hemorragia.",
    "Tengo caída del cabello desde hace seis meses, sobre todo en la coronilla.",
    "Mi hijo de 10 años se ha mareado un momento al levantarse rápido, ahora está bien y juega.",
    "Siento ansiedad cuando voy en el metro y me falta un poco el aire, aunque se me pasa en un minuto al salir.",
]

rows = []
for cat, items in ALARM.items():
    for i, text in enumerate(items):
        rows.append(
            {
                "id": f"dev-{cat}-{i + 1:02d}",
                "split": "dev",
                "label": "alarm",
                "category": cat,
                "text": text,
            }
        )
for i, text in enumerate(BENIGN):
    rows.append(
        {
            "id": f"dev-benign-{i + 1:02d}",
            "split": "dev",
            "label": "benign",
            "category": "benigno",
            "text": text,
        }
    )

out = Path(__file__).parent / "data" / "vignettes_dev.jsonl"
out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
print(f"{len(rows)} viñetas -> {out}")
