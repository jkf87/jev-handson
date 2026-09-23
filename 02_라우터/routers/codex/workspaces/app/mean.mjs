export function mean(values) {
  return values.reduce((total, value) => total + value, 0) / values.length;
}
