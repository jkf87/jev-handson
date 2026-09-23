# 수정된 배열 평균 함수

빈 배열 체크를 추가하여 문제를 해결했습니다.

## 수정된 함수

```javascript
function mean(xs) {
  if (xs.length === 0) {
    return null;
  }
  return xs.reduce((a, b) => a + b, 0) / xs.length;
}
```

## 경계 조건 테스트

```javascript
// 빈 배열 테스트
console.assert(mean([]) === null, "빈 배열은 null을 반환해야 함");

// 단일 요소
console.assert(mean([5]) === 5, "단일 요소는 그 값을 반환해야 함");

// 일반 입력
console.assert(mean([1, 2, 3]) === 2, "배열 [1,2,3]의 평균은 2");
console.assert(mean([10, 20]) === 15, "배열 [10,20]의 평균은 15");

// 음수 포함
console.assert(mean([-1, 1]) === 0, "배열 [-1,1]의 평균은 0");

// 부동소수점
console.assert(mean([1, 2, 3, 4]) === 2.5, "배열 [1,2,3,4]의 평균은 2.5");

console.log("모든 테스트 완료");
```

**주요 변경사항:**
- `xs.length === 0` 조건으로 빈 배열 확인
- 빈 배열일 때 `null` 반환
- 그 외 모든 경우 기존 로직 유지

테스트 코드는 제시된 형태이며, 실제 실행 환경에서 실행하여 검증해야 합니다.
