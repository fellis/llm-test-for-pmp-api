# AI-Driven Customization Platform

## Обзор

Превращение классического веб-приложения (инвестиционные портфели) в AI-driven платформу, где пользователи могут кастомизировать UI и функционал через natural language.

**Принцип работы:**
```
Пользователь описывает что хочет → LLM генерирует код → Code Review → Deploy
```

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         INFRASTRUCTURE                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                      ADMIN INTERFACE                               │ │
│  │  - Chat UI (streaming)                                            │ │
│  │  - Code preview (Monaco)                                          │ │
│  │  - TODO progress                                                  │ │
│  │  - Publish button                                                 │ │
│  └─────────────────────────────────┬─────────────────────────────────┘ │
│                                    │                                    │
│                                    ▼                                    │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                      ORCHESTRATOR                                  │ │
│  │  - Session management                                             │ │
│  │  - Context building                                               │ │
│  │  - Tool execution                                                 │ │
│  │  - Validation gate                                                │ │
│  └─────────────────────────────────┬─────────────────────────────────┘ │
│                                    │                                    │
│                                    ▼                                    │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                      LLM INFERENCE (vLLM)                          │ │
│  │  Model: Qwen2.5-Coder-32B-AWQ или 14B                             │ │
│  │  Context: 16-48K tokens                                           │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                      MEMORY LAYER (Letta/LangGraph)                │ │
│  │  - In-context: system prompt, working memory, recent messages     │ │
│  │  - Out-of-context: vector store, full history                     │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│                           ISOLATION LAYER                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │  User Sandbox A  │  │  User Sandbox B  │  │  User Sandbox C  │      │
│  │  (Docker)        │  │  (Docker)        │  │  (Docker)        │      │
│  │  - Frontend      │  │  - Frontend      │  │  - Frontend      │      │
│  │  - User Backend  │  │  - User Backend  │  │  - User Backend  │      │
│  │  - User DB       │  │  - User DB       │  │  - User DB       │      │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘      │
│           │                     │                     │                 │
│           └─────────────────────┴─────────────────────┘                 │
│                                 │                                       │
│                                 │ MCP ONLY                              │
│                                 ▼                                       │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    CORE BACKEND (неизменный)                       │ │
│  │  - Business logic                                                 │ │
│  │  - Primary database                                               │ │
│  │  - Portfolios, assets, transactions                               │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Ограничения

| Ограничение | Причина | Решение |
|-------------|---------|---------|
| Нельзя использовать API (Claude/GPT) | Чувствительные данные | Self-hosted LLM |
| Бюджет ~€340/мес | Фиксированный | NVIDIA A30 (24GB) |
| Core Backend неизменен | Стабильность | MCP контракты |

---

## Инфраструктура

### Сервер

```
Provider: [TBD]
Price: €337.90/мес

Hardware:
- GPU: NVIDIA A30 (24GB VRAM)
- CPU: 2x AMD EPYC 7402
- RAM: 128GB DDR4
- Storage: 2x 960GB SSD
- Network: 1 Gbps, 30TB traffic
```

### Software Stack

```
LLM Inference:
- vLLM (OpenAI-compatible API)
- Model: Qwen2.5-Coder-32B-AWQ или Qwen2.5-Coder-14B

Memory/Context:
- Letta или LangGraph
- Redis (sessions)
- ChromaDB/pgvector (vector store)

Backend:
- Python/FastAPI (orchestrator)
- PostgreSQL (data)

Frontend:
- React (admin interface)
- WebSocket (streaming)
- Monaco Editor (code preview)

Infrastructure:
- Docker (sandboxes)
- Git (version control)
- GitHub/GitLab API (PR creation)
```

---

## Выбор модели

### Вариант A: Qwen2.5-Coder-32B-AWQ

```
VRAM: ~18-20GB
Context: 16-24K tokens
Quality: ~80% от Claude Sonnet
Speed: ~30-50 tokens/sec

Плюсы: Лучшее качество кода
Минусы: Меньше контекста
```

### Вариант B: Qwen2.5-Coder-14B

```
VRAM: ~12GB
Context: 32-48K tokens
Quality: ~70% от Claude Sonnet
Speed: ~60-80 tokens/sec

Плюсы: Больше контекста, быстрее
Минусы: Качество чуть ниже
```

### Рекомендация

Начать с **14B** для большего контекста, перейти на **32B** если качество недостаточно.

---

## Компоненты системы

### 1. TODO механизм

**Назначение:**
- Разбивает сложные задачи на шаги
- Отслеживает прогресс
- Позволяет возобновить после сбоя
- Показывает пользователю что происходит

**Статусы:**
```
pending → in_progress → completed
                     → failed
                     → cancelled
```

**Реализация:**
- LLM вызывает `todo_write` tool
- Состояние в Redis
- UI обновляется через WebSocket
- Только 1 задача in_progress одновременно

**UI:**
```
┌─────────────────────────────────────────────┐
│  Интеграция Alpha Vantage API              │
│                                             │
│  ✓ Найти документацию API                  │
│  ✓ Создать клиент API                      │
│  ● Создать компонент котировок             │
│  ○ Добавить на дашборд                     │
│                                             │
└─────────────────────────────────────────────┘
```

---

### 2. Git интеграция

**Workflow:**
```
Генерация → Валидация → Branch → Commit → PR → Review → Merge → Deploy
```

**Детали:**
- Ветка: `user/{id}/feature-{uuid}`
- Автоматический commit с описанием
- PR через GitHub/GitLab API
- MVP: ручной code review
- Позже: автоматический deploy

**Валидация перед commit:**
- [ ] ESLint/Prettier
- [ ] TypeScript type check
- [ ] Security scan (no eval, no secrets)
- [ ] Sandbox constraints (allowed imports only)

---

### 3. Уточнения у пользователя

**Когда агент спрашивает:**
- Неоднозначные требования
- Отсутствует критическая информация
- Выбор между вариантами
- Security/performance решения

**Когда НЕ спрашивает:**
- Можно сделать разумный default
- Пользователь легко изменит потом
- Мелкие детали

**Формат ответа LLM:**
```json
{
  "needs_clarification": true,
  "questions": [
    {
      "id": "data_source",
      "question": "Какой источник данных?",
      "options": ["Alpha Vantage", "NewsAPI", "Custom"],
      "required": true
    }
  ],
  "user_message": "Для создания виджета мне нужно уточнить..."
}
```

**Хранение:**
- Ответы сохраняются в `resolved_context`
- Инжектятся в system prompt
- Агент не переспрашивает

---

### 4. Диалоговый режим

**Session содержит:**
```python
class Session:
    id: str
    user_id: str
    messages: List[Message]        # История диалога
    resolved_context: Dict         # Принятые решения
    artifacts: List[GeneratedFile] # Сгенерированный код
    task_plan: TaskPlan           # TODO список
```

**Контекст в каждом запросе:**
1. System prompt + инструкции
2. Resolved context (что уже решили)
3. Текущие артефакты (сгенерированный код)
4. Релевантная история (из vector store)
5. Недавние сообщения
6. Текущий запрос

**Управление контекстом:**
- При превышении лимита — сжатие через Letta
- Старые сообщения → vector store
- Код → сигнатуры вместо полного текста

---

### 5. Web Search

**Назначение:**
- Поиск документации внешних API
- Примеры интеграций
- Решение нестандартных задач

**Провайдеры:**
```
Serper API:  $50 = 50K запросов (рекомендуется)
Tavily:      Специально для AI агентов
SearXNG:     Self-hosted, бесплатно
```

**Flow:**
```
User: "Интегрируй Alpha Vantage API"
  │
  ▼
Agent: web_search("Alpha Vantage API documentation")
  │
  ▼
Agent: web_fetch("https://alphavantage.co/documentation/")
  │
  ▼
Agent: Генерирует код на основе документации
```

---

## Roadmap

### MVP (4-6 недель)

- [ ] vLLM + Qwen развёртывание
- [ ] Базовый чат с агентом (streaming)
- [ ] Генерация простых компонентов (1-2 файла)
- [ ] Уточняющие вопросы
- [ ] Preview сгенерированного кода
- [ ] Публикация в Git (создание PR)
- [ ] Базовая валидация (lint, types)

### v1.0 (8-12 недель)

- [ ] TODO прогресс для сложных задач
- [ ] Web search для внешних API
- [ ] Итеративная генерация (несколько файлов)
- [ ] История сессий
- [ ] MCP интеграция с Core Backend
- [ ] Sandbox preview (запуск кода)
- [ ] Memory layer (Letta)

### v2.0 (будущее)

- [ ] Автоматический deploy
- [ ] Шаблоны частых кастомизаций
- [ ] Multi-user sandboxes
- [ ] Версионирование и rollback
- [ ] Библиотека виджетов
- [ ] Режим обучения (агент объясняет)
- [ ] Dry run preview

---

## Решение: OpenCode как база

После анализа альтернатив выбран **OpenCode** как основа для реализации.

**Почему OpenCode:**
- TODO механизм — встроен (`todowrite`, `todoread`)
- Уточняющие вопросы — встроен (`question` tool)
- Auto-compact контекста — на 95% автоматически
- LSP проверка кода — 40+ языков
- MCP интеграция — есть
- 90k stars, активно развивается

**Что нужно добавить:**
- Web UI (React + WebSocket)
- Интеграция с Core Backend (MCP)
- Git PR workflow
- Sandbox permissions

**Детальный план:** см. [OPENCODE-IMPLEMENTATION.md](./OPENCODE-IMPLEMENTATION.md)

---

## Открытые вопросы

1. **14B vs 32B модель** — нужно протестировать на реальных задачах
2. **OpenCode API** — изучить endpoints и WebSocket протокол
3. **Формат MCP контрактов** — определить API для Core Backend
4. **Sandbox networking** — как изолировать, но дать доступ к MCP
5. **Code review процесс** — автоматизация vs ручной

---

## Ссылки

**Основа:**
- [OpenCode](https://github.com/opencode-ai/opencode) — выбранная база
- [OpenCode Docs](https://opencode.ai/docs)

**Инфраструктура:**
- [vLLM](https://github.com/vllm-project/vllm)
- [Qwen2.5-Coder](https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct)

**Альтернативы (для справки):**
- [OpenHands](https://github.com/All-Hands-AI/OpenHands) — готовый Web UI, но меньше фич
- [Letta (MemGPT)](https://github.com/letta-ai/letta) — memory management
- [LangGraph](https://github.com/langchain-ai/langgraph) — agent workflows
