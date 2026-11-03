# Ariadne Mark

**Open-source compliance toolkit for AI-generated images and video.**

Статус: pre-alpha ядро SDK, устанавливаемое из исходников. Реализованы форматы данных о происхождении и результатов проверки. Маркировка файлов, C2PA-подписание и production verifier ещё не реализованы. Аккаунт и API-ключ для локальной работы не нужны. См. [установку](../README.md#install-and-try-the-core) и [очередность реализации](implementation/sequence.md).

## Требования → код → тесты

Главная точка входа — [матрица покрытия](../compliance/COVERAGE.md): 15 требований, место реализации, тесты, документация и статус каждого пункта.

- [Машиночитаемый реестр требований](../compliance/requirements.json)
- [Реестр нормативных источников](../compliance/sources/index.json)
- [Правила ведения покрытия](../CONTRIBUTING.md)

## Структура

```text
src/ariadne_mark/   # watermark, provenance, signing, video, registry,
                   # verification, disclosure, pipeline
apps/verifier/     # публичный интерфейс и API проверки
tests/             # проверки по соответствующим требованиям
benchmarks/        # устойчивость, качество, затем performance
compliance/        # requirements, sources, versioned profiles, coverage
docs/              # compliance, implementation, operations, benchmarks
```

Первая область реализации: изображения и видео, CPU-first, ЕС и Калифорния. Самостоятельная маркировка музыки/аудиофайлов вне первого scope. Поддержка синтетического аудио внутри видео требует отдельного решения до заявления полного покрытия видео.

Полноценные профили законодательства и границы поддержки публикуются только после проверки. Юридические выводы, тексты первоисточников и наши технические решения различаются явно.

## Проверка связности структуры

```sh
python3 scripts/check_requirements.py
```

Проверяет пути, ссылки на источники и статусы. Не запускает watermarking и не подтверждает compliance.

Организация: https://github.com/ariadne-mark. Основной репозиторий: https://github.com/ariadne-mark/ariadne-mark. Каркас опубликован; лицензия исходного кода и нашей документации — Apache-2.0. Сторонние материалы сохраняют собственные условия использования.
