/**
 * 서버는 Pydantic `Decimal` 을 JSON 문자열로 직렬화한다.
 * 화면 표시·연산 직전에 `toNum`, 표시 전용은 `format*` 사용.
 */

export const toNum = (v: string | number | null | undefined): number => {
  if (v === null || v === undefined) return 0;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
};

const krwFormatter = new Intl.NumberFormat("ko-KR", {
  style: "currency",
  currency: "KRW",
  maximumFractionDigits: 0,
});

const usdFormatter = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const compactKrwFormatter = new Intl.NumberFormat("ko-KR", {
  notation: "compact",
  maximumFractionDigits: 1,
});

export const formatKRW = (v: string | number | null | undefined): string => {
  if (v === null || v === undefined) return "—";
  return krwFormatter.format(toNum(v));
};

export const formatUSD = (v: string | number | null | undefined): string => {
  if (v === null || v === undefined) return "—";
  return usdFormatter.format(toNum(v));
};

/**
 * 큰 KRW 금액을 1.2억/3,400만 같은 축약 표기.
 */
export const formatKRWCompact = (v: string | number | null | undefined): string => {
  if (v === null || v === undefined) return "—";
  return `₩${compactKrwFormatter.format(toNum(v))}`;
};

export const formatPct = (
  v: string | number | null | undefined,
  digits = 1,
): string => {
  if (v === null || v === undefined) return "—";
  return `${toNum(v).toFixed(digits)}%`;
};

export const formatQty = (v: string | number | null | undefined): string => {
  if (v === null || v === undefined) return "—";
  const n = toNum(v);
  return Number.isInteger(n) ? n.toLocaleString("ko-KR") : n.toLocaleString("ko-KR", { maximumFractionDigits: 4 });
};
