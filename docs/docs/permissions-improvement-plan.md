# Permissions Improvement Plan

## Context

Сейчас при вступлении пользователя в организацию он не получает доступ ни к одному орбиту — нужно руками добавлять в каждый. Система задумывалась по аналогии с Jira (org = company, orbit = project), и логично чтобы новые мемберы/админы орги автоматически становились мемберами/админами во всех орбитах. Это будет настройкой с дефолтом `true`.

**Маппинг ролей:** `org admin → orbit admin`, `org member → orbit member`.

**Два триггера автодобавления:**
1. Юзер принимает инвайт в организацию → добавляется во все текущие орбиты
2. Создаётся новый орбит → все текущие члены орги добавляются в него

---

## Backend

### 1. Миграция БД
**Новый файл:** `backend/migrations/versions/033_add_auto_add_members_to_orbits.py`

```sql
ALTER TABLE organizations ADD COLUMN auto_add_members_to_orbits BOOLEAN NOT NULL DEFAULT TRUE;
```

### 2. Organization ORM
**Файл:** `backend/luml/models/organization.py`

```python
auto_add_members_to_orbits: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
```

### 3. Schemas
**Файл:** `backend/luml/schemas/organization.py`

- В `OrganizationDetails` добавить: `auto_add_members_to_orbits: bool`
- В `OrganizationUpdate` добавить: `auto_add_members_to_orbits: bool | None = None`

### 4. Organization Handler — accept_invite
**Файл:** `backend/luml/handlers/organizations.py`

После `create_organization_member(...)`:
```python
org = await self.__organizations_repository.get_organization(invite.organization_id)
if org.auto_add_members_to_orbits:
    orbit_role = OrbitRole.ADMIN if invite.role == OrgRole.ADMIN else OrbitRole.MEMBER
    orbits = await self.__orbits_repository.get_orbits(invite.organization_id)
    for orbit in orbits:
        try:
            await self.__orbits_repository.create_orbit_member(
                OrbitMemberCreate(user_id=user_id, orbit_id=orbit.id, role=orbit_role)
            )
        except DatabaseConstraintError:
            pass  # already a member, skip
```

### 5. Orbit Handler — create_orbit
**Файл:** `backend/luml/handlers/orbits.py`

После добавления создателя как admin:
```python
org = await self.__organizations_repository.get_organization(organization_id)
if org.auto_add_members_to_orbits:
    org_members = await self.__user_repository.get_organization_members(organization_id)
    for member in org_members:
        if member.user_id == user_id:
            continue  # creator already added as admin
        orbit_role = OrbitRole.ADMIN if member.role == OrgRole.ADMIN else OrbitRole.MEMBER
        try:
            await self.__orbits_repository.create_orbit_member(
                OrbitMemberCreate(user_id=member.user_id, orbit_id=new_orbit.id, role=orbit_role)
            )
        except DatabaseConstraintError:
            pass
```

---

## Frontend

### 6. TypeScript types
**Файл:** `frontend/src/lib/api/api.interfaces.ts`

- В `OrganizationDetails`: `auto_add_members_to_orbits: boolean`
- В `CreateOrganizationPayload`: `auto_add_members_to_orbits?: boolean`

### 7. Settings UI
**Файл:** `frontend/src/components/organizations/OrganizationInfo.vue`

В диалоге "Organization settings" добавить toggle:
```
[toggle] Automatically add new members to all orbits
```
Привязать к `auto_add_members_to_orbits`, отправлять через `updateOrganization` (PATCH).

---

## Критические файлы

| Файл | Изменение |
|------|-----------|
| `backend/migrations/versions/033_add_auto_add_members_to_orbits.py` | новый файл |
| `backend/luml/models/organization.py` | новое поле ORM |
| `backend/luml/schemas/organization.py` | поле в Details и Update |
| `backend/luml/handlers/organizations.py` | логика в `accept_invite` |
| `backend/luml/handlers/orbits.py` | логика в `create_orbit` |
| `frontend/src/lib/api/api.interfaces.ts` | новое поле в типах |
| `frontend/src/components/organizations/OrganizationInfo.vue` | UI toggle |

---

## Верификация — auto-add

1. Пригласить юзера как `member` → проверить что он появился во всех орбитах как `member`
2. Пригласить юзера как `admin` → появился как orbit `admin`
3. Создать новый орбит → все существующие члены орги добавлены с правильными ролями
4. Выключить `auto_add_members_to_orbits` → новые мемберы и новые орбиты не добавляют автоматически
5. Toggle в UI сохраняется и отображает текущее состояние

---

## Изменения прав Orbit Member

### Что меняется

| Ресурс | Действие | Было | Станет |
|--------|----------|------|--------|
| Artifact | delete | — | ✅ |
| Artifact | deploy | — | ✅ |
| Deployment | update | ✅ | ✅ (только если статус не `active`) |
| Deployment | delete | — | ✅ (только если статус не `active`) |

**Collection: deploy** — этого действия не существует в системе, убрать из документации permissions.md.

### Логика

- Orbit member получает **полный контроль над артефактами**: создаёт, обновляет, удаляет, деплоит.
- **Деплойменты** — может смотреть и создавать (инициировать деплой), но не изменять и не удалять конфиг уже существующего деплоя. Это прерогатива orbit admin.
- **Коллекции** — без изменений: структура проекта, удаление и деплой только у admin.

### Backend

**Файл:** `backend/luml/schemas/permissions.py`

Обновить матрицу для `OrbitRole.MEMBER`:
- `Resource.ARTIFACT`: добавить `Action.DELETE`, `Action.DEPLOY`
- `Resource.DEPLOYMENT`: убрать `Action.UPDATE`

### Документация

**Файл:** `docs/docs/permissions.md`

Обновить таблицу Artifact — добавить ✅ для `Orbit: Member` в колонках `delete` и `deploy`.
Обновить таблицу Deployment — убрать ✅ у `Orbit: Member` в колонке `update`.
Убрать строку `deploy` из таблицы Collection (действие не существует).
Обновить описание в блоке `Orbit Roles` → `member`.

### Ограничение по статусу деплоймента

Orbit member может `update` и `delete` деплоймент, **но только если он не `active`**. Это бизнес-правило в хендлере, не в матрице прав.

**Файл:** `backend/luml/handlers/deployments.py` (или аналогичный)

В методах `update_deployment` и `delete_deployment` перед выполнением:
```python
if user_orbit_role == OrbitRole.MEMBER and deployment.status == DeploymentStatus.ACTIVE:
    raise InsufficientPermissionsError("Cannot modify an active deployment")
```

### Верификация — orbit member permissions

1. Залогиниться как orbit member → создать артефакт → задеплоить → удалить: всё должно работать
2. Попробовать обновить/удалить `active` деплоймент → 403
3. Остановить деплоймент → обновить/удалить → должно работать
4. Попробовать удалить коллекцию → 403

---

## Роль Orbit Viewer (read-only)

### Что добавляется

Новая orbit-роль `viewer` — только чтение, без создания/изменения/удаления. Для стейкхолдеров, менеджеров, внешних ревьюеров.

| Ресурс | list | read | create | update | delete | deploy |
|--------|:----:|:----:|:------:|:------:|:------:|:------:|
| Artifact | ✅ | ✅ | — | — | — | — |
| Collection | ✅ | ✅ | — | — | — | — |
| Deployment | ✅ | ✅ | — | — | — | — |
| Satellite | ✅ | ✅ | — | — | — | — |
| Orbit Secret | ✅ | — | — | — | — | — |

### Backend

- **`backend/luml/schemas/orbit.py`** — добавить `viewer` в `OrbitRole` enum
- **`backend/luml/schemas/permissions.py`** — добавить матрицу прав для `OrbitRole.VIEWER`
- **`backend/luml/models/orbit.py`** — обновить поле `role` в `OrbitMembersOrm` (новый допустимый вариант)
- **`backend/migrations/versions/034_add_orbit_viewer_role.py`** — новый файл, если роль хранится как enum в БД (ALTER TYPE)

### Frontend

- **`frontend/src/lib/api/api.interfaces.ts`** — добавить `viewer` в `OrbitRoleEnum`
- **`frontend/src/components/organizations/OrganizationOrbitSettings.vue`** — добавить `Viewer` в дропдаун выбора роли при добавлении участника

### Верификация

1. Добавить юзера как `viewer` → он видит артефакты/деплойменты, но кнопки create/edit/delete скрыты
2. Попытка создать артефакт через API → 403
3. Попытка прочитать значение секрета → 403

---

## Инвайт напрямую в орбит

### Что добавляется

Возможность пригласить человека сразу в орбит по email. Система автоматически:
1. Создаёт org-инвайт с ролью `member` (если юзер ещё не в орге)
2. После принятия — добавляет в указанный орбит с указанной orbit-ролью

Если юзер уже в орге — сразу добавляет в орбит без инвайта.

### Backend

- **`backend/luml/schemas/organization.py`** — новая схема `OrbitInviteCreate`: `email`, `orbit_id`, `orbit_role`
- **`backend/luml/models/organization.py`** — добавить опциональное поле `orbit_id` и `orbit_role` в `OrganizationInviteOrm` (чтобы после accept_invite знать куда добавить)
- **`backend/luml/handlers/organizations.py`** — в `accept_invite`: если у инвайта есть `orbit_id`, после создания org-членства добавить в орбит
- **`backend/luml/api/orbits/orbits_members.py`** — новый endpoint `POST /orbits/{orbit_id}/invites`
- **`backend/migrations/versions/034_add_orbit_invite_fields.py`** — добавить `orbit_id` (nullable FK) и `orbit_role` (nullable) в таблицу `organization_invites`

### Frontend

- **`frontend/src/components/organizations/OrganizationOrbitSettings.vue`** — форма "Invite by email" с выбором роли (вместо или рядом с текущим "Add existing member")
- **`frontend/src/lib/api/api.ts`** — новый метод `inviteToOrbit(organizationId, orbitId, data)`
- **`frontend/src/lib/api/api.interfaces.ts`** — новый тип `InviteToOrbitPayload`

### Верификация

1. Пригласить новый email в орбит → юзер получает инвайт → принимает → появляется в орге и в орбите
2. Пригласить существующего org-члена в орбит → сразу добавляется без инвайта
3. Пригласить с ролью `viewer` → появляется как viewer

---

## Скоупинг API-ключей по орбитам

### Что добавляется

При создании API-ключа можно указать список орбитов, к которым он даёт доступ. Если список пустой — ключ работает как сейчас (доступ ко всем орбитам пользователя). Полезно для CI/CD конкретного проекта.

### Backend

- **`backend/luml/models/`** — новая модель `ApiKeyOrbitOrm`: `api_key_id`, `orbit_id` (many-to-many)
- **`backend/luml/schemas/`** — добавить `orbit_ids: list[UUID] | None` в схему создания API-ключа
- **`backend/luml/handlers/permissions.py`** — при проверке прав по API-ключу: если у ключа есть orbit scope → проверять что запрашиваемый `orbit_id` входит в список
- **`backend/migrations/versions/035_add_api_key_orbit_scope.py`** — новая таблица `api_key_orbits`

### Frontend

- **`frontend/src/`** — в форме создания API-ключа добавить мультиселект орбитов (опционально, "All orbits" по умолчанию)

### Верификация

1. Создать ключ со скоупом на орбит A → запрос к орбиту A проходит, к орбиту B → 403
2. Создать ключ без скоупа → работает как раньше
3. Удалить орбит → связанные записи в `api_key_orbits` удаляются каскадом