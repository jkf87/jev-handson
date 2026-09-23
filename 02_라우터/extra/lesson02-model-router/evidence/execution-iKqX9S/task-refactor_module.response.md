## 전제

실제 파일이 없으므로 다음을 가정하고 설계합니다. 다르면 해당 부분만 치환하세요.

- Express 4.x, 단일 `router.js`(약 400줄), 엔드포인트 8~15개 추정
- DB는 커넥션 풀 기반 (`pg` / Knex / Sequelize 중 하나). 예시는 `pg` 풀 + 명시적 `client` 전달 방식으로 씁니다.
- 검증은 핸들러 안에서 `if (!req.body.x) return res.status(400)...` 형태로 인라인
- 기존 응답 스키마와 상태 코드는 **바꾸지 않는 것**이 이번 작업의 제약

---

## 1. 목표 구조

```
src/
  routes/orders.routes.js      # 경로·미들웨어 결선만
  controllers/orders.controller.js
  services/orders.service.js
  repositories/orders.repo.js
  repositories/users.repo.js
  db/unit-of-work.js           # 트랜잭션 경계
  validation/orders.schema.js
  errors/AppError.js
  middleware/error-handler.js
```

### 계층별 책임 (어기면 리뷰에서 반려할 규칙)

| 계층 | 하는 일 | 절대 안 하는 일 |
|---|---|---|
| routes | path ↔ controller 매핑, 인증/파싱 미들웨어 부착 | 비즈니스 분기 |
| controller | `req` → DTO 변환, 서비스 호출, 상태코드·응답 바디 조립 | SQL, 도메인 규칙 |
| service | 도메인 규칙, 여러 repo 조합, **트랜잭션 경계 선언** | `req`/`res` 참조, HTTP 상태코드 |
| repository | SQL/ORM 호출, row → 도메인 객체 매핑 | 트랜잭션 시작/커밋, 권한 판단 |

핵심 불변식 두 개:
- **`req`, `res`는 controller 밖으로 나가지 않는다.** 서비스는 HTTP를 모른다.
- **커밋/롤백은 service만 한다.** repository는 주어진 `client`를 쓸 뿐이다.

---

## 2. 이관 절차 (스트랭글러 방식)

한 번에 400줄을 옮기지 말고 엔드포인트 단위로 자릅니다.

**0단계 — 안전망 먼저.** 리팩터링 코드를 한 줄도 쓰기 전에 현행 라우터 대상 통합 테스트(4절)를 작성해 초록으로 만듭니다. 이게 없으면 "동작 보존"을 주장할 근거가 없습니다.

**1단계 — 수직 분할.** 가장 단순한 읽기 전용 엔드포인트(예: `GET /orders/:id`) 하나만 controller/service/repo로 관통시킵니다. 구조가 맞는지 여기서 검증합니다.

**2단계 — 순수 함수 추출.** 응답 조립·계산 로직을 인자만 받는 함수로 빼냅니다. 이 단계는 DB를 안 건드리므로 리스크가 가장 낮습니다.

**3단계 — repository 추출.** 라우터 안의 모든 쿼리를 repo 메서드로 옮깁니다. 이때 SQL 텍스트는 **복사만 하고 수정 금지**합니다. 쿼리 튜닝은 별도 PR로.

**4단계 — 쓰기 엔드포인트 + 트랜잭션.** 3절 UoW를 도입해 다중 쓰기 엔드포인트를 옮깁니다. 가장 위험한 단계이므로 마지막에 둡니다.

**5단계 — 검증/에러 통일.** 인라인 검증을 스키마로, `res.status(4xx)` 직접 호출을 `AppError` + 에러 핸들러로 치환합니다. **이 단계에서 상태코드·메시지 문구가 바뀌기 쉬우니** 0단계 테스트가 문구까지 고정하고 있어야 합니다.

각 단계는 독립 PR로, 단계마다 전체 테스트 초록을 확인하고 다음으로 갑니다.

---

## 3. 트랜잭션 경계

### 원칙

트랜잭션은 **서비스의 public 메서드 = 유스케이스 1개**를 경계로 합니다. 이유:

- repository가 트랜잭션을 열면 "주문 생성 + 재고 차감"처럼 두 repo를 묶을 수 없습니다.
- controller가 열면 HTTP 계층이 DB 수명주기를 알게 되어 서비스 재사용(배치·큐 컨슈머)이 막힙니다.

### 구현: 명시적 `client` 전달

가장 단순하고 추적 가능한 방식입니다. repo 시그니처 첫 인자가 항상 실행 컨텍스트입니다.

```js
// db/unit-of-work.js
const { pool } = require('./pool');

async function withTransaction(fn) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const result = await fn(client);
    await client.query('COMMIT');
    return result;
  } catch (err) {
    await client.query('ROLLBACK').catch(() => {}); // 롤백 실패가 원인 에러를 가리지 않도록
    throw err;
  } finally {
    client.release();
  }
}

module.exports = { withTransaction };
```

```js
// repositories/orders.repo.js  — db는 pool 또는 트랜잭션 client
async function insertOrder(db, { userId, totalAmount, status }) {
  const { rows } = await db.query(
    `INSERT INTO orders (user_id, total_amount, status)
     VALUES ($1, $2, $3) RETURNING *`,
    [userId, totalAmount, status]
  );
  return toDomain(rows[0]);
}

async function findById(db, id) {
  const { rows } = await db.query('SELECT * FROM orders WHERE id = $1', [id]);
  return rows[0] ? toDomain(rows[0]) : null;
}
```

```js
// services/orders.service.js
const { withTransaction } = require('../db/unit-of-work');
const { pool } = require('../db/pool');
const ordersRepo = require('../repositories/orders.repo');
const inventoryRepo = require('../repositories/inventory.repo');
const { AppError } = require('../errors/AppError');

async function getOrder(id) {
  const order = await ordersRepo.findById(pool, id);   // 읽기 전용은 트랜잭션 불필요
  if (!order) throw new AppError('ORDER_NOT_FOUND', 404, 'Order not found');
  return order;
}

async function createOrder({ userId, items }) {
  return withTransaction(async (tx) => {
    const total = items.reduce((s, i) => s + i.price * i.quantity, 0);
    const order = await ordersRepo.insertOrder(tx, {
      userId, totalAmount: total, status: 'PENDING',
    });
    for (const item of items) {
      const ok = await inventoryRepo.decrement(tx, item.sku, item.quantity);
      if (!ok) throw new AppError('OUT_OF_STOCK', 409, `Out of stock: ${item.sku}`);
    }
    await ordersRepo.insertItems(tx, order.id, items);
    return order;
  });
}
```

### 지켜야 할 세부 규칙

1. **중첩 금지.** 서비스 메서드끼리 호출하면 트랜잭션이 이중으로 열립니다. `createOrder`가 `getOrder`를 부르면 안 됩니다. 해법: 내부용 `_createOrderTx(tx, dto)`를 두고, public 메서드는 `withTransaction`으로 감싸는 얇은 껍데기로만 둡니다. 다른 서비스가 필요하면 `_` 버전을 `tx`와 함께 호출합니다.
2. **외부 I/O를 트랜잭션 안에 넣지 않습니다.** 결제 API 호출, 이메일 발송, S3 업로드는 커밋 **이후**로. 기존 라우터가 이미 커밋 전에 하고 있었다면, 동작 보존이 우선이므로 일단 그대로 옮기고 별도 이슈로 분리해 기록하세요.
3. **경계는 서비스에서만 보입니다.** controller는 `tx`라는 단어를 몰라야 합니다.

> `AsyncLocalStorage`로 `tx`를 암묵 전파하는 방법도 있습니다. 시그니처가 깨끗해지지만 "지금 트랜잭션 안인가"가 코드에서 안 보여 디버깅이 어렵습니다. 400줄 규모라면 명시적 전달을 권합니다.

---

## 4. 순환 의존

### 왜 생기는가

계층 분리 직후 흔한 경로는 `OrderService → UserService → OrderService`(유저 삭제 시 주문 확인) 같은 형태입니다.

### 차단 규칙

의존 방향을 **단방향**으로 고정합니다: `routes → controller → service → repository → db`. 역방향과 계층 건너뛰기(controller가 repo 직접 호출)를 모두 금지합니다. 같은 계층 내부(service ↔ service)만 순환 위험이 남습니다.

### 실제 순환이 났을 때, 우선순위 순 해법

1. **repository로 낮춘다.** `UserService`가 `OrderService`에서 필요한 게 "해당 유저의 미결 주문 수"뿐이라면, `ordersRepo.countPending(db, userId)`를 직접 호출합니다. 같은 계층 참조가 사라집니다. 대부분 이걸로 해결됩니다.
2. **상위 오케스트레이터를 만든다.** 양쪽 도메인 규칙이 진짜로 필요하면 `CheckoutService`처럼 둘 다 의존하는 유스케이스 서비스를 신설하고, 두 서비스는 서로를 모르게 둡니다.
3. **의존성 역전.** `OrderService`가 인터페이스(`UserLookup`)만 알게 하고, 구현 주입은 조립 지점에서 합니다.
4. **이벤트로 끊는다.** "유저 삭제 → 주문 아카이브"처럼 비동기 허용 흐름만. 트랜잭션 경계가 갈라지므로 남용 금지.

`require` 순환은 **팩토리 주입**으로도 막습니다. 모듈 최상위에서 서로를 `require`하지 말고, 각 모듈이 의존성을 인자로 받는 팩토리를 export하고 `container.js` 한 곳에서 결선합니다. 부수 효과로 테스트에서 가짜 repo 주입이 쉬워집니다.

**자동 검사:** CI에 `npx madge --circular src/` 또는 ESLint `import/no-cycle`을 추가하세요. 수동 리뷰로는 계속 새어 나옵니다.

---

## 5. 리팩터링 전/후 대비

### 전 (현행 추정)

```js
router.post('/orders', async (req, res) => {
  const { userId, items } = req.body;
  if (!userId) return res.status(400).json({ error: 'userId required' });
  if (!Array.isArray(items) || items.length === 0)
    return res.status(400).json({ error: 'items required' });

  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const total = items.reduce((s, i) => s + i.price * i.quantity, 0);
    const { rows } = await client.query(
      `INSERT INTO orders (user_id, total_amount, status)
       VALUES ($1, $2, 'PENDING') RETURNING *`, [userId, total]);
    // ... 재고 차감, 아이템 삽입 ...
    await client.query('COMMIT');
    res.status(201).json({ id: rows[0].id, total: rows[0].total_amount, status: rows[0].status });
  } catch (e) {
    await client.query('ROLLBACK');
    res.status(500).json({ error: 'internal error' });
  } finally {
    client.release();
  }
});
```

### 후

```js
// routes/orders.routes.js
const router = require('express').Router();
const c = require('../controllers/orders.controller');
const { validate } = require('../middleware/validate');
const { createOrderSchema } = require('../validation/orders.schema');

router.post('/orders', validate(createOrderSchema), c.createOrder);
router.get('/orders/:id', c.getOrder);
module.exports = router;
```

```js
// controllers/orders.controller.js
const ordersService = require('../services/orders.service');

async function createOrder(req, res, next) {
  try {
    const order = await ordersService.createOrder({
      userId: req.body.userId,
      items: req.body.items,
    });
    // 기존 응답 형태를 한 글자도 바꾸지 않는다
    res.status(201).json({
      id: order.id,
      total: order.totalAmount,
      status: order.status,
    });
  } catch (err) {
    next(err);
  }
}

async function getOrder(req, res, next) {
  try {
    const order = await ordersService.getOrder(req.params.id);
    res.status(200).json({ id: order.id, total: order.totalAmount, status: order.status });
  } catch (err) {
    next(err);
  }
}

module.exports = { createOrder, getOrder };
```

```js
// middleware/error-handler.js  — 라우터 등록 후 마지막에 app.use()
const { AppError } = require('../errors/AppError');

function errorHandler(err, req, res, _next) {
  if (err instanceof AppError) {
    return res.status(err.status).json({ error: err.message });
  }
  req.log?.error({ err }, 'unhandled');
  return res.status(500).json({ error: 'internal error' });  // 기존 문구 유지
}
module.exports = { errorHandler };
```

검증 미들웨어가 반환하는 400 바디도 **기존 문구(`{ error: 'userId required' }`)를 그대로 재현**해야 합니다. 스키마 라이브러리 기본 에러 포맷을 그냥 내보내면 여기서 계약이 깨집니다.

---

## 6. 통합 테스트 계획

### 전략: 특성화 테스트(characterization test)

"올바른 동작"이 아니라 **"현재 동작"**을 기록하는 것이 목적입니다. 기존 버그도 그대로 고정합니다(고칠 거면 별도 PR).

### 레벨 구분

| 레벨 | 대상 | DB | 비중 |
|---|---|---|---|
| L1 통합 | `supertest`로 앱 전체 + 실제 DB | 실 DB (컨테이너) | **주력** |
| L2 서비스 | service + 실 repo | 실 DB | 트랜잭션·롤백 검증용 |
| L3 단위 | 순수 계산 함수 | 없음 | 경계값용 |

controller를 mock service로 단위 테스트하는 건 가치가 낮습니다(껍데기라서). L1에 무게를 두세요.

### DB 전략

Testcontainers 또는 docker-compose로 실 Postgres를 띄웁니다. SQLite 대체는 금물 — SQL 방언 차이 때문에 "테스트는 통과하는데 운영은 깨지는" 상황이 생깁니다.

격리는 **테스트마다 트랜잭션을 열고 끝나면 롤백**하는 방식이 가장 빠릅니다. 단, 프로덕션 코드가 자체 트랜잭션을 열면 중첩되므로 `SAVEPOINT` 처리가 필요합니다. 복잡하다면 `TRUNCATE ... RESTART IDENTITY CASCADE`로 단순하게 가세요.

### 커버리지 기준 (리팩터링 착수 조건)

각 엔드포인트에 대해 최소 이 조합이 있어야 합니다:

- 해피 패스 1개 — 상태코드 + **응답 바디 전체 shape**
- 검증 실패 — 필드별로 상태코드와 **에러 메시지 문구까지**
- 미존재 리소스 404
- 권한 실패 401/403 (해당 시)
- **다중 쓰기 엔드포인트는 실패 주입 후 롤백 확인** ← 가장 중요

### 테스트 코드

```js
// test/helpers/app.js
const express = require('express');
const ordersRoutes = require('../../src/routes/orders.routes');
const { errorHandler } = require('../../src/middleware/error-handler');

function buildApp() {
  const app = express();
  app.use(express.json());
  app.use('/api', ordersRoutes);
  app.use(errorHandler);
  return app;
}
module.exports = { buildApp };
```

```js
// test/integration/orders.test.js
const request = require('supertest');
const { buildApp } = require('../helpers/app');
const { pool } = require('../../src/db/pool');
const { seedUser, seedInventory } = require('../helpers/fixtures');

const app = buildApp();

beforeEach(async () => {
  await pool.query('TRUNCATE orders, order_items, inventory, users RESTART IDENTITY CASCADE');
});
afterAll(async () => { await pool.end(); });

describe('POST /api/orders', () => {
  test('주문 생성 시 201과 기존 응답 형태를 반환한다', async () => {
    const user = await seedUser({ id: 1 });
    await seedInventory({ sku: 'A1', quantity: 10 });

    const res = await request(app)
      .post('/api/orders')
      .send({ userId: user.id, items: [{ sku: 'A1', price: 1000, quantity: 2 }] });

    expect(res.status).toBe(201);
    // 필드 추가/제거를 잡기 위해 shape 전체를 비교한다
    expect(Object.keys(res.body).sort()).toEqual(['id', 'status', 'total']);
    expect(res.body.status).toBe('PENDING');
    expect(res.body.total).toBe(2000);
  });

  test('userId 누락 시 400과 기존 메시지를 유지한다', async () => {
    const res = await request(app).post('/api/orders').send({ items: [] });
    expect(res.status).toBe(400);
    expect(res.body).toEqual({ error: 'userId required' });
  });

  test('재고 부족 시 409이며 주문이 전혀 남지 않는다 (롤백)', async () => {
    await seedUser({ id: 1 });
    await seedInventory({ sku: 'A1', quantity: 1 });

    const res = await request(app)
      .post('/api/orders')
      .send({ userId: 1, items: [{ sku: 'A1', price: 1000, quantity: 5 }] });

    expect(res.status).toBe(409);
    const { rows } = await pool.query('SELECT count(*)::int AS c FROM orders');
    expect(rows[0].c).toBe(0);            // 부분 커밋이 없어야 한다
    const inv = await pool.query('SELECT quantity FROM inventory WHERE sku = $1', ['A1']);
    expect(inv.rows[0].quantity).toBe(1); // 재고도 원복
  });
});
```

```js
// test/integration/transaction.test.js — 두 번째 repo 실패 시 첫 쓰기가 롤백되는지
const ordersService = require('../../src/services/orders.service');
const inventoryRepo = require('../../src/repositories/inventory.repo');
const { pool } = require('../../src/db/pool');

test('중간 단계 예외 발생 시 앞선 INSERT가 롤백된다', async () => {
  const spy = jest.spyOn(inventoryRepo, 'decrement')
    .mockRejectedValue(new Error('boom'));

  await expect(
    ordersService.createOrder({ userId: 1, items: [{ sku: 'A1', price: 100, quantity: 1 }] })
  ).rejects.toThrow('boom');

  const { rows } = await pool.query('SELECT count(*)::int AS c FROM orders');
  expect(rows[0].c).toBe(0);

  spy.mockRestore();
});
```

### 차분 검증 (권장)

L1 테스트를 **리팩터링 전 코드에 대해 먼저 초록으로** 만든 뒤, 같은 테스트 파일을 수정 없이 리팩터링 후 코드에 돌립니다. 테스트를 손대야 한다면 그건 동작이 바뀌었다는 신호이므로, 의도한 변경인지 반드시 확인하세요.

더 강한 보장이 필요하면 구/신 라우터를 동시에 띄우고 동일 요청을 양쪽에 보내 응답을 diff하는 스크립트를 임시로 운영하는 방법도 있습니다(shadow 비교).

---

## 7. 검증 체크리스트

- [ ] `madge --circular src/` 결과 0건
- [ ] `grep -rn "res\.\|req\." src/services src/repositories` → 0건
- [ ] `grep -rn "BEGIN\|COMMIT\|ROLLBACK" src/repositories` → 0건
- [ ] `grep -rn "pool\.query\|client\.query" src/controllers` → 0건
- [ ] 모든 엔드포인트의 상태코드·응답 키 집합이 리팩터링 전과 동일
- [ ] 쓰기 엔드포인트마다 롤백 테스트 1개 이상

---

## 고지

위 코드는 실제 파일을 보지 않고 일반적인 Express + `pg` 구조를 가정해 작성한 **템플릿**입니다. 저는 이 환경에서 파일을 읽거나 명령을 실행하지 않았으므로, 제시한 테스트를 **실행하지 않았고 통과 여부도 확인하지 않았습니다.** 테이블·컬럼명, 기존 응답 스키마, 에러 메시지 문구는 실제 라우터에 맞춰 반드시 치환해야 합니다.

실제 `router.js` 내용을 붙여주시면 엔드포인트별 분해 매핑표와 실제 응답 스키마에 맞춘 테스트 케이스를 구체적으로 작성해 드리겠습니다.
