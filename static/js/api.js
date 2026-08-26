import { getLanguage, t } from "./i18n.js?v=20260826-7";

export class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.name = "ApiError";
        this.status = status;
    }
}

export async function request(path, options = {}) {
    const requiresLanguage = /^\/(ai|assets|stories)(?:[/?]|$)/.test(path);
    const response = await fetch(path, {
        credentials: "same-origin",
        ...options,
        headers: {
            "Content-Type": "application/json",
            ...(requiresLanguage ? { "X-Language": getLanguage() } : {}),
            ...options.headers,
        },
    });

    let data = {};
    try {
        data = await response.json();
    } catch {
        // 非 JSON 错误将使用统一提示。
    }

    if (!response.ok) {
        const detail = typeof data.detail === "string"
            ? data.detail
            : t("request.failed");
        throw new ApiError(detail, response.status);
    }

    return data;
}
