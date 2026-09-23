## 수정된 함수

```javascript
function mean(xs) {
  if (xs.length === 0) return null;
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}
```

빈 배열일 때 `xs.length === 0`을 먼저 검사해 `null`을 반환하고, 그 외에는 기존 로직을 그대로 유지했습니다.

## 테스트 코드

```javascript
const assert = require('assert');

// 빈 배열 -> null
assert.strictEqual(mean([]), null);

// 단일 원소
assert.strictEqual(mean([5]), 5);

// 일반 입력 (기존 동작 유지)
assert.strictEqual(mean([1, 2, 3]), 2);

// 음수 포함
assert.strictEqual(mean([-1, 0, 1]), 0);

// 소수 결과
assert.strictEqual(mean([1, 2]), 1.5);

console.log('All tests passed');
```

이 테스트는 실행하지 않았습니다. 실제로 실행해 통과 여부를 확인해 주세요.
