# 🐛 Known Issues & Workarounds

**Last Updated:** 2025-12-27  
**Project:** LangGraph Medical Center v1.0.0

---

## 🔴 ACTIVE ISSUES

### 1. **Event Loop Conflicts with eventlet + asyncpg**

**Status:** ⚠️ WORKAROUND APPLIED  
**Severity:** MEDIUM  
**Affected:** Message persistence to PostgreSQL  
**Commit:** `4dd8d27`

#### **Problem:**

```
❌ Error: Task got Future attached to a different loop
⚠️ Conexión corrupta detectada
❌ Error guardando mensaje: cannot perform operation: another operation is in progress
```

#### **Root Cause:**

Flask + SocketIO + eventlet + asyncpg is an **incompatible architecture**:

1. **Eventlet** monkey-patches asyncio and creates its own event loop
2. **asyncpg** (PostgreSQL async driver) expects a consistent event loop
3. **`run_until_complete()`** in eventlet background tasks tries to use original loop
4. **Result:** Event loop mismatch → connection pool corruption

```python
# Problematic pattern in app.py:
loop = asyncio.get_event_loop()  # Original loop
loop.run_until_complete(async_fn())  # Blocks, uses different loop

# Eventlet creates separate loop for background tasks
socketio.start_background_task(run_async_handler)
```

#### **Current Workaround:**

Message persistence is **disabled** after graph execution:

```python
# app.py lines 374-384
# Messages NOT saved to DB after streaming
# Only kept in-memory by LangGraph checkpointer
```

**Impact:**
- ✅ System works perfectly
- ✅ User gets responses
- ✅ Graph execution succeeds
- ✅ Checkpointer keeps state (in-memory)
- ❌ Messages NOT persisted to PostgreSQL
- ❌ No message history across restarts

#### **Proper Solutions (in priority order):**

##### **Option 1: Migrate to FastAPI** (RECOMMENDED)

**Pros:**
- Native async/await (no eventlet)
- asyncpg works perfectly
- Better performance
- Modern framework

**Cons:**
- 2-3 days of migration work
- Need to rewrite WebSocket handlers
- Different patterns than Flask

**Effort:** 2-3 days  
**Files affected:** ~5 files (app.py, routers)

```python
# FastAPI example:
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    # Direct async/await, no event loop mixing
    result = await graph_manager.stream(state, config)
    async for event in result:
        await websocket.send_json(event)
```

##### **Option 2: Use psycopg2 (sync) instead of asyncpg**

**Pros:**
- Quick fix (1-2 hours)
- No event loop conflicts
- Works with eventlet

**Cons:**
- Blocks worker threads
- Lower throughput
- Not modern async pattern

**Effort:** 1-2 hours  
**Files affected:** 2 files (database_service.py, conversation_memory.py)

```python
# Replace asyncpg with psycopg2:
import psycopg2
from psycopg2.pool import ThreadedConnectionPool

pool = ThreadedConnectionPool(minconn=2, maxconn=10, dsn=DATABASE_URL)

def add_message(message):
    conn = pool.getconn()
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO messages ...", (message,))
        conn.commit()
    finally:
        pool.putconn(conn)
```

##### **Option 3: Message Queue for Async Persistence**

**Pros:**
- Decouples persistence from request handling
- Can use asyncpg
- No blocking

**Cons:**
- Adds complexity (Redis/RabbitMQ)
- More infrastructure
- Eventual consistency

**Effort:** 3-4 days  
**Dependencies:** Redis or RabbitMQ

```python
# Using Celery + Redis:
from celery import Celery

celery = Celery('tasks', broker='redis://localhost:6379')

@celery.task
def save_message_async(message_dict):
    # Runs in separate worker with own event loop
    asyncio.run(conversation_memory.add_message(message))

# In app.py:
save_message_async.delay(message.to_dict())
```

---

### 2. **Docker Compose version attribute warning**

**Status:** ⚠️ COSMETIC  
**Severity:** LOW

#### **Warning:**

```
time="2025-12-27T23:18:55+01:00" level=warning msg="docker-compose.yml: 
the attribute `version` is obsolete, it will be ignored"
```

#### **Fix:**

Remove `version: '3.8'` from docker-compose.yml:

```yaml
# OLD:
version: '3.8'
services:
  ...

# NEW:
services:
  ...
```

**Effort:** 30 seconds

---

### 3. **Environment variables not set warnings**

**Status:** ⚠️ EXPECTED  
**Severity:** LOW

#### **Warnings:**

```
The "OPENAI_API_KEY" variable is not set. Defaulting to a blank string.
The "FLASK_SECRET_KEY" variable is not set. Defaulting to a blank string.
```

#### **Fix:**

Create `.env` file in project root:

```bash
# .env
OPENAI_API_KEY=sk-...your-key...
FLASK_SECRET_KEY=your-secret-key-here
OPENAI_MODEL=gpt-4o
LOG_LEVEL=INFO
```

Then load it:

```bash
# Option A: Export before running
export $(cat .env | xargs)
docker-compose up

# Option B: Use --env-file
docker-compose --env-file .env up

# Option C: Add to docker-compose.yml
services:
  app:
    env_file:
      - ../.env
```

**Effort:** 1 minute

---

## 🟡 MINOR ISSUES

### 4. **RLock warning with eventlet**

**Status:** ℹ️ INFORMATIONAL  
**Severity:** LOW

#### **Warning:**

```
9 RLock(s) were not greened, to fix this error make sure you 
run eventlet.monkey_patch() before importing any other modules.
```

#### **Explanation:**

Some threading primitives (RLocks) were created before eventlet's monkey-patch.

**Impact:** Minimal - these locks still work, just not async-optimized

**Fix:** Ensure `eventlet.monkey_patch()` is first import in app.py (already done)

---

## ✅ RESOLVED ISSUES

### 5. **Slow Docker builds (pip)**

**Status:** ✅ FIXED in `d6b2896`  
**Solution:** Migrated to UV package manager

**Before:** 5-10 minutes  
**After:** 30 seconds  
**Improvement:** 10-20x faster

---

### 6. **No dependency lockfile**

**Status:** ✅ FIXED in `b16b156`  
**Solution:** Created uv.lock with hash verification

**Before:** requirements.txt (no hashes)  
**After:** uv.lock (SHA256 hashes)  
**Security:** 🔒 100% reproducible + verified

---

## 📊 Issue Priority Matrix

| Issue | Severity | Impact on Users | Fix Effort | Priority |
|-------|----------|-----------------|------------|----------|
| Event loop conflicts | MEDIUM | LOW (workaround active) | 2-3 days | HIGH |
| Docker warnings | LOW | NONE | 1 min | LOW |
| Env vars warning | LOW | LOW | 1 min | LOW |
| RLock warning | LOW | NONE | N/A | LOW |

---

## 🎯 Recommended Action Plan

### **SHORT TERM (This Week):**

1. ✅ Apply workaround (message persistence disabled) - **DONE**
2. ⚠️ Fix .env warnings (create .env file) - **5 min**
3. ⚠️ Remove `version:` from docker-compose.yml - **30 sec**

### **MEDIUM TERM (Next 2 Weeks):**

4. 🔧 Option A: Migrate to FastAPI (best long-term) - **2-3 days**
5. 🔧 Option B: Replace asyncpg with psycopg2 (quick fix) - **2 hours**

### **LONG TERM (Next Month):**

6. 📈 Implement observability (Prometheus, Grafana)
7. 🔐 Add security scanning (bandit, trivy)
8. 🧪 Increase test coverage (70% → 90%)
9. 🚀 Set up CI/CD pipeline (GitHub Actions)

---

## 💬 Questions?

**For issue #1 (event loop):**  
- Does the system need to persist messages across restarts?
- Is in-memory checkpointing acceptable?
- Willing to migrate to FastAPI?

**For other issues:**  
- Check `DEVELOPMENT.md` for dev setup
- Check `DOCKER_UV_MIGRATION.md` for Docker details

---

**Maintained by:** Medical AI Team  
**Last Review:** 2025-12-27
