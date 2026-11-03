# Матрица требований Ariadne Mark

Все 15 пунктов включены в план. **Учтено в плане ≠ реализовано ≠ проверено ≠ полное юридическое соответствие.**

Текущий статус: **6 из 15 реализовано и проверено в указанном техническом scope**, 9 в работе. См. [границы поддержки](../docs/operations/support.md) и [доказательства](../docs/validation/0.4.0a0.md). Юридическая применимость не становится подтверждённой автоматически.

Машиночитаемый источник: [requirements.json](requirements.json). Нормативные источники: [sources/index.json](sources/index.json).

| ID | Требование | Реализация | Проверки | Документация | Готово |
|---|---|---|---|---|---|
| REQ-001 | Определить применимые требования | [compliance/profiles](../compliance/profiles/README.md) | [tests/compliance](../tests/compliance/README.md) | [Руководство](../docs/compliance/applicability.md) | ☐ |
| REQ-002 | Записать машиночитаемую маркировку изображения | [src/ariadne_mark/watermark](../src/ariadne_mark/watermark/README.md) | [tests/watermark](../tests/watermark/README.md) | [Руководство](../docs/implementation/image-marking.md) | ✓ |
| REQ-003 | Сформировать сведения о происхождении | [src/ariadne_mark/provenance](../src/ariadne_mark/provenance/README.md) | [tests/provenance](../tests/provenance/README.md) | [Руководство](../docs/implementation/provenance.md) | ☐ |
| REQ-004 | Подписать и проверить C2PA | [src/ariadne_mark/signing](../src/ariadne_mark/signing/README.md) | [tests/signing](../tests/signing/README.md) | [Руководство](../docs/implementation/signing.md) | ✓ |
| REQ-005 | Реализовать полный путь для видео | [src/ariadne_mark/video](../src/ariadne_mark/video/README.md) | [tests/video](../tests/video/README.md) | [Руководство](../docs/implementation/video.md) | ✓ |
| REQ-006 | Обеспечить восстановление связи с источником | [src/ariadne_mark/registry](../src/ariadne_mark/registry/README.md) | [tests/registry](../tests/registry/README.md) | [Руководство](../docs/implementation/recovery.md) | ✓ |
| REQ-007 | Предоставить публичную проверку | [apps/verifier](../apps/verifier/README.md) | [tests/verifier](../tests/verifier/README.md) | [Руководство](../docs/implementation/verifier.md) | ☐ |
| REQ-008 | Разделить результаты проверки и ошибки | [src/ariadne_mark/verification](../src/ariadne_mark/verification/README.md) | [tests/verification](../tests/verification/README.md) | [Руководство](../docs/implementation/verification-results.md) | ✓ |
| REQ-009 | Предоставить нужные disclosure-компоненты | [src/ariadne_mark/disclosure](../src/ariadne_mark/disclosure/README.md) | [tests/disclosure](../tests/disclosure/README.md) | [Руководство](../docs/implementation/disclosure.md) | ☐ |
| REQ-010 | Сохранять историю преобразований | [src/ariadne_mark/provenance](../src/ariadne_mark/provenance/README.md) | [tests/provenance](../tests/provenance/README.md) | [Руководство](../docs/implementation/provenance-relay.md) | ✓ |
| REQ-011 | Ограничить обработку данных в verifier | [apps/verifier](../apps/verifier/README.md) | [tests/privacy](../tests/privacy/README.md) | [Руководство](../docs/operations/privacy.md) | ☐ |
| REQ-012 | Измерить устойчивость и качество | [benchmarks/durability](../benchmarks/durability/README.md) | [tests/robustness](../tests/robustness/README.md) | [Руководство](../docs/benchmarks/durability.md) | ☐ |
| REQ-013 | Обеспечить работу на CPU и явный отказ | [src/ariadne_mark/pipeline](../src/ariadne_mark/pipeline/README.md) | [tests/integration](../tests/integration/README.md) | [Руководство](../docs/operations/cpu-deployment.md) | ☐ |
| REQ-014 | Организовать production-подписание | [src/ariadne_mark/signing](../src/ariadne_mark/signing/README.md) | [tests/signing](../tests/signing/README.md) | [Руководство](../docs/operations/keys-and-trust.md) | ☐ |
| REQ-015 | Версионировать правила и выпускать доказательства | [compliance/profiles](../compliance/profiles/README.md) | [tests/compliance](../tests/compliance/README.md) | [Руководство](../docs/operations/releases.md) | ☐ |

## Когда ставим галочку

- Реализация есть в конкретном commit/release.
- Выполнен критерий приёмки из requirements.json.
- Есть отчёт исполняемых тестов с окружением и версиями.
- Документация показывает использование и ограничения.
- Для нормативного пункта проверена применимость и редакция источника.

Галочка подтверждает этот конкретный пункт в указанном scope, а не все обязанности продукта.

## Три типа связей

Законодательные требования привязываются к источнику и применимости. Технические меры (например, C2PA или реестр) объясняют выбранный способ реализации. Инженерные требования (например, CPU и fail-closed) нужны для качества продукта. Эти категории не подменяют друг друга.
