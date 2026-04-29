const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

type QueryValue = string | number | boolean | null | undefined;

const buildUrl = (path: string, params?: Record<string, QueryValue>): string => {
  const url = new URL(path.replace(/^\/+/, "/"), API_BASE);
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value === undefined || value === null) continue;
      url.searchParams.set(key, String(value));
    }
  }
  return url.toString();
};

/**
 * REST GET. 에러는 ApiError 로 throw, 성공 시 JSON 반환.
 */
export async function apiGet<T>(
  path: string,
  params?: Record<string, QueryValue>,
): Promise<T> {
  const res = await fetch(buildUrl(path, params), {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    const detail = await safeJson(res);
    throw new ApiError(res.status, `GET ${path} failed (${res.status})`, detail);
  }
  return res.json() as Promise<T>;
}

/**
 * REST POST with JSON body.
 */
export async function apiPost<T, B = unknown>(path: string, body: B): Promise<T> {
  const res = await fetch(buildUrl(path), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await safeJson(res);
    throw new ApiError(res.status, `POST ${path} failed (${res.status})`, detail);
  }
  return res.json() as Promise<T>;
}

const safeJson = async (res: Response): Promise<unknown> => {
  try {
    return await res.json();
  } catch {
    return null;
  }
};

export { API_BASE };
