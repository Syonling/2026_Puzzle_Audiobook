import { request } from "./api.js?v=20260826-2";
import { t } from "./i18n.js?v=20260826-2";
import {
    activateDraftCanvas,
    clearCanvasCache,
    discardActiveCanvasChanges,
    getActiveCanvasContext,
    getActiveCanvasSnapshot,
    restoreActiveCanvasSnapshot,
    restoreRemoteCanvas,
    showRemoteCanvasLoading,
    storeRemoteCanvas,
} from "./canvas.js?v=20260826-2";
import {
    activateDraftAudio,
    clearAudioCache,
    discardActiveAudioChanges,
    getActiveAudioSnapshot,
    restoreActiveAudioSnapshot,
    restoreRemoteAudio,
    showRemoteAudioLoading,
    storeRemoteAudio,
    syncAudioToCanvasObjects,
} from "./audio.js?v=20260826-2";

const getDefaultProjectTitle = () => t("project.unnamed");
const saveButton = document.querySelector("[data-save-project]");
const saveStatus = document.querySelector("[data-save-status]");
const unsavedDialog = document.querySelector("[data-unsaved-dialog]");
const undoButton = document.querySelector("[data-history-undo]");
const redoButton = document.querySelector("[data-history-redo]");

let projectId = null;
let currentStepContext = null;
let isSaving = false;
let isCanvasLoading = false;
let isProjectResolving = false;
let projectLookupFailed = false;
let canvasLoadRevision = 0;
let projectRevision = 0;
let projectLookupRevision = 0;
let activeStoryContext = null;
let hasUnsavedChanges = false;
// { type: "step", storyId, stepOrder } 或 { type: "story", storyId }
let pendingSwitchRequest = null;
let changedDuringSave = false;
let saveInFlightStepId = null;
let saveStatusDescriptor = { key: "canvas.unsaved", values: {}, state: "" };
let isAIPreviewActive = false;
let undoSnapshot = null;
let redoSnapshot = null;
let pendingHistorySnapshot = null;
let isRestoringHistory = false;

function cloneHistoryValue(value) {
    return typeof structuredClone === "function"
        ? structuredClone(value)
        : JSON.parse(JSON.stringify(value));
}

function captureHistorySnapshot() {
    const canvas = getActiveCanvasSnapshot();
    const audio = getActiveAudioSnapshot();
    const context = getActiveCanvasContext();
    if (!canvas || !audio || !context || context.stepId !== currentStepContext?.stepId) return null;
    return {
        stepId: context.stepId,
        canvas: cloneHistoryValue(canvas),
        audio: cloneHistoryValue(audio),
        wasUnsaved: hasUnsavedChanges,
    };
}

function updateHistoryButtons() {
    const blocked = isCanvasLoading || isProjectResolving || isAIPreviewActive || !currentStepContext;
    if (undoButton) undoButton.disabled = blocked || !undoSnapshot;
    if (redoButton) redoButton.disabled = blocked || !redoSnapshot;
}

function clearHistory() {
    undoSnapshot = null;
    redoSnapshot = null;
    pendingHistorySnapshot = null;
    updateHistoryButtons();
}

function commitPendingHistory() {
    if (!pendingHistorySnapshot || isRestoringHistory || isAIPreviewActive) return;
    undoSnapshot = pendingHistorySnapshot;
    pendingHistorySnapshot = null;
    redoSnapshot = null;
    updateHistoryButtons();
}

function restoreHistorySnapshot(snapshot) {
    if (!snapshot || snapshot.stepId !== currentStepContext?.stepId) return false;
    isRestoringHistory = true;
    const canvasRestored = restoreActiveCanvasSnapshot(snapshot.canvas);
    const audioRestored = restoreActiveAudioSnapshot(snapshot.audio);
    isRestoringHistory = false;
    if (!canvasRestored || !audioRestored) return false;
    hasUnsavedChanges = Boolean(snapshot.wasUnsaved);
    if (hasUnsavedChanges) setTranslatedSaveStatus("project.changed");
    else if (projectId === null) setTranslatedSaveStatus("canvas.unsaved");
    else setTranslatedSaveStatus("project.loaded", {}, "success");
    return true;
}

function undoLastChange() {
    if (!undoSnapshot || isAIPreviewActive) return;
    const current = captureHistorySnapshot();
    const target = undoSnapshot;
    if (!current || !restoreHistorySnapshot(target)) return;
    redoSnapshot = current;
    undoSnapshot = null;
    pendingHistorySnapshot = null;
    updateHistoryButtons();
}

function redoLastChange() {
    if (!redoSnapshot || isAIPreviewActive) return;
    const current = captureHistorySnapshot();
    const target = redoSnapshot;
    if (!current || !restoreHistorySnapshot(target)) return;
    undoSnapshot = current;
    redoSnapshot = null;
    pendingHistorySnapshot = null;
    updateHistoryButtons();
}

function setSaveStatus(message, state = "") {
    saveStatusDescriptor = { message, state };
    if (!saveStatus) return;
    saveStatus.textContent = message;
    saveStatus.dataset.state = state;
}

function setTranslatedSaveStatus(key, values = {}, state = "") {
    saveStatusDescriptor = { key, values: { ...values }, state };
    if (!saveStatus) return;
    saveStatus.textContent = t(key, values);
    saveStatus.dataset.state = state;
}

function refreshSaveStatusTranslation() {
    if (saveStatusDescriptor.key) {
        const { key, values, state } = saveStatusDescriptor;
        if (saveStatus) {
            saveStatus.textContent = t(key, values);
            saveStatus.dataset.state = state;
        }
    }
}

function updateSaveButton() {
    if (!saveButton) return;
    saveButton.disabled =
        isSaving
        || isCanvasLoading
        || isProjectResolving
        || isAIPreviewActive
        || projectLookupFailed
        || currentStepContext === null;
    saveButton.textContent = isSaving ? t("canvas.saving") : t("canvas.save");
    updateHistoryButtons();
}

function getProjectTitle() {
    return document.querySelector(".project-name")?.textContent.trim()
        || getDefaultProjectTitle();
}

function setStepButtonsDisabled(disabled) {
    document.querySelectorAll("[data-step-order]").forEach((button) => {
        button.disabled = disabled;
    });
}

function selectStoryStep(storyId, steps, preferredStepOrder) {
    if (steps.length === 0) {
        currentStepContext = null;
        updateSaveButton();
        return;
    }

    const preferredStep = steps.find(
        (step) => step.step_order === preferredStepOrder,
    ) || steps[0];

    window.dispatchEvent(new CustomEvent("puzzle-audiobook:select-step", {
        detail: {
            storyId,
            stepOrder: preferredStep.step_order,
        },
    }));
}

function performStepSelection(requestedStep, announceSwitch = true) {
    if (announceSwitch) {
        window.dispatchEvent(new CustomEvent("puzzle-audiobook:before-context-switch"));
    }
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:select-step", {
        detail: {
            storyId: requestedStep.storyId,
            stepOrder: requestedStep.stepOrder,
        },
    }));
}

function performPendingSwitch(request, announceSwitch = true) {
    if (request.type === "story") {
        if (announceSwitch) {
            window.dispatchEvent(new CustomEvent("puzzle-audiobook:before-context-switch"));
        }
        window.dispatchEvent(new CustomEvent("puzzle-audiobook:select-story", {
            detail: { storyId: request.storyId },
        }));
        return;
    }
    performStepSelection(request, announceSwitch);
}

function requestStepSelection(requestedStep) {
    const isCurrentStep =
        requestedStep.storyId === currentStepContext?.storyId
        && requestedStep.stepOrder === currentStepContext?.stepOrder;
    if (isCurrentStep) return;

    if (requestedStep.storyId !== currentStepContext?.storyId) {
        performStepSelection(requestedStep);
        return;
    }

    if (!hasUnsavedChanges) {
        performStepSelection(requestedStep);
        return;
    }

    pendingSwitchRequest = { type: "step", ...requestedStep };
    unsavedDialog.showModal();
}

function requestStorySelection(storyId) {
    if (!hasUnsavedChanges) {
        performPendingSwitch({ type: "story", storyId });
        return;
    }

    pendingSwitchRequest = { type: "story", storyId };
    unsavedDialog.showModal();
}

async function resolveProjectForStory(storyContext) {
    const lookupRevision = ++projectLookupRevision;
    const projectRevisionAtStart = projectRevision;

    projectId = null;
    currentStepContext = null;
    isProjectResolving = true;
    projectLookupFailed = false;
    isCanvasLoading = false;
    canvasLoadRevision += 1;
    clearCanvasCache();
    setStepButtonsDisabled(true);
    setTranslatedSaveStatus("project.finding");
    updateSaveButton();

    try {
        // 后端当前实际路由为 GET /projects/{story_id}。
        const result = await request(`/projects/${storyContext.storyId}`);
        const isStillCurrent =
            lookupRevision === projectLookupRevision
            && projectRevisionAtStart === projectRevision;
        if (!isStillCurrent) return;

        if (
            !Number.isInteger(result.id)
            || result.story_id !== storyContext.storyId
            || !Number.isInteger(result.current_step)
        ) {
            throw new Error(t("project.invalid"));
        }

        projectId = result.id;
        const projectName = document.querySelector(".project-name");
        if (projectName) projectName.textContent = result.title || getDefaultProjectTitle();
        isProjectResolving = false;
        setStepButtonsDisabled(false);
        setTranslatedSaveStatus("project.found", { id: projectId }, "success");
        updateSaveButton();
        selectStoryStep(
            storyContext.storyId,
            storyContext.steps,
            null,
        );
    } catch (error) {
        const isStillCurrent =
            lookupRevision === projectLookupRevision
            && projectRevisionAtStart === projectRevision;
        if (!isStillCurrent) return;

        projectId = null;
        isProjectResolving = false;
        setStepButtonsDisabled(false);

        const projectName = document.querySelector(".project-name");
        if (projectName) projectName.textContent = getDefaultProjectTitle();

        if (error.status === 404) {
            projectLookupFailed = false;
            setTranslatedSaveStatus("project.notCreated");
        } else {
            // 非 404 不能解释成“没有项目”，否则可能错误地创建重复作品。
            projectLookupFailed = true;
            if (error.message) setSaveStatus(error.message, "error");
            else setTranslatedSaveStatus("project.lookupFailed", {}, "error");
        }

        selectStoryStep(storyContext.storyId, storyContext.steps, null);
        updateSaveButton();
    }
}

async function loadStepCanvas(context) {
    const requestedProjectId = projectId;
    const requestedStepId = context.stepId;
    const revision = ++canvasLoadRevision;

    isCanvasLoading = true;
    updateSaveButton();
    showRemoteCanvasLoading(context, requestedProjectId);
    showRemoteAudioLoading(context, requestedProjectId);
    setTranslatedSaveStatus("project.loading");

    try {
        const result = await request(
            `/projects/${requestedProjectId}/steps/${requestedStepId}/canvas`,
        );

        const isStillCurrent =
            revision === canvasLoadRevision
            && projectId === requestedProjectId
            && currentStepContext?.stepId === requestedStepId
            && result.project_id === requestedProjectId
            && result.story_step_id === requestedStepId;

        if (!isStillCurrent) return;

        restoreRemoteCanvas(context, requestedProjectId, result.canvas);
        restoreRemoteAudio(context, requestedProjectId, result.audio);
        syncAudioToCanvasObjects(
            result.canvas?.objects,
            document.querySelector("[data-canvas-paper]")?.getBoundingClientRect().width,
        );
        clearHistory();
        hasUnsavedChanges = false;
        setTranslatedSaveStatus("project.loaded", {}, "success");
    } catch (error) {
        const isStillCurrent =
            revision === canvasLoadRevision
            && projectId === requestedProjectId
            && currentStepContext?.stepId === requestedStepId;
        if (!isStillCurrent) return;

        // 请求失败时不伪造服务器空画布，保留明确的失败状态。
        if (error.message) setSaveStatus(error.message, "error");
        else setTranslatedSaveStatus("project.loadFailed", {}, "error");
    } finally {
        if (revision === canvasLoadRevision) {
            isCanvasLoading = false;
            updateSaveButton();
        }
    }
}

async function handleStepChange(context) {
    currentStepContext = { ...context };
    updateSaveButton();

    if (isProjectResolving) return;

    if (projectLookupFailed) {
        canvasLoadRevision += 1;
        isCanvasLoading = false;
        activateDraftCanvas(context);
        activateDraftAudio(context);
        clearHistory();
        hasUnsavedChanges = false;
        updateSaveButton();
        return;
    }

    if (projectId === null) {
        canvasLoadRevision += 1;
        isCanvasLoading = false;
        activateDraftCanvas(context);
        activateDraftAudio(context);
        clearHistory();
        hasUnsavedChanges = false;
        setTranslatedSaveStatus("canvas.unsaved");
        return;
    }

    await loadStepCanvas(context);
}

async function saveCurrentCanvas() {
    if (
        isSaving
        || isCanvasLoading
        || isProjectResolving
        || projectLookupFailed
        || !currentStepContext
    ) return false;

    const canvas = getActiveCanvasSnapshot();
    const audio = getActiveAudioSnapshot();
    const activeContext = getActiveCanvasContext();
    if (!canvas || !audio || !activeContext || activeContext.stepId !== currentStepContext.stepId) {
        setTranslatedSaveStatus("project.notReady", {}, "error");
        return false;
    }

    isSaving = true;
    updateSaveButton();
    setTranslatedSaveStatus("project.saving");

    const contextAtStart = { ...currentStepContext };
    const projectIdAtStart = projectId;
    const projectRevisionAtStart = projectRevision;
    saveInFlightStepId = contextAtStart.stepId;
    changedDuringSave = false;

    try {
        if (projectIdAtStart === null) {
            const result = await request("/projects", {
                method: "POST",
                body: JSON.stringify({
                    story_id: contextAtStart.storyId,
                    story_step_id: contextAtStart.stepId,
                    title: getProjectTitle(),
                    canvas,
                    audio,
                }),
            });

            // 新故事已开始时，旧创建请求不能污染新作品状态。
            if (projectRevision !== projectRevisionAtStart) return;
            if (
                !Number.isInteger(result.id)
                || result.story_id !== contextAtStart.storyId
                || result.story_step_id !== contextAtStart.stepId
            ) {
                throw new Error(t("project.createInvalid"));
            }

            projectId = result.id;
            const isSameStep = currentStepContext?.stepId === contextAtStart.stepId;

            if (isSameStep && changedDuringSave) {
                // 保存期间画布又变了：保留本地版本（含新编辑），维持未保存状态。
                setTranslatedSaveStatus("project.createdChanged", { id: projectId });
            } else if (isSameStep) {
                storeRemoteCanvas(contextAtStart, projectId, result.canvas, true);
                storeRemoteAudio(contextAtStart, projectId, result.audio, true);
                hasUnsavedChanges = false;
                setTranslatedSaveStatus("project.created", { id: projectId }, "success");
            } else {
                storeRemoteCanvas(contextAtStart, projectId, result.canvas, false);
                storeRemoteAudio(contextAtStart, projectId, result.audio, false);
                if (currentStepContext) {
                    setTranslatedSaveStatus("project.createdLoading", { id: projectId });
                    await loadStepCanvas(currentStepContext);
                }
            }
        } else {
            const result = await request(
                `/projects/${projectIdAtStart}/steps/${contextAtStart.stepId}/canvas`,
                {
                    method: "PUT",
                    body: JSON.stringify({
                        canvas,
                        audio,
                    }),
                },
            );

            if (
                projectRevision !== projectRevisionAtStart
                || projectId !== projectIdAtStart
            ) return;
            if (
                result.project_id !== projectIdAtStart
                || result.story_step_id !== contextAtStart.stepId
            ) {
                throw new Error(t("project.saveInvalid"));
            }

            const isSameStep = currentStepContext?.stepId === contextAtStart.stepId;
            if (isSameStep && changedDuringSave) {
                // 保存期间画布又变了：保留本地版本（含新编辑），维持未保存状态。
                setTranslatedSaveStatus("project.stepSavedChanged", { order: contextAtStart.stepOrder });
            } else {
                storeRemoteCanvas(
                    contextAtStart,
                    projectIdAtStart,
                    result.canvas,
                    isSameStep,
                );
                storeRemoteAudio(
                    contextAtStart,
                    projectIdAtStart,
                    result.audio,
                    isSameStep,
                );
                hasUnsavedChanges = false;
                setTranslatedSaveStatus("project.stepSaved", { order: contextAtStart.stepOrder }, "success");
            }
        }
        return true;
    } catch (error) {
        // projectId 只在成功响应通过校验后赋值，失败不会产生虚假 ID。
        if (error.message) setSaveStatus(error.message, "error");
        else setTranslatedSaveStatus("project.saveFailed", {}, "error");
        return false;
    } finally {
        isSaving = false;
        saveInFlightStepId = null;
        changedDuringSave = false;
        updateSaveButton();
    }
}

export function getCurrentProjectId() {
    return projectId;
}

export function beginAIPreview() {
    isAIPreviewActive = true;
    updateSaveButton();
    return hasUnsavedChanges;
}

export function acceptAIPreview() {
    if (!isAIPreviewActive) return;
    isAIPreviewActive = false;
    hasUnsavedChanges = true;
    setTranslatedSaveStatus("project.changed");
    updateSaveButton();
}

export function rejectAIPreview(originalUnsavedState) {
    if (!isAIPreviewActive) return;
    isAIPreviewActive = false;
    hasUnsavedChanges = Boolean(originalUnsavedState);
    if (hasUnsavedChanges) setTranslatedSaveStatus("project.changed");
    else if (projectId === null) setTranslatedSaveStatus("canvas.unsaved");
    else setTranslatedSaveStatus("project.loaded", {}, "success");
    updateSaveButton();
}

export function resetProject() {
    projectRevision += 1;
    projectLookupRevision += 1;
    canvasLoadRevision += 1;
    projectId = null;
    currentStepContext = null;
    isSaving = false;
    isCanvasLoading = false;
    isProjectResolving = false;
    projectLookupFailed = false;
    activeStoryContext = null;
    hasUnsavedChanges = false;
    pendingSwitchRequest = null;
    changedDuringSave = false;
    saveInFlightStepId = null;
    isAIPreviewActive = false;
    clearHistory();
    clearCanvasCache();
    clearAudioCache();

    const projectName = document.querySelector(".project-name");
    if (projectName) projectName.textContent = getDefaultProjectTitle();
    setTranslatedSaveStatus("canvas.unsaved");
    updateSaveButton();
}

saveButton?.addEventListener("click", saveCurrentCanvas);

window.addEventListener("puzzle-audiobook:step-change", (event) => {
    handleStepChange(event.detail);
});
window.addEventListener("puzzle-audiobook:canvas-change", (event) => {
    if (isAIPreviewActive) return;
    commitPendingHistory();
    if (isSaving && event.detail.stepId === saveInFlightStepId) {
        // 保存请求进行中又产生了新编辑：记下来，保存成功后不能用服务器快照覆盖。
        changedDuringSave = true;
        hasUnsavedChanges = true;
        return;
    }
    if (
        !isSaving
        && currentStepContext?.stepId === event.detail.stepId
    ) {
        hasUnsavedChanges = true;
        setTranslatedSaveStatus("project.changed");
    }
});
window.addEventListener("puzzle-audiobook:audio-change", (event) => {
    if (isAIPreviewActive) return;
    commitPendingHistory();
    if (isSaving && event.detail.stepId === saveInFlightStepId) {
        changedDuringSave = true;
        hasUnsavedChanges = true;
        return;
    }
    if (!isSaving && currentStepContext?.stepId === event.detail.stepId) {
        hasUnsavedChanges = true;
        setTranslatedSaveStatus("project.changed");
    }
});
window.addEventListener("puzzle-audiobook:history-checkpoint", () => {
    if (isRestoringHistory || isAIPreviewActive || pendingHistorySnapshot) return;
    pendingHistorySnapshot = captureHistorySnapshot();
    if (pendingHistorySnapshot) {
        redoSnapshot = null;
        updateHistoryButtons();
    }
});
window.addEventListener("puzzle-audiobook:history-commit-snapshot", (event) => {
    const detail = event.detail;
    if (!detail?.canvas || !detail?.audio || detail.stepId !== currentStepContext?.stepId) return;
    undoSnapshot = {
        stepId: detail.stepId,
        canvas: cloneHistoryValue(detail.canvas),
        audio: cloneHistoryValue(detail.audio),
        wasUnsaved: Boolean(detail.wasUnsaved),
    };
    redoSnapshot = null;
    pendingHistorySnapshot = null;
    updateHistoryButtons();
});
window.addEventListener("puzzle-audiobook:step-change-request", (event) => {
    requestStepSelection(event.detail);
});
window.addEventListener("puzzle-audiobook:story-change-request", (event) => {
    requestStorySelection(event.detail.storyId);
});
window.addEventListener("puzzle-audiobook:story-ready", (event) => {
    activeStoryContext = {
        ...event.detail,
        steps: event.detail.steps.map((step) => ({ ...step })),
    };
    resolveProjectForStory(event.detail);
});
window.addEventListener("puzzle-audiobook:authenticated", () => {
    if (projectLookupFailed && activeStoryContext) {
        resolveProjectForStory(activeStoryContext);
    }
});
window.addEventListener("puzzle-audiobook:language-change", () => {
    updateSaveButton();
    if (projectId === null) {
        const projectName = document.querySelector(".project-name");
        if (projectName) projectName.textContent = getDefaultProjectTitle();
    }
    refreshSaveStatusTranslation();
});
window.addEventListener("puzzle-audiobook:new-story", resetProject);
window.addEventListener("puzzle-audiobook:reset", resetProject);

document.querySelector("[data-unsaved-cancel]")?.addEventListener("click", () => {
    pendingSwitchRequest = null;
    unsavedDialog.close();
});
undoButton?.addEventListener("click", undoLastChange);
redoButton?.addEventListener("click", redoLastChange);
document.querySelector("[data-unsaved-discard]")?.addEventListener("click", () => {
    const requestedSwitch = pendingSwitchRequest;
    if (requestedSwitch) {
        window.dispatchEvent(new CustomEvent("puzzle-audiobook:before-context-switch"));
    }
    pendingSwitchRequest = null;
    hasUnsavedChanges = false;
    discardActiveCanvasChanges();
    discardActiveAudioChanges();
    unsavedDialog.close();
    if (requestedSwitch) performPendingSwitch(requestedSwitch, false);
});
document.querySelector("[data-unsaved-save]")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    button.disabled = true;
    button.textContent = t("unsaved.saving");

    if (pendingSwitchRequest) {
        window.dispatchEvent(new CustomEvent("puzzle-audiobook:before-context-switch"));
    }
    const saved = await saveCurrentCanvas();
    button.disabled = false;
    button.textContent = t("unsaved.save");

    if (!saved) return;
    const requestedSwitch = pendingSwitchRequest;
    pendingSwitchRequest = null;
    unsavedDialog.close();
    if (requestedSwitch) performPendingSwitch(requestedSwitch, false);
});
unsavedDialog?.addEventListener("close", () => {
    pendingSwitchRequest = null;
});

const initialProjectName = document.querySelector(".project-name");
if (initialProjectName) initialProjectName.textContent = getDefaultProjectTitle();
updateSaveButton();
