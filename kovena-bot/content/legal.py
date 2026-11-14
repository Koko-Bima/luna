"""Правовые проверки текста (ТЗ, п. 2.3, 6 D2)."""
import re

from content.texts import DISCLAIMER

# D2: при упоминании продукта, состава или цены дисклеймер добавляется сам.
# Основы слов, а не слова целиком: «магния», «наборов», «омегу» тоже ловятся.
PRODUCT_MARKERS = ("инозит", "магни", "омег", "набор", "₽", "бад", "капсул",
                   "витамин", "фолиев", "состав")

# Запрещённые формулировки (п. 2.3, 9).
FORBIDDEN = ("зачат", "фертильн", "беремен", "дефицит", "помогает", "повышает шансы",
             "восполняет", "заберемен", "диагноз", "лечит", "лечени", "терапевт", "врач")

_CONTRAINDICATIONS = re.compile(r"Противопоказания:[^\n]*")


def _norm(text: str) -> str:
    return text.lower().replace("ё", "е")


def mentions_product(text: str) -> bool:
    low = _norm(text)
    return any(m in low for m in PRODUCT_MARKERS)


def forbidden_words(text: str) -> list[str]:
    """Найденные запрещённые основы. Перечень противопоказаний с этикетки не проверяется."""
    low = _norm(_CONTRAINDICATIONS.sub("", text))
    return [w for w in FORBIDDEN if w in low]


def with_disclaimer(text: str) -> str:
    if mentions_product(text) and DISCLAIMER not in text:
        return f"{text}\n\n{DISCLAIMER}"
    return text
