import { request } from "./api.js?v=20260826-2";
import { t } from "./i18n.js?v=20260826-2";

const SESSION_KEY = "puzzleAudiobook.user";
const APP_STORAGE_PREFIX = "puzzleAudiobook.";
let authMode = "login";
let authRevision = 0;

function getCurrentUser() {
    try {
        const user = JSON.parse(localStorage.getItem(SESSION_KEY));
        if (
            !user
            || !Number.isInteger(user.id)
            || typeof user.username !== "string"
            || !user.username
        ) {
            localStorage.removeItem(SESSION_KEY);
            return null;
        }
        return user;
    } catch {
        localStorage.removeItem(SESSION_KEY);
        return null;
    }
}

function saveCurrentUser(user) {
    authRevision += 1;
    localStorage.setItem(SESSION_KEY, JSON.stringify(user));
}

function clearAppState() {
    authRevision += 1;
    Object.keys(localStorage)
        .filter((key) => key.startsWith(APP_STORAGE_PREFIX))
        .forEach((key) => localStorage.removeItem(key));
    Object.keys(sessionStorage)
        .filter((key) => key.startsWith(APP_STORAGE_PREFIX))
        .forEach((key) => sessionStorage.removeItem(key));
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:reset"));
}

function setMode(mode) {
    authMode = mode;
    const isLogin = mode === "login";

    document.querySelectorAll("[data-auth-mode]").forEach((button) => {
        button.setAttribute("aria-selected", String(button.dataset.authMode === mode));
    });
    document.querySelectorAll("[data-auth-title]").forEach((title) => {
        title.textContent = isLogin ? t("auth.welcome") : t("auth.create");
    });
    document.querySelectorAll("[data-auth-intro]").forEach((intro) => {
        intro.textContent = isLogin
            ? t("auth.loginIntro")
            : t("auth.registerIntro");
    });
    document.querySelectorAll("[data-auth-submit]").forEach((button) => {
        button.textContent = isLogin ? t("auth.login") : t("auth.register");
    });
    document.querySelectorAll('input[name="password"]').forEach((input) => {
        input.autocomplete = isLogin ? "current-password" : "new-password";
    });
    clearErrors();
}

function clearErrors() {
    document.querySelectorAll("[data-auth-error]").forEach((error) => {
        error.textContent = "";
        error.hidden = true;
    });
}

function showError(form, message) {
    const error = form.querySelector("[data-auth-error]");
    error.textContent = message;
    error.hidden = false;
}

function localizeAuthError(error) {
    if (error?.status === 409 || error?.message === "Username already exist") {
        return t("auth.usernameExists");
    }
    if (error?.status === 401 || error?.message === "Wrong username or password") {
        return t("auth.wrongCredentials");
    }
    return error?.message || t("request.failed");
}

function updateAccountView() {
    const user = getCurrentUser();
    const account = document.querySelector("[data-account]");
    if (!account) return;

    const button = account.querySelector("[data-account-button]");
    const initial = account.querySelector("[data-account-initial]");
    const name = account.querySelector("[data-account-name]");
    const label = account.querySelector("[data-account-label]");
    const menu = account.querySelector("[data-account-menu]");

    account.classList.toggle("is-signed-in", Boolean(user));
    button.setAttribute(
        "aria-label",
        user ? t("account.userMenu", { username: user.username }) : t("account.loginOrRegister"),
    );

    if (user) {
        initial.textContent = user.username.slice(0, 1).toUpperCase();
        initial.hidden = false;
        name.textContent = user.username;
        label.textContent = user.username;
        label.hidden = false;
    } else {
        initial.hidden = true;
        name.textContent = "";
        label.textContent = "";
        label.hidden = true;
        menu.hidden = true;
        button.setAttribute("aria-expanded", "false");
    }
}

async function syncSession() {
    const accountButton = document.querySelector("[data-account-button]");
    const revisionAtStart = authRevision;

    try {
        const result = await request("/auth/me");
        saveCurrentUser(result.user);
        updateAccountView();

        // 已登录用户直接离开独立登录页。
        if (!document.querySelector("[data-account]")) {
            window.location.replace("/");
        }
    } catch (error) {
        if (error.status === 401 && authRevision === revisionAtStart) {
            localStorage.removeItem(SESSION_KEY);
            updateAccountView();
        }
        // 网络异常时保留最近一次用户显示信息，待下一次请求再确认。
    } finally {
        if (accountButton) accountButton.disabled = false;
    }
}

async function handleSubmit(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const submit = form.querySelector("[data-auth-submit]");
    const formData = new FormData(form);
    const username = String(formData.get("username") || "").trim();
    const password = String(formData.get("password") || "");

    clearErrors();
    if (!username || !password) {
        showError(form, t("auth.required"));
        return;
    }

    submit.disabled = true;
    submit.textContent = authMode === "login" ? t("auth.loggingIn") : t("auth.registering");

    try {
        let result = await request(`/auth/${authMode}`, {
            method: "POST",
            body: JSON.stringify({ username, password }),
        });

        // 注册接口只创建用户；随后登录以取得 HttpOnly Session Cookie。
        if (authMode === "register") {
            result = await request("/auth/login", {
                method: "POST",
                body: JSON.stringify({ username, password }),
            });
        }

        saveCurrentUser(result.user);
        updateAccountView();
        window.dispatchEvent(new CustomEvent("puzzle-audiobook:authenticated", {
            detail: { user: { ...result.user } },
        }));
        form.reset();

        const dialog = document.querySelector("[data-auth-dialog]");
        if (dialog?.open) {
            dialog.close();
        } else {
            window.location.href = "/";
        }
    } catch (error) {
        showError(form, localizeAuthError(error));
    } finally {
        submit.disabled = false;
        submit.textContent = authMode === "login" ? t("auth.login") : t("auth.register");
    }
}

document.querySelectorAll("[data-auth-mode]").forEach((button) => {
    button.addEventListener("click", () => setMode(button.dataset.authMode));
});

document.querySelectorAll("[data-auth-form]").forEach((form) => {
    form.addEventListener("submit", handleSubmit);
});

const dialog = document.querySelector("[data-auth-dialog]");
const accountButton = document.querySelector("[data-account-button]");
const accountMenu = document.querySelector("[data-account-menu]");

accountButton?.addEventListener("click", () => {
    if (!getCurrentUser()) {
        setMode("login");
        dialog.showModal();
        dialog.querySelector('input[name="username"]').focus();
        return;
    }

    const willOpen = accountMenu.hidden;
    accountMenu.hidden = !willOpen;
    accountButton.setAttribute("aria-expanded", String(willOpen));
});

document.querySelector("[data-auth-close]")?.addEventListener("click", () => dialog.close());
dialog?.addEventListener("click", (event) => {
    if (event.target === dialog) dialog.close();
});

document.querySelector("[data-logout]")?.addEventListener("click", async (event) => {
    const logoutButton = event.currentTarget;
    logoutButton.disabled = true;
    logoutButton.textContent = t("account.logoutPending");

    try {
        await request("/auth/logout", { method: "POST" });
    } catch (error) {
        // 即使网络异常，也清除本机数据，避免用户信息继续留在当前页面。
        console.error("Logout request failed:", error);
    } finally {
        clearAppState();
        window.location.replace("/");
    }
});

document.addEventListener("click", (event) => {
    const account = document.querySelector("[data-account]");
    if (account && !account.contains(event.target) && accountMenu) {
        accountMenu.hidden = true;
        accountButton.setAttribute("aria-expanded", "false");
    }
});

window.addEventListener("storage", (event) => {
    if (event.key === SESSION_KEY) updateAccountView();
});
window.addEventListener("puzzle-audiobook:language-change", () => {
    setMode(authMode);
    updateAccountView();
});

updateAccountView();
setMode("login");
syncSession();
