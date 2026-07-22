const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL ??
    "http://127.0.0.1:8000/api";

export async function apiFetch<T>(
    path: string,
    options?: RequestInit
): Promise<T> {
    const response = await fetch(
        `${API_BASE_URL}${path}`,
        {
            headers: {
                "Content-Type": "application/json",
                ...(options?.headers ?? {}),
            },
            ...options,
        }
    );

    if (!response.ok) {
        throw new Error(`API Error ${response.status}`);
    }

    return response.json();
}