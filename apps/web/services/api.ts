const API_BASE_URL =
    process.env.NEXT_PUBLIC_API_URL ??
    "http://localhost:8000/api";

export function apiRequest(
    path: string,
    options?: RequestInit,
): Promise<Response> {
    return fetch(
        `${API_BASE_URL}${path}`,
        {
            credentials: "include",
            ...options,
        },
    );
}

export async function apiFetch<T>(
    path: string,
    options?: RequestInit
): Promise<T> {
    const response = await apiRequest(
        path,
        {
            headers: {
                "Content-Type": "application/json",
                ...(options?.headers ?? {}),
            },
            ...options,
        },
    );

    if (!response.ok) {
        throw new Error(`API Error ${response.status}`);
    }

    return response.json();
}
