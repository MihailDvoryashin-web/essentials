# Essentials AI Changelog

Этот файл — хронологический журнал изменений для AI-разработчиков. Новые записи добавляются выше старых. Исторические записи не удаляются. В журнал попадают только изменения, подтверждённые текущим кодом и проверками.

## 2026-08-24

### Задача:

Закрепить обязательный project-memory и GitHub synchronization protocol.

### Изменённые файлы:

- `PROJECT_CONTEXT.md`
- `CHANGELOG_AI.md`

### Изменённая логика:

Production behavior не менялся. Добавлено правило: после каждого изменения кода обновлять архитектурный контекст и этот changelog, проверять Git status, создавать целевой commit и отправлять его в configured GitHub remote.

### Проверка:

- `git diff --check`: OK.
- Git branch: `main`.
- GitHub remote: НЕ НАСТРОЕН; push невозможен до добавления remote.
