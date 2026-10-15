/**
 * Cliente HTTP para el sistema LIS Laboratorio Clínico.
 * Implementa estrictamente PROMPT_FASE_1.md §5 y §9:
 * - Token JWT almacenado EXCLUSIVAMENTE en memoria (sin almacenamiento persistente en cliente).
 * - Envío automático de cabecera X-LIS-Client: web en refresh y logout.
 * - Credenciales (cookies) en include para la cookie refresh SameSite=Strict.
 * - Reintento automático ante 401 SESION_EXPIRADA (un intento con /api/auth/refresh).
 * - Manejo de 403 DEBE_CAMBIAR_PASSWORD redirigiendo a /cambiar-password.
 */

export interface ErrorResponse {
  codigo: string;
  mensaje: string;
  minutos_restantes?: number;
  [key: string]: unknown;
}

export class ApiError extends Error {
  public status: number;
  public codigo: string;
  public extra?: Record<string, unknown>;

  constructor(status: number, codigo: string, mensaje: string, extra?: Record<string, unknown>) {
    super(mensaje);
    this.name = "ApiError";
    this.status = status;
    this.codigo = codigo;
    this.extra = extra;
  }
}

// Token de acceso estrictamente en memoria (§5, §9)
let inMemoryAccessToken: string | null = null;

// Callbacks para eventos globales del ciclo de sesión
let onSessionExpiredCallback: (() => void) | null = null;
let onMustChangePasswordCallback: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  inMemoryAccessToken = token;
}

export function getAccessToken(): string | null {
  return inMemoryAccessToken;
}

export function setOnSessionExpired(callback: () => void): void {
  onSessionExpiredCallback = callback;
}

export function setOnMustChangePassword(callback: () => void): void {
  onMustChangePasswordCallback = callback;
}

interface RequestOptions extends RequestInit {
  retryOnSessionExpired?: boolean;
}

export async function apiClient<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { retryOnSessionExpired = true, ...fetchOptions } = options;

  const headers = new Headers(fetchOptions.headers || {});

  // Adjuntar cabecera CSRF requerida en refresh y logout (§5)
  if (endpoint.includes("/api/auth/refresh") || endpoint.includes("/api/auth/logout")) {
    headers.set("X-LIS-Client", "web");
  }

  // Adjuntar Bearer token si existe en memoria
  if (inMemoryAccessToken && !headers.has("Authorization")) {
    headers.set("Authorization", `Bearer ${inMemoryAccessToken}`);
  }

  if (!headers.has("Content-Type") && !(fetchOptions.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(endpoint, {
    ...fetchOptions,
    headers,
    credentials: "include", // Enviar cookie httpOnly refresh_token
  });

  // Manejo de respuestas 204 No Content
  if (response.status === 204) {
    return undefined as unknown as T;
  }

  if (!response.ok) {
    let errorData: ErrorResponse = {
      codigo: "ERROR_DESCONOCIDO",
      mensaje: "Ocurrió un error en el servidor.",
    };

    try {
      errorData = await response.json();
    } catch {
      errorData.mensaje = response.statusText || `Error HTTP ${response.status}`;
    }

    // Interceptor: 403 DEBE_CAMBIAR_PASSWORD (§9)
    if (response.status === 403 && errorData.codigo === "DEBE_CAMBIAR_PASSWORD") {
      if (onMustChangePasswordCallback) {
        onMustChangePasswordCallback();
      }
      throw new ApiError(response.status, errorData.codigo, errorData.mensaje, errorData);
    }

    // Interceptor: 401 SESION_EXPIRADA en petición normal -> reintentar un refresh (§9)
    if (
      response.status === 401 &&
      errorData.codigo === "SESION_EXPIRADA" &&
      retryOnSessionExpired &&
      inMemoryAccessToken &&
      !endpoint.includes("/api/auth/refresh") &&
      !endpoint.includes("/api/auth/login")
    ) {
      try {
        const refreshResponse = await fetch("/api/auth/refresh", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-LIS-Client": "web",
          },
          credentials: "include",
        });

        if (refreshResponse.ok) {
          const refreshData = await refreshResponse.json();
          setAccessToken(refreshData.access_token);
          // Reintentar la petición original UNA sola vez con el nuevo token
          return apiClient<T>(endpoint, {
            ...options,
            retryOnSessionExpired: false,
          });
        }
      } catch {
        // Falló el refresh
      }

      // Si el refresh falló, limpiar sesión y disparar expiración
      setAccessToken(null);
      if (onSessionExpiredCallback) {
        onSessionExpiredCallback();
      }
    }

    throw new ApiError(response.status, errorData.codigo, errorData.mensaje, errorData);
  }

  return response.json() as Promise<T>;
}
