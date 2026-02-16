# OpenCode Implementation Plan

## Почему OpenCode

OpenCode выбран как база для AI-driven customization platform потому что:

| Критерий | OpenCode | Альтернативы |
|----------|----------|--------------|
| TODO механизм | ✅ Встроен | Нужно писать |
| Уточняющие вопросы | ✅ `question` tool | Нужно писать |
| Auto-compact контекста | ✅ На 95% | Нужно писать |
| LSP (проверка кода) | ✅ 40+ языков | Нет |
| MCP интеграция | ✅ Есть | Частично |
| Permissions | ✅ allow/deny/ask | Нужно писать |
| Stars/активность | 90k, активен | — |

**Нужно добавить:** Web UI поверх существующего HTTP API.

---

## Архитектура OpenCode

```
┌─────────────────────────────────────────────────────────────────┐
│                    OPENCODE ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │               Terminal UI (Bubble Tea)                   │   │
│  │                                                          │   │
│  │   ← ЗАМЕНИТЬ на Web UI (React + WebSocket)              │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │               HTTP Server (Hono + Bun)                   │   │
│  │                                                          │   │
│  │   ← Уже есть API, нужно документировать endpoints       │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│         ┌────────────────────┼────────────────────┐            │
│         ▼                    ▼                    ▼            │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐      │
│  │   AI SDK    │     │   SQLite    │     │    LSP      │      │
│  │  (75+ LLM)  │     │ (sessions)  │     │ (40+ lang)  │      │
│  └─────────────┘     └─────────────┘     └─────────────┘      │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    LLM Provider                          │   │
│  │                                                          │   │
│  │   vLLM + Qwen2.5-Coder (self-hosted)                    │   │
│  │                                                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Встроенные фичи OpenCode

### 1. Agents (режимы работы)

| Agent | Описание | Использование |
|-------|----------|---------------|
| **Build** | Полный доступ, редактирование файлов | Генерация кода |
| **Plan** | Read-only, анализ без изменений | Планирование задач |
| **General** (subagent) | Многошаговые задачи | Сложные фичи |
| **Explore** (subagent) | Быстрый поиск по коду | Навигация |

### 2. Tools (инструменты)

```
File Operations:
├── read      — читать файл
├── write     — создать/перезаписать файл
├── edit      — редактировать часть файла
└── patch     — применить патч

Search:
├── grep      — поиск по содержимому
├── glob      — поиск по имени файла
└── list      — список файлов в директории

Execution:
├── bash      — выполнить команду
└── lsp       — проверка ошибок (experimental)

Specialized:
├── webfetch  — загрузить URL
├── question  — задать вопрос пользователю
├── todowrite — создать/обновить задачи
├── todoread  — прочитать задачи
└── skill     — использовать навык
```

### 3. Auto-Compact

Когда контекст достигает 95% лимита:
- Автоматически суммаризирует старые сообщения
- Сохраняет ключевую информацию
- Освобождает место для новых запросов

### 4. Permissions

Настраиваются в `opencode.json`:

```json
{
  "permissions": {
    "bash": "ask",      // Спрашивать перед выполнением
    "write": "allow",   // Разрешить без вопросов
    "delete": "deny"    // Запретить
  }
}
```

---

## Что нужно сделать

### Этап 1: Развёртывание (1-2 дня)

**Задачи:**
- [ ] Арендовать сервер Unihost LWN-G10 (A30 24GB, 128GB RAM) — €338-450/мес
- [ ] Установить Docker + NVIDIA Container Toolkit
- [ ] Установить vLLM + Qwen2.5-Coder
- [ ] Установить OpenCode
- [ ] Настроить OpenCode для работы с локальной LLM
- [ ] Проверить работу через терминал

**Сервер:**
- Провайдер: Unihost (https://unihost.com/dedicated/ai-servers/)
- Конфигурация: LWN-G10 или LWE-G4
- GPU: Nvidia A30 (24GB VRAM)
- RAM: 128GB
- Цена: €338-450/мес

**Команды:**

```bash
# 0. Установка NVIDIA Container Toolkit (на сервере)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# 1. vLLM (A30 24GB → Qwen-14B с большим контекстом или 32B-AWQ)
docker run --gpus all -d --name vllm \
  -p 8000:8000 \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen2.5-Coder-14B-Instruct \
  --max-model-len 32768 \
  --gpu-memory-utilization 0.9

# 2. OpenCode
curl -fsSL https://opencode.ai/install.sh | bash

# 3. Настройка (~/.config/opencode/config.json)
{
  "provider": "openai-compatible",
  "model": "Qwen/Qwen2.5-Coder-14B-Instruct",
  "baseUrl": "http://localhost:8000/v1",
  "apiKey": "dummy"
}

# 4. Тест
opencode
```

---

### Этап 2: Изучение API (2-3 дня)

**Задачи:**
- [ ] Изучить исходный код OpenCode (Hono сервер)
- [ ] Документировать HTTP endpoints
- [ ] Понять формат WebSocket сообщений
- [ ] Понять как работает session management

**Ключевые файлы для изучения:**

```
opencode/
├── src/
│   ├── server/          # Hono HTTP сервер
│   │   ├── routes/      # API endpoints
│   │   └── websocket/   # WebSocket handlers
│   ├── agents/          # Build, Plan, General, Explore
│   ├── tools/           # Все инструменты
│   ├── db/              # SQLite схема
│   └── ai/              # AI SDK интеграция
```

**Ожидаемые endpoints (нужно проверить):**

```
POST /api/chat          # Отправить сообщение
GET  /api/sessions      # Список сессий
GET  /api/session/:id   # Получить сессию
WS   /ws                # WebSocket для streaming
```

---

### Этап 3: Web UI (1-2 недели)

**Задачи:**
- [ ] Создать React приложение
- [ ] Реализовать чат интерфейс
- [ ] Подключить WebSocket для streaming
- [ ] Отображать TODO прогресс
- [ ] Отображать уточняющие вопросы
- [ ] Preview сгенерированного кода
- [ ] Кнопка Publish

**Компоненты:**

```
src/
├── components/
│   ├── Chat/
│   │   ├── ChatContainer.tsx    # Основной контейнер
│   │   ├── MessageList.tsx      # Список сообщений
│   │   ├── MessageInput.tsx     # Поле ввода
│   │   └── StreamingMessage.tsx # Streaming ответ
│   ├── Tasks/
│   │   ├── TaskList.tsx         # Список TODO
│   │   └── TaskItem.tsx         # Один TODO item
│   ├── Questions/
│   │   └── ClarificationModal.tsx # Уточняющие вопросы
│   ├── Code/
│   │   ├── CodePreview.tsx      # Monaco editor
│   │   └── FileDiff.tsx         # Diff view
│   └── Actions/
│       └── PublishButton.tsx    # Кнопка публикации
├── hooks/
│   ├── useWebSocket.ts          # WebSocket connection
│   ├── useChat.ts               # Chat state
│   └── useTasks.ts              # TODO state
├── api/
│   └── opencode.ts              # API клиент
└── App.tsx
```

**Wireframe:**

```
┌─────────────────────────────────────────────────────────────────┐
│  Logo    Session: "Новый виджет котировок"           [Publish]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────┐  ┌──────────────────┐ │
│  │                                     │  │ Tasks            │ │
│  │  User: Добавь виджет котировок      │  │                  │ │
│  │                                     │  │ ✓ Найти API      │ │
│  │  Agent: Уточните источник данных:   │  │ ✓ Создать тип    │ │
│  │         ○ Alpha Vantage             │  │ ● Компонент      │ │
│  │         ○ Yahoo Finance             │  │ ○ Интеграция     │ │
│  │         ● Другой                    │  │                  │ │
│  │                                     │  ├──────────────────┤ │
│  │  User: Yahoo Finance                │  │ Files            │ │
│  │                                     │  │                  │ │
│  │  Agent: Создаю компонент...         │  │ + StockWidget.tsx│ │
│  │         ```tsx                      │  │ + api/stocks.ts  │ │
│  │         export const StockWidget... │  │ ~ Dashboard.tsx  │ │
│  │         ```                         │  │                  │ │
│  │                                     │  └──────────────────┘ │
│  └─────────────────────────────────────┘                        │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Сообщение...                                        [Send] ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### Этап 4: Интеграции (1 неделя)

**Задачи:**
- [ ] MCP для Core Backend (portfolios, transactions, assets)
- [ ] Git интеграция (создание PR)
- [ ] Sandbox ограничения
- [ ] Permissions для пользователей

**MCP для Core Backend:**

```json
// mcp/core-backend.json
{
  "name": "core-backend",
  "tools": [
    {
      "name": "get_portfolios",
      "description": "Get user portfolios",
      "endpoint": "GET /mcp/portfolios"
    },
    {
      "name": "get_transactions",
      "description": "Get portfolio transactions",
      "endpoint": "GET /mcp/transactions?portfolio_id={id}"
    },
    {
      "name": "get_assets",
      "description": "Get available assets",
      "endpoint": "GET /mcp/assets"
    }
  ]
}
```

**Git интеграция:**

```typescript
// После нажатия Publish
async function publish(sessionId: string) {
  const session = await getSession(sessionId);
  const files = session.generatedFiles;
  
  // 1. Создать ветку
  const branch = `user/${userId}/feature-${sessionId}`;
  await git.checkout('-b', branch);
  
  // 2. Записать файлы
  for (const file of files) {
    await fs.writeFile(file.path, file.content);
  }
  
  // 3. Commit
  await git.add('.');
  await git.commit(`[AI] ${session.title}`);
  
  // 4. Push и создать PR
  await git.push('-u', 'origin', branch);
  const pr = await github.createPullRequest({
    title: `[AI Generated] ${session.title}`,
    body: session.summary,
    head: branch,
    base: 'main'
  });
  
  return pr.url;
}
```

**Sandbox ограничения (opencode.json):**

```json
{
  "permissions": {
    "bash": "deny",
    "write": {
      "allow": ["src/user-components/**", "src/user-pages/**"],
      "deny": ["src/core/**", "config/**", ".env*"]
    },
    "read": {
      "deny": [".env*", "secrets/**"]
    }
  },
  "tools": {
    "webfetch": {
      "allowedDomains": [
        "api.alphavantage.co",
        "newsapi.org",
        "docs.*"
      ]
    }
  }
}
```

---

### Этап 5: Тестирование и доработка (1 неделя)

**Задачи:**
- [ ] Тестирование типичных сценариев
- [ ] Оптимизация промптов
- [ ] Обработка ошибок
- [ ] Логирование
- [ ] Документация для пользователей

---

## Timeline

```
Неделя 1:
├── День 1-2: Развёртывание сервера + vLLM + OpenCode
├── День 3-5: Изучение API OpenCode
└── День 6-7: Прототип Web UI (чат)

Неделя 2:
├── День 1-3: Web UI (TODO, вопросы, preview)
├── День 4-5: WebSocket streaming
└── День 6-7: Тестирование UI

Неделя 3:
├── День 1-2: MCP интеграция с Core Backend
├── День 3-4: Git + PR workflow
├── День 5: Sandbox permissions
└── День 6-7: Тестирование интеграций

Неделя 4:
├── День 1-3: Тестирование сценариев
├── День 4-5: Исправление багов
└── День 6-7: Документация
```

**Итого: 4 недели до MVP**

---

## Ресурсы

**OpenCode:**
- GitHub: https://github.com/opencode-ai/opencode
- Docs: https://opencode.ai/docs
- Tools: https://opencode.ai/docs/tools

**vLLM:**
- GitHub: https://github.com/vllm-project/vllm
- Docs: https://docs.vllm.ai

**Qwen:**
- Model: https://huggingface.co/Qwen/Qwen2.5-Coder-14B-Instruct

---

## Инфраструктура: Выбор сервера

### Требования

```
GPU:     24GB VRAM (для Qwen2.5-Coder-14B или 32B-AWQ)
RAM:     128GB (для OpenCode + сессии пользователей)
Storage: 1TB+ SSD/NVMe
Network: 1 Gbps
Тип:     Dedicated (чувствительные данные)
Регион:  EU (GDPR)
```

### Рекомендуемые варианты

#### Вариант 1: Unihost LWN-G10 (Нидерланды) — €338-450/мес

```
GPU:     Nvidia A30 (24GB VRAM)
CPU:     2x AMD EPYC 7402
RAM:     128 GB DDR4
Storage: 2x 960 GB SSD
Network: 1 Gbps / 30 TB
Setup:   €0

Цена:    €337.90/мес (акция) или €450.90/мес (стандарт)
```

**Плюсы:**
- A30 — datacenter GPU, стабильный
- 24GB VRAM — Qwen-14B и 32B-AWQ
- 128GB RAM — достаточно для production
- EU, GDPR compliant

**Ссылка:** https://unihost.com/dedicated/ai-servers/

#### Вариант 2: Unihost LWE-G4 (UK) — €424/мес

```
GPU:     Nvidia A30 (24GB VRAM)
CPU:     2x AMD EPYC 7402
RAM:     128 GB DDR4
Storage: 2x 960 GB SSD
Network: 1 Gbps / 30 TB

Цена:    €424.33/мес (со скидкой)
```

#### Вариант 3: Hetzner GEX44 (Германия) — €184/мес (бюджет)

```
GPU:     NVIDIA RTX 4000 SFF Ada (20GB VRAM)
CPU:     Intel Core i5-13500 (14 cores)
RAM:     64 GB DDR4
Storage: 2x 1.92 TB NVMe SSD
Network: 1 Gbps unlimited
Setup:   €159 (разово)

Цена:    €184/мес
```

**Ограничения:**
- 20GB VRAM — только Qwen-14B (int8)
- 64GB RAM — меньше чем нужно
- Qwen-32B не влезет

**Ссылка:** https://www.hetzner.com/dedicated-rootserver/gex44/

### Сравнение

| Провайдер | GPU | VRAM | RAM | Цена | Qwen-14B | Qwen-32B |
|-----------|-----|------|-----|------|----------|----------|
| **Unihost LWN-G10** | A30 | 24GB | 128GB | €338-450 | ✅ | ✅ AWQ |
| Unihost LWE-G4 | A30 | 24GB | 128GB | €424 | ✅ | ✅ AWQ |
| Hetzner GEX44 | RTX 4000 | 20GB | 64GB | €184 | ✅ int8 | ❌ |

### Рекомендация

**Для MVP:** Unihost LWN-G10 за €338/мес (если акция доступна) или LWE-G4 за €424/мес.

**Для экономии:** Hetzner GEX44 за €184/мес, но только с Qwen-14B.

### Альтернативы (не рекомендуются для чувствительных данных)

| Провайдер | Тип | Цена | Почему нет |
|-----------|-----|------|------------|
| RunPod | Cloud | ~$80/мес | Shared infrastructure |
| Vast.ai | P2P | ~$60/мес | Данные на чужих машинах |
| Scaleway | Cloud | €548/мес | Дороже dedicated |

---

## Риски и митигация

| Риск | Вероятность | Митигация |
|------|-------------|-----------|
| OpenCode API не документирован | Высокая | Читать исходный код |
| Сложности с WebSocket | Средняя | Изучить существующий TUI код |
| Качество генерации | Средняя | Тюнинг промптов, fallback на 32B |
| Context overflow | Средняя | Auto-compact уже есть |
| GPU memory issues | Низкая | Мониторинг, 14B вместо 32B |

---

## Следующий шаг

1. Арендовать сервер
2. Развернуть vLLM + OpenCode
3. Начать изучение API
