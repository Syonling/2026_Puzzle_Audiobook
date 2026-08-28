import { t } from "./i18n.js?v=20260829-4";

const STORAGE_KEY = "puzzleAudiobook.countdown";
const root = document.querySelector("[data-countdown]");
const toggle = root?.querySelector("[data-countdown-toggle]");
const panel = root?.querySelector("[data-countdown-panel]");
const output = root?.querySelector("[data-countdown-output]");
const minutesInput = root?.querySelector("[data-countdown-minutes]");
const secondsInput = root?.querySelector("[data-countdown-seconds]");
const startButton = root?.querySelector("[data-countdown-start]");
const pauseButton = root?.querySelector("[data-countdown-pause]");
const resetButton = root?.querySelector("[data-countdown-reset]");

let configuredSeconds = 600;
let remainingMilliseconds = configuredSeconds * 1000;
let endAt = null;
let intervalId = null;

function emit(eventType, data = {}) {
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:timer-event", {
        detail: { eventType, ...data },
    }));
}

function readState() {
    try {
        const state = JSON.parse(sessionStorage.getItem(STORAGE_KEY));
        if (!state || typeof state !== "object") return;
        configuredSeconds = Math.max(1, Number(state.configuredSeconds) || 600);
        remainingMilliseconds = Math.max(
            0,
            Number(state.remainingMilliseconds) || configuredSeconds * 1000,
        );
        endAt = state.endAt !== null
            && state.endAt !== undefined
            && Number.isFinite(Number(state.endAt))
            ? Number(state.endAt)
            : null;
        if (endAt !== null) remainingMilliseconds = Math.max(0, endAt - Date.now());
    } catch {
        sessionStorage.removeItem(STORAGE_KEY);
    }
}

function saveState() {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({
        configuredSeconds,
        remainingMilliseconds,
        endAt,
    }));
}

function formatTime(milliseconds) {
    const totalSeconds = Math.max(0, Math.ceil(milliseconds / 1000));
    const minutes = Math.floor(totalSeconds / 60);
    const seconds = totalSeconds % 60;
    return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function updateInputs() {
    if (minutesInput) minutesInput.value = String(Math.floor(configuredSeconds / 60));
    if (secondsInput) secondsInput.value = String(configuredSeconds % 60);
}

function stopInterval() {
    if (intervalId !== null) window.clearInterval(intervalId);
    intervalId = null;
}

function render() {
    if (!root) return;
    if (endAt !== null) remainingMilliseconds = Math.max(0, endAt - Date.now());
    if (output) output.textContent = formatTime(remainingMilliseconds);
    const running = endAt !== null && remainingMilliseconds > 0;
    const finished = remainingMilliseconds <= 0;
    root.classList.toggle("is-running", running);
    root.classList.toggle("is-finished", finished);
    if (startButton) {
        startButton.textContent = remainingMilliseconds < configuredSeconds * 1000
            ? t("timer.continue")
            : t("timer.start");
        startButton.disabled = running || finished;
    }
    if (pauseButton) pauseButton.disabled = !running;
    if (toggle) toggle.title = finished ? t("timer.finished") : t("timer.open");

    if (finished && endAt !== null) {
        endAt = null;
        stopInterval();
        saveState();
        emit("timer_finished", { configured_seconds: configuredSeconds });
    }
}

function tick() {
    render();
    saveState();
}

function readConfiguredDuration() {
    const minutes = Math.max(0, Math.min(999, Number(minutesInput?.value) || 0));
    const seconds = Math.max(0, Math.min(59, Number(secondsInput?.value) || 0));
    return Math.max(1, Math.floor(minutes * 60 + seconds));
}

function start() {
    if (endAt !== null) return;
    if (remainingMilliseconds <= 0 || remainingMilliseconds === configuredSeconds * 1000) {
        configuredSeconds = readConfiguredDuration();
        remainingMilliseconds = configuredSeconds * 1000;
    }
    endAt = Date.now() + remainingMilliseconds;
    stopInterval();
    intervalId = window.setInterval(tick, 250);
    emit("timer_started", {
        configured_seconds: configuredSeconds,
        remaining_seconds: Math.ceil(remainingMilliseconds / 1000),
    });
    tick();
}

function pause() {
    if (endAt === null) return;
    remainingMilliseconds = Math.max(0, endAt - Date.now());
    endAt = null;
    stopInterval();
    emit("timer_paused", {
        remaining_seconds: Math.ceil(remainingMilliseconds / 1000),
    });
    tick();
}

function reset() {
    stopInterval();
    endAt = null;
    configuredSeconds = readConfiguredDuration();
    remainingMilliseconds = configuredSeconds * 1000;
    emit("timer_reset", { configured_seconds: configuredSeconds });
    tick();
}

readState();
updateInputs();
render();
if (endAt !== null) intervalId = window.setInterval(tick, 250);

toggle?.addEventListener("click", () => {
    const opening = panel.hidden;
    panel.hidden = !opening;
    toggle.setAttribute("aria-expanded", String(opening));
});
startButton?.addEventListener("click", start);
pauseButton?.addEventListener("click", pause);
resetButton?.addEventListener("click", reset);
[minutesInput, secondsInput].filter(Boolean).forEach((input) => {
    input.addEventListener("change", () => {
        if (endAt !== null) return;
        configuredSeconds = readConfiguredDuration();
        remainingMilliseconds = configuredSeconds * 1000;
        tick();
    });
});
document.addEventListener("click", (event) => {
    if (!root?.contains(event.target) && panel) {
        panel.hidden = true;
        toggle?.setAttribute("aria-expanded", "false");
    }
});
window.addEventListener("puzzle-audiobook:language-change", render);
window.addEventListener("pagehide", saveState);
