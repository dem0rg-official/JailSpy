#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
VENV_DIR="${PROJECT_DIR}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  printf 'Ошибка: не найден %s. Установите Python 3.10+ и повторите.\n' "${PYTHON_BIN}" >&2
  exit 1
fi

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
  printf 'Создаю виртуальное окружение…\n'
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

if ! "${VENV_DIR}/bin/python" -c 'import playwright' >/dev/null 2>&1; then
  printf 'Устанавливаю Playwright…\n'
  "${VENV_DIR}/bin/python" -m pip install --upgrade pip playwright
fi

# Browser binaries are installed inside Playwright's cache, outside this source tree.
if [[ "${HYPERCHROME_SKIP_BROWSER_INSTALL:-0}" == "1" ]]; then
  printf 'Пропускаю установку Chromium (HYPERCHROME_SKIP_BROWSER_INSTALL=1).\n'
elif ! "${VENV_DIR}/bin/python" -m playwright install chromium >/dev/null 2>&1; then
  printf 'Не удалось установить Chromium Playwright. Проверьте интернет и системные зависимости.\n' >&2
  exit 1
fi

exec "${VENV_DIR}/bin/python" "${PROJECT_DIR}/tracker.py" "$@"
