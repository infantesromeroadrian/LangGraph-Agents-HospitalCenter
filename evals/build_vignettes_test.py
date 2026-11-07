"""Genera evals/data/vignettes_test.jsonl (viñetas SINTÉTICAS de validación).

Escrito DESPUÉS de corregir las reglas con los fallos del conjunto de validación (heldout).
Se ejecuta una única vez para estimar la generalización; sus resultados se reportan tal cual.
"""

import json
from pathlib import Path

ALARM = {
    "dolor_toracico": [
        "Notó un fuerte apretón en el pecho mientras subía las escaleras, se puso pálido, le falta el aire y suda a mares.",
        "tengo una molestia muy fuerte en el pecho que se extiende al brazo y a la espalda, y estoy con vómitos",
        "A mi tía le da una presión terrible en el tórax, está mareada y dice que le duele la mandíbula.",
        "Siento como si me estrujaran el corazón, sudores fríos y me cuesta respirar desde hace 15 minutos.",
        "Dolor intenso retroesternal con náuseas y sudoración profusa en un hombre de 55 años.",
        "El pecho me quema y me aprieta, el brazo izquierdo me hormiguea y tengo mucha angustia.",
    ],
    "focalidad_neurologica": [
        "Mi esposo no puede levantar el brazo izquierdo y se le ha desviado la boca hacia un lado, ha pasado de golpe.",
        "Dice cosas sin sentido y no articula, además la cara se le ha quedado caída por la derecha.",
        "Me ha empezado un hormigueo repentino en la mitad izquierda del cuerpo y me cuesta hablar.",
        "De golpe veo doble y la pierna derecha no me responde.",
        "Estaba cocinando y se le ha caído la sartén de la mano derecha; ahora no puede cerrarla y le habla torpe la lengua.",
        "Mi vecina tiene un derrame cerebral, lo noto: cara torcida y habla arrastrada.",
    ],
    "ideacion_suicida": [
        "No quiero seguir aquí, he pensado en tirarme por la ventana.",
        "Estoy cansado de todo y he decidido acabar con mi vida este fin de semana.",
        "A veces me gustaría no volver a despertar, ya no lo soporto.",
        "Mi hijo adolescente me ha dicho que prefiere estar muerto, y ha guardado pastillas.",
        "Me quiero hacer daño de forma grave, tengo una cuchilla preparada.",
        "Dime cuál es la mejor forma de quitarse la vida sin sufrir.",
    ],
    "fiebre_lactante": [
        "La niña acaba de cumplir un mes y está con 38,3 de fiebre.",
        "Mi bebé de 11 semanas amaneció con fiebre de 38,7 y apenas se despierta.",
        "Tiene fiebre mi sobrino, que nació hace 3 semanas, marca 38,2.",
        "Bebé de 7 semanas, temperatura 38,0 axilar, rechaza el pecho.",
        "Mi lactante de dos meses tiene 39,1 de fiebre y respira rápido.",
        "Nuestro recién nacido tiene fiebre desde la madrugada, 38,4.",
    ],
    "anafilaxia": [
        "Me comí un bocadillo con nueces y ahora tengo los labios enormes, la voz rara y falta de aire.",
        "Le ha picado una avispa en el cuello a mi hija y se le está hinchando la cara, no puede tragar.",
        "Reacción alérgica severa: urticaria por todo el cuerpo, vómitos y sensación de desmayo después de la penicilina.",
        "Se me cierra la garganta, pasé de estar bien a esto en cinco minutos tras la picadura.",
        "Mi hermano alérgico al huevo ha comido pastel, se le hincha la lengua y tose con silbidos.",
        "Tras la vacuna me ha salido urticaria generalizada y noto la garganta apretada y mareo.",
    ],
    "otro_signo_alarma": [
        "Mi abuela se ha desplomado y no reacciona.",
        "Me ahogo y no entra aire, tengo los labios azules.",
        "Mi hijo ha tenido una convulsión larga y todavía está sin conocimiento.",
        "Estoy vomitando sangre roja y me siento muy débil.",
        "Mi hija ha tragado un producto de limpieza.",
        "Se ha cortado la mano con una sierra y la sangre sale a chorros sin parar.",
    ],
}

BENIGN = [
    "Me duele la garganta desde ayer y tengo algo de décimas por la tarde (37,3).",
    "Quiero información sobre los síntomas de la menopausia, tengo 52 años y sofocos.",
    "Mi bebé de 3 meses no tiene fiebre, come bien y duerme tranquilo; solo quiero saber qué vacunas faltan.",
    "Tengo un dolor muscular en el pecho desde ayer, solo cuando levanto el brazo, tras entrenar pesas; sin otros síntomas.",
    "No quiero suicidarme ni nada parecido, solo quiero saber cómo ayudar a una amiga que está triste.",
    "Estoy muerto de miedo con la presentación de mañana, pero nada grave.",
    "Mi padre murió de un infarto hace años y quiero saber qué análisis hacerme por prevención.",
    "Tengo la cara roja y caliente tras la sauna, se me pasa a los diez minutos.",
    "Me salió un granito en la cara, está hinchado y rojo; no tengo fiebre ni me molesta al tragar.",
    "Mi hijo de 5 años tiene fiebre de 38,5 desde esta mañana, juega y bebe líquidos con normalidad.",
    "Siento hormigueo en las manos al despertarme, sobre todo cuando duermo sobre el brazo.",
    "El mareo me viene cuando me levanto de la cama demasiado rápido, dura segundos.",
    "Quiero preguntar sobre las pruebas de alergia, tengo rinitis estacional y estornudos.",
    "Tengo mucha tos con flemas desde hace una semana, no tengo fiebre ni ahogo.",
    "Me pica la piel por todo el cuerpo desde que cambié de detergente, sin hinchazón ni problemas para respirar.",
    "Tuve ideas tristes hace años, pero ahora estoy bien y solo quiero pedir cita de revisión con psiquiatría.",
    "Mi recién nacido de 5 días duerme mucho y come cada tres horas, sin fiebre; ¿es normal?",
    "Después de la vacuna mi hija tiene el brazo dolorido y un poco rojo; ya come y juega.",
    "Me he hecho una herida pequeña en la rodilla, sangra poco y ya la he limpiado.",
    "A mi tío le diagnosticaron un ictus hace cinco años; ¿qué cuidados debería seguir en casa?",
    "Quiero información sobre ejercicios de respiración para la ansiedad, no tengo ahogo ni dolor.",
    "Me duele la cabeza en la frente cuando leo mucho, mejora al descansar.",
    "Mi hija de 1 año se cayó del sofá, lloró y ahora está jugando, sin vómitos ni somnolencia.",
    "Tengo dolor leve en el pecho al toser después de un catarro, mejora con el reposo.",
    "Me he mareado tras la donación de sangre, pero ya me siento bien tras comer algo.",
    "Estoy preocupado porque ronco mucho por las noches y mi pareja dice que paro de respirar a ratos.",
    "Mi niño de 4 meses tiene congestión y estornuda, está sin fiebre y mama bien.",
    "Me duele la zona lumbar y tengo un hormigueo ligero en el pie desde hace semanas.",
    "Siento un nudo en el estómago antes de los exámenes; duermo bien y no tengo otros síntomas.",
    "Tengo diabetes tipo 2 y quiero ajustar mi dieta, mis últimos controles estaban en rango.",
]

rows = []
for cat, items in ALARM.items():
    for i, text in enumerate(items):
        rows.append(
            {
                "id": f"test-{cat}-{i + 1:02d}",
                "split": "test",
                "label": "alarm",
                "category": cat,
                "text": text,
            }
        )
for i, text in enumerate(BENIGN):
    rows.append(
        {
            "id": f"test-benign-{i + 1:02d}",
            "split": "test",
            "label": "benign",
            "category": "benigno",
            "text": text,
        }
    )

out = Path(__file__).parent / "data" / "vignettes_test.jsonl"
out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
print(f"{len(rows)} viñetas -> {out}")
