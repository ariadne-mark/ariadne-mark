# Ariadne Mark

**Open-source compliance toolkit for AI-generated images and video.**

Статус: каркас репозитория. Исполняемый SDK, установочный пакет и production verifier ещё не выпущены.

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

Название GitHub-организации согласовано как кандидат `ariadne-mark`; этот локальный каркас ещё не опубликован. Лицензия до публикации должна быть выбрана и добавлена отдельно.
