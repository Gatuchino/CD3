/**
 * DocuBot — Configuración MSAL con soporte modo demo.
 * En DEMO_MODE=true salta la autenticación Azure AD B2C.
 */
export const IS_DEMO = import.meta.env.VITE_DEMO_MODE === "true";

export const msalConfig = {
  auth: {
    clientId: import.meta.env.VITE_AZURE_CLIENT_ID ?? "demo",
    authority: import.meta.env.VITE_AZURE_AUTHORITY ?? "https://login.microsoftonline.com/demo",
    redirectUri: import.meta.env.VITE_AZURE_REDIRECT_URI ?? "http://localhost:5173",
    knownAuthorities: [],
  },
  cache: {
    cacheLocation: "sessionStorage" as const,
    storeAuthStateInCookie: false,
  },
};

export const loginRequest = {
  scopes: ["openid", "profile"],
};

export const DEMO_USER = {
  name: "Usuario Demo",
  email: "demo@aurenza.cl",
  tenantId: "demo-tenant",
  projectId: import.meta.env.VITE_DEMO_PROJECT_ID ?? "demo-project-id",
};
