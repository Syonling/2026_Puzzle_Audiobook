import { request } from "./api.js?v=20260826-7";
import { getLanguage, t } from "./i18n.js?v=20260826-7";
import {
    getActiveCanvasContext,
    getActiveCanvasSnapshot,
    replaceActiveCanvasFromAI,
    restoreActiveCanvasSnapshot,
    setCanvasAIPreviewLocked,
} from "./canvas.js?v=20260826-7";
import {
    getActiveAudioSnapshot,
    restoreActiveAudioSnapshot,
    setAudioAIPreviewLocked,
} from "./audio.js?v=20260826-7";
import {
    acceptAIPreview,
    beginAIPreview,
    rejectAIPreview,
} from "./projects.js?v=20260826-7";
import { getEventSessionId } from "./logger.js?v=20260826-7";

const form = document.querySelector("[data-ai-question-form]");
const input = document.querySelector("[data-ai-question-input]");
const submit = document.querySelector("[data-ai-question-submit]");
const presetList = document.querySelector("[data-ai-preset-list]");
const errorMessage = document.querySelector("[data-ai-question-error]");
const BACKGROUND_AUDIO_INSTANCE_ID = "canvas-background";
const answerToast = document.querySelector("[data-ai-answer-toast]");
const answerText = document.querySelector("[data-ai-answer-text]");
const answerTitle = document.querySelector("[data-ai-answer-title]");
const retryButton = document.querySelector("[data-ai-answer-retry]");
const previewActions = document.querySelector("[data-ai-preview-actions]");
const acceptPreviewButton = document.querySelector("[data-ai-preview-accept]");
const rejectPreviewButton = document.querySelector("[data-ai-preview-reject]");

let isSubmitting = false;
let presetRequestRevision = 0;
let answerRequestRevision = 0;
let aiPreviewTransaction = null;

function createSuggestionId() {
    return globalThis.crypto?.randomUUID?.()
        || `suggestion-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function emitAIEvent(eventType, detail = {}) {
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:ai-event", {
        detail: { eventType, ...detail },
    }));
}

function createAudioForAI(audio) {
    return {
        ...audio,
        tracks: Array.isArray(audio?.tracks)
            ? audio.tracks.filter(
                (track) => track?.id !== "narration",
            ).map((track) => ({
                ...track,
                clips: Array.isArray(track?.clips)
                    ? track.clips.map((clip) => {
                        const {
                            base_volume: _baseVolume,
                            is_primary: _isPrimary,
                            ...clipWithoutBaseVolume
                        } = clip;
                        if (clip?.object_instance_id !== BACKGROUND_AUDIO_INSTANCE_ID) {
                            return clipWithoutBaseVolume;
                        }
                        const {
                            volume: _backgroundVolume,
                            ...clipWithoutVolume
                        } = clipWithoutBaseVolume;
                        return clipWithoutVolume;
                    })
                    : [],
            }))
            : [],
    };
}

function publishSuggestedAssets(assetKeys = [], audioSuggestions = []) {
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:asset-suggestions", {
        detail: {
            assetKeys: [...assetKeys],
            audioSuggestions: Array.isArray(audioSuggestions)
                ? audioSuggestions.map((suggestion) => ({ ...suggestion }))
                : [],
        },
    }));
}

function showError(message = "") {
    errorMessage.textContent = message;
    errorMessage.hidden = !message;
}

function hideAnswer() {
    answerToast.hidden = true;
    answerToast.classList.remove("is-error");
}

function showAnswer(answer, { isError = false, showPreviewActions = false } = {}) {
    answerToast.classList.toggle("is-error", isError);
    answerTitle.textContent = isError ? t("ai.error") : t("ai.answer");
    answerText.textContent = answer;
    retryButton.hidden = !isError;
    previewActions.hidden = !showPreviewActions;
    answerToast.hidden = false;
}

function cloneSnapshot(value) {
    return typeof structuredClone === "function"
        ? structuredClone(value)
        : JSON.parse(JSON.stringify(value));
}

function rejectCurrentAIPreview({ closeAnswer = true } = {}) {
    if (!aiPreviewTransaction) {
        if (closeAnswer) hideAnswer();
        return;
    }
    const transaction = aiPreviewTransaction;
    aiPreviewTransaction = null;
    restoreActiveCanvasSnapshot(transaction.originalCanvas);
    restoreActiveAudioSnapshot(transaction.originalAudio);
    setCanvasAIPreviewLocked(false);
    setAudioAIPreviewLocked(false);
    rejectAIPreview(transaction.originalUnsavedState);
    emitAIEvent("ai_rejected", {
        suggestionId: transaction.suggestionId,
        responseToken: transaction.responseToken,
        rejectedItems: transaction.previewCanvas?.objects || [],
    });
    if (closeAnswer) hideAnswer();
}

function acceptCurrentAIPreview() {
    if (!aiPreviewTransaction) return;
    const transaction = aiPreviewTransaction;
    const context = getActiveCanvasContext();
    if (context) {
        window.dispatchEvent(new CustomEvent("puzzle-audiobook:history-commit-snapshot", {
            detail: {
                stepId: context.stepId,
                canvas: transaction.originalCanvas,
                audio: transaction.originalAudio,
                wasUnsaved: transaction.originalUnsavedState,
            },
        }));
    }
    aiPreviewTransaction = null;
    setCanvasAIPreviewLocked(false);
    setAudioAIPreviewLocked(false);
    acceptAIPreview();
    emitAIEvent("ai_accepted", {
        suggestionId: transaction.suggestionId,
        responseToken: transaction.responseToken,
        acceptedCanvas: getActiveCanvasSnapshot(),
        acceptedAudio: getActiveAudioSnapshot(),
        acceptedItems: transaction.previewCanvas?.objects || [],
        rejectedItems: [],
        modifiedItems: [],
    });
    hideAnswer();
}

function beginCanvasAIPreview(aiCanvas, responseToken, suggestionId) {
    const originalCanvas = getActiveCanvasSnapshot();
    const originalAudio = getActiveAudioSnapshot();
    if (!originalCanvas || !originalAudio) throw new Error(t("ai.stepRequired"));

    const originalUnsavedState = beginAIPreview();
    aiPreviewTransaction = {
        originalCanvas: cloneSnapshot(originalCanvas),
        originalAudio: cloneSnapshot(originalAudio),
        originalUnsavedState,
        responseToken,
        suggestionId,
    };
    setCanvasAIPreviewLocked(true);
    setAudioAIPreviewLocked(true);
    try {
        replaceActiveCanvasFromAI(aiCanvas, {
            responseToken,
            suggestionId,
        });
        aiPreviewTransaction.previewCanvas = cloneSnapshot(getActiveCanvasSnapshot());
    } catch (error) {
        rejectCurrentAIPreview({ closeAnswer: false });
        throw error;
    }
}

function formatReasoning(reasoning) {
    return reasoning
        .replace(/([。！？!?])\s*/g, "$1\n")
        .replace(/\.(?=\s+|$)\s*/g, ".\n")
        .trim();
}

function formatAudioSuggestions(suggestions) {
    if (!Array.isArray(suggestions)) return "";
    return suggestions
        .filter((item) => item && typeof item.selected_audio_key === "string")
        .map((item) => {
            const name = item.audio_name || item.selected_audio_key;
            const offset = Number.isFinite(Number(item.start_offset_seconds))
                ? ` · ${Math.max(0, Number(item.start_offset_seconds))}s`
                : "";
            const effects = Array.isArray(item.effect_keys) && item.effect_keys.length
                ? ` · ${item.effect_keys.join(", ")}`
                : "";
            return `🔊 ${item.asset_key}: ${name}${offset}${effects}`;
        })
        .join("\n");
}

function cancelPendingAnswer() {
    answerRequestRevision += 1;
    isSubmitting = false;
    if (submit) {
        submit.disabled = false;
        submit.textContent = t("ai.submit");
    }
}

function createPresetButton(question) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "ai-preset-button";
    button.textContent = question.question;
    button.addEventListener("click", () => {
        input.value = question.question;
        input.focus();
        input.setSelectionRange(input.value.length, input.value.length);
        showError();
    });
    return button;
}

async function loadPresetQuestions() {
    const revision = ++presetRequestRevision;
    try {
        const questions = await request("/ai/getquestions");
        if (revision !== presetRequestRevision) return;
        if (!Array.isArray(questions)) {
            throw new Error(t("ai.presetsInvalid"));
        }

        if (questions.length === 0) {
            const empty = document.createElement("span");
            empty.className = "ai-preset-status";
            empty.textContent = t("ai.presetsEmpty");
            presetList.replaceChildren(empty);
            return;
        }

        presetList.replaceChildren(...questions.map(createPresetButton));
    } catch (error) {
        if (revision !== presetRequestRevision) return;
        const failed = document.createElement("span");
        failed.className = "ai-preset-status is-error";
        failed.textContent = error.message || t("ai.presetsFailed");
        presetList.replaceChildren(failed);
    }
}

form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (isSubmitting) return;
    rejectCurrentAIPreview();
    const userRequest = input.value.trim();

    showError();
    if (!userRequest) {
        showError(t("ai.inputRequired"));
        input.focus();
        return;
    }

    const canvasContext = getActiveCanvasContext();
    const canvas = getActiveCanvasSnapshot();
    const audio = getActiveAudioSnapshot();
    if (
        !canvasContext
        || !Number.isInteger(canvasContext.storyId)
        || !Number.isInteger(canvasContext.stepOrder)
        || !canvas
        || !audio
    ) {
        showError(t("ai.stepRequired"));
        return;
    }

    isSubmitting = true;
    const revision = ++answerRequestRevision;
    const suggestionId = createSuggestionId();
    const languageAtSubmit = getLanguage();
    const stepIdAtSubmit = canvasContext.stepId;
    submit.disabled = true;
    submit.textContent = t("ai.thinking");
    hideAnswer();
    publishSuggestedAssets();
    emitAIEvent("ai_request", {
        suggestionId,
        requestTimestamp: new Date().toISOString(),
        pageId: canvasContext.stepId,
        userRequest,
    });

    try {
        const result = await request("/ai/getanswer", {
            method: "POST",
            headers: {
                "X-Suggestion-ID": suggestionId,
                "X-Session-ID": getEventSessionId(),
            },
            body: JSON.stringify({
                user_request: userRequest,
                story_id: canvasContext.storyId,
                step_order: canvasContext.stepOrder,
                canvas,
                audio: createAudioForAI(audio),
            }),
        });
        const latestContext = getActiveCanvasContext();
        if (
            revision !== answerRequestRevision
            || getLanguage() !== languageAtSubmit
            || latestContext?.storyId !== canvasContext.storyId
            || latestContext?.stepId !== stepIdAtSubmit
        ) return;
        emitAIEvent("ai_result_received", {
            suggestionId,
            responseTimestamp: new Date().toISOString(),
            mode: result.mode,
            output: result.output,
        });
        if (result.mode === "suggestion") {
            const iconKeys = result.output?.icon_keys;
            if (
                !Array.isArray(iconKeys)
                || !iconKeys.every((assetKey) => typeof assetKey === "string")
            ) {
                throw new Error(t("ai.suggestionInvalid"));
            }

            const backgroundKey = result.output?.background_key;
            if (backgroundKey !== null && backgroundKey !== undefined
                && typeof backgroundKey !== "string") {
                throw new Error(t("ai.suggestionInvalid"));
            }
            const suggestedKeys = [...new Set([
                ...iconKeys,
                ...(backgroundKey ? [backgroundKey] : []),
            ])];
            publishSuggestedAssets(suggestedKeys, result.output?.audio_suggestions);
            const reasoning = typeof result.output?.reasoning === "string"
                ? result.output.reasoning.trim()
                : "";
            const audioSuggestions = formatAudioSuggestions(
                result.output?.audio_suggestions,
            );
            const explanation = reasoning ? formatReasoning(reasoning) : (
                suggestedKeys.length > 0
                    ? t("ai.suggestions", { count: suggestedKeys.length })
                    : t("ai.noSuggestions")
            );
            showAnswer(
                [explanation, audioSuggestions].filter(Boolean).join("\n\n"),
            );
            emitAIEvent("ai_result_displayed", {
                suggestionId,
                displayTimestamp: new Date().toISOString(),
                mode: result.mode,
                suggestedItems: suggestedKeys,
                suggestedAudio: result.output?.audio_suggestions || [],
            });
        } else if (result.mode === "generate") {
            const responseToken =
                `${languageAtSubmit}:${canvasContext.storyId}:${stepIdAtSubmit}:${revision}`;
            beginCanvasAIPreview(result.output, responseToken, suggestionId);
            publishSuggestedAssets();
            const reasoning = typeof result.output?.reasoning === "string"
                ? result.output.reasoning.trim()
                : "";
            showAnswer(
                reasoning ? formatReasoning(reasoning) : t("ai.generated"),
                { showPreviewActions: true },
            );
            emitAIEvent("ai_result_displayed", {
                suggestionId,
                displayTimestamp: new Date().toISOString(),
                mode: result.mode,
                suggestedItems: result.output?.objects || [],
                suggestedAudio: result.output?.audio_suggestions || [],
            });
        } else {
            throw new Error(t("ai.unknownMode"));
        }
    } catch (error) {
        if (revision !== answerRequestRevision) return;
        emitAIEvent("ai_request_failed", {
            suggestionId,
            failedTimestamp: new Date().toISOString(),
            message: error.message || null,
        });
        showAnswer(error.message || t("ai.failed"), { isError: true });
    } finally {
        if (revision !== answerRequestRevision) return;
        isSubmitting = false;
        submit.disabled = false;
        submit.textContent = t("ai.submit");
    }
});

document.querySelector("[data-ai-answer-close]")?.addEventListener("click", () => {
    if (aiPreviewTransaction) rejectCurrentAIPreview();
    else hideAnswer();
});
retryButton?.addEventListener("click", () => form?.requestSubmit());
acceptPreviewButton?.addEventListener("click", acceptCurrentAIPreview);
rejectPreviewButton?.addEventListener("click", () => rejectCurrentAIPreview());

window.addEventListener("puzzle-audiobook:reset", () => {
    aiPreviewTransaction = null;
    setCanvasAIPreviewLocked(false);
    setAudioAIPreviewLocked(false);
    cancelPendingAnswer();
    form?.reset();
    showError();
    hideAnswer();
    publishSuggestedAssets();
});
window.addEventListener("puzzle-audiobook:language-change", () => {
    rejectCurrentAIPreview();
    cancelPendingAnswer();
    showError();
    hideAnswer();
    loadPresetQuestions();
});
window.addEventListener("puzzle-audiobook:before-context-switch", () => {
    rejectCurrentAIPreview();
});
window.addEventListener("puzzle-audiobook:step-change", () => {
    cancelPendingAnswer();
    if (input) input.value = "";
    showError();
    publishSuggestedAssets();
    hideAnswer();
});
window.addEventListener("puzzle-audiobook:new-story", () => {
    cancelPendingAnswer();
    hideAnswer();
});

loadPresetQuestions();
