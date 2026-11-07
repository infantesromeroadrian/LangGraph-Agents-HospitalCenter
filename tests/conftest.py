"""Entorno determinista para la suite: sin claves reales ni red.

Se fija antes de que cualquier módulo de `src` instancie `settings` o `llm_service`.
Los valores son ficticios y solo existen durante la ejecución de los tests.
"""

import os

_TEST_ENV = {
    "OPENAI_API_KEY": "test-key-not-real",
    "APP_SECRET_KEY": "test-secret-key-only-for-pytest-0123456789",
    "ADMIN_API_KEY": "test-admin-key-0123456789",
}
for _name, _value in _TEST_ENV.items():
    os.environ[_name] = _value
