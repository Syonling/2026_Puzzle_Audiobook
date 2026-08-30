import { t } from "./i18n.js?v=20260829-4";

const EMPTY_CANVAS = Object.freeze({
    objects: [],
    background_key: null,
});
const ASSET_DRAG_TYPE = "application/x-puzzle-audiobook-asset";
const BASE_OBJECT_SIZE = 96;
const MIN_SCALE = 0.35;
const MAX_SCALE = 3;
const BACKGROUND_AUDIO_INSTANCE_ID = "canvas-background";

const canvasCache = new Map();
const localizedAssetsByKey = new Map();
let activeContext = null;
let activeCanvasKey = null;
let selectedObjectId = null;
let isAIPreviewLocked = false;

function createEmptyCanvas() {
    return { ...EMPTY_CANVAS, objects: [] };
}

function normalizeCanvas(canvas) {
    if (!canvas || typeof canvas !== "object" || Array.isArray(canvas)) {
        return createEmptyCanvas();
    }
    return {
        ...canvas,
        objects: Array.isArray(canvas.objects)
            ? canvas.objects.map((object) => {
                const objectId =
                    object.object_id || object.objectId || object.asset_key || "";
                return {
                    ...object,
                    instance_id: object.instance_id || createInstanceId(),
                    object_id: objectId,
                    // source 会随 canvas JSON 保存并在恢复后继续用于实验日志。
                    source: object.source === "AI" ? "AI" : "manual",
                    image_url: object.image_url || object.imageUrl
                        || (objectId ? `/static/images/${objectId}.png` : ""),
                    scale: Number(object.scale) || 1,
                    rotation: Number(object.rotation) || 0,
                    flip_x: object.flip_x === true || object.flipX === true,
                };
            })
            : [],
        background_key: canvas.background_key ?? null,
        background: canvas.background_key && canvas.background?.image_url
            ? { ...canvas.background }
            : null,
    };
}

function getCanvasKey(projectId, storyStepId) {
    return `${projectId === null ? "draft" : projectId}:${storyStepId}`;
}

function getActiveCanvas() {
    return activeCanvasKey ? canvasCache.get(activeCanvasKey) : null;
}

function clamp(value, min, max) {
    return Math.min(Math.max(value, min), max);
}

function createInstanceId() {
    return globalThis.crypto?.randomUUID?.()
        || `object-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function notifyCanvasChanged() {
    if (!activeContext) return;
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:canvas-change", {
        detail: { ...activeContext },
    }));
}

function notifyHistoryCheckpoint() {
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:history-checkpoint"));
}

function notifyObjectTransform(object, final = false) {
    const paper = document.querySelector("[data-canvas-paper]");
    if (!activeContext || !paper) return;
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:canvas-object-transform", {
        detail: {
            context: { ...activeContext },
            canvasWidth: paper.getBoundingClientRect().width,
            object: { ...object },
            final,
        },
    }));
}

function updateObjectElement(wrapper, object) {
    const scale = clamp(Number(object.scale) || 1, MIN_SCALE, MAX_SCALE);
    const rotation = Number(object.rotation) || 0;
    const renderedSize = BASE_OBJECT_SIZE * scale;
    wrapper.style.left = `${Number(object.x) || 0}px`;
    wrapper.style.top = `${Number(object.y) || 0}px`;
    const image = wrapper.querySelector(".canvas-object-image");
    image.style.width = `${renderedSize}px`;
    image.style.height = `${renderedSize}px`;
    image.style.left = `${-renderedSize / 2}px`;
    image.style.top = `${-renderedSize / 2}px`;
    image.style.transform = rotation !== 0 || object.flip_x
        ? `rotate(${rotation}deg) scaleX(${object.flip_x ? -1 : 1})`
        : "none";

    const extent = renderedSize / 2;
    const resizeHandle = wrapper.querySelector(".canvas-resize-handle");
    resizeHandle.style.left = `${extent}px`;
    resizeHandle.style.top = `${extent}px`;
    const rotateHandle = wrapper.querySelector(".canvas-rotate-handle");
    rotateHandle.style.left = `${-extent}px`;
    rotateHandle.style.top = `${extent}px`;
    wrapper.querySelector(".canvas-object-toolbar").style.top =
        `${-extent - 42}px`;
}

function moveObject(event, wrapper, object) {
    if (event.button !== 0 || isAIPreviewLocked) return;
    event.preventDefault();
    event.stopPropagation();
    selectObject(object.instance_id);

    const paper = document.querySelector("[data-canvas-paper]");
    const rect = paper.getBoundingClientRect();
    const startX = event.clientX;
    const startY = event.clientY;
    const originalX = Number(object.x) || 0;
    const originalY = Number(object.y) || 0;
    let didMove = false;
    let historyCaptured = false;

    function onMove(pointerEvent) {
        const nextX = clamp(originalX + pointerEvent.clientX - startX, 0, rect.width);
        const nextY = clamp(originalY + pointerEvent.clientY - startY, 0, rect.height);
        if (!historyCaptured && (nextX !== originalX || nextY !== originalY)) {
            notifyHistoryCheckpoint();
            historyCaptured = true;
        }
        didMove = didMove || nextX !== originalX || nextY !== originalY;
        object.x = nextX;
        object.y = nextY;
        updateObjectElement(wrapper, object);
        notifyObjectTransform(object);
    }

    function onEnd() {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onEnd);
        if (didMove) {
            notifyObjectTransform(object, true);
            notifyCanvasChanged();
        }
    }

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onEnd, { once: true });
}

function resizeObject(event, wrapper, object) {
    if (isAIPreviewLocked) return;
    event.preventDefault();
    event.stopPropagation();

    const paperRect = document.querySelector("[data-canvas-paper]").getBoundingClientRect();
    const centerX = paperRect.left + (Number(object.x) || 0);
    const centerY = paperRect.top + (Number(object.y) || 0);
    const initialDistance = Math.hypot(
        event.clientX - centerX,
        event.clientY - centerY,
    ) || 1;
    const initialScale = Number(object.scale) || 1;
    let historyCaptured = false;

    function onMove(pointerEvent) {
        const distance = Math.hypot(
            pointerEvent.clientX - centerX,
            pointerEvent.clientY - centerY,
        );
        const nextScale = clamp(
            initialScale * distance / initialDistance,
            MIN_SCALE,
            MAX_SCALE,
        );
        if (!historyCaptured && nextScale !== initialScale) {
            notifyHistoryCheckpoint();
            historyCaptured = true;
        }
        object.scale = nextScale;
        updateObjectElement(wrapper, object);
        notifyObjectTransform(object);
    }

    function onEnd() {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onEnd);
        if (historyCaptured) {
            notifyObjectTransform(object, true);
            renderActiveCanvas();
            notifyCanvasChanged();
        }
    }

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onEnd, { once: true });
}

function rotateObject(event, wrapper, object) {
    if (event.button !== 0 || isAIPreviewLocked) return;
    event.preventDefault();
    event.stopPropagation();

    const paperRect = document.querySelector("[data-canvas-paper]").getBoundingClientRect();
    const centerX = paperRect.left + (Number(object.x) || 0);
    const centerY = paperRect.top + (Number(object.y) || 0);
    const startAngle = Math.atan2(event.clientY - centerY, event.clientX - centerX);
    const initialRotation = Number(object.rotation) || 0;
    let historyCaptured = false;

    function onMove(pointerEvent) {
        const pointerAngle = Math.atan2(
            pointerEvent.clientY - centerY,
            pointerEvent.clientX - centerX,
        );
        const angleDelta = (pointerAngle - startAngle) * 180 / Math.PI;
        const nextRotation = ((initialRotation + angleDelta + 180) % 360 + 360) % 360 - 180;
        if (!historyCaptured && nextRotation !== initialRotation) {
            notifyHistoryCheckpoint();
            historyCaptured = true;
        }
        object.rotation = nextRotation;
        updateObjectElement(wrapper, object);
    }

    function onEnd() {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onEnd);
        if (historyCaptured) {
            renderActiveCanvas();
            notifyCanvasChanged();
        }
    }

    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onEnd, { once: true });
}

function changeObjectScale(instanceId, change) {
    if (isAIPreviewLocked) return;
    const object = getActiveCanvas()?.objects.find(
        (item) => item.instance_id === instanceId,
    );
    if (!object) return;
    const currentScale = Number(object.scale) || 1;
    const nextScale = clamp(currentScale + change, MIN_SCALE, MAX_SCALE);
    if (nextScale === currentScale) return;
    notifyHistoryCheckpoint();
    object.scale = nextScale;
    renderActiveCanvas();
    notifyObjectTransform(object, true);
    notifyCanvasChanged();
}

function bringObjectForward(instanceId) {
    if (isAIPreviewLocked) return;
    const canvas = getActiveCanvas();
    if (!canvas) return;
    const index = canvas.objects.findIndex(
        (object) => object.instance_id === instanceId,
    );
    if (index < 0 || index >= canvas.objects.length - 1) return;
    notifyHistoryCheckpoint();
    [canvas.objects[index], canvas.objects[index + 1]] =
        [canvas.objects[index + 1], canvas.objects[index]];
    renderActiveCanvas();
    notifyCanvasChanged();
}

function toggleObjectMirror(instanceId) {
    if (isAIPreviewLocked) return;
    const object = getActiveCanvas()?.objects.find(
        (item) => item.instance_id === instanceId,
    );
    if (!object) return;
    notifyHistoryCheckpoint();
    object.flip_x = !object.flip_x;
    renderActiveCanvas();
    notifyCanvasChanged();
}

function deleteObject(instanceId) {
    if (isAIPreviewLocked) return;
    const canvas = getActiveCanvas();
    if (!canvas) return;
    const deletedObject = canvas.objects.find(
        (object) => object.instance_id === instanceId,
    );
    if (!deletedObject) return;
    notifyHistoryCheckpoint();
    canvas.objects = canvas.objects.filter(
        (object) => object.instance_id !== instanceId,
    );
    selectedObjectId = null;
    renderActiveCanvas();
    notifyCanvasChanged();
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:canvas-object-deleted", {
        detail: {
            context: { ...activeContext },
            object: { ...deletedObject },
        },
    }));
}

function createToolbarButton(label, ariaLabel, action) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.setAttribute("aria-label", ariaLabel);
    button.addEventListener("pointerdown", (event) => {
        event.preventDefault();
        event.stopPropagation();
        action();
    });
    button.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            event.stopPropagation();
            action();
        }
    });
    return button;
}

function createObjectElement(object) {
    const wrapper = document.createElement("div");
    wrapper.className = "canvas-object";
    wrapper.dataset.instanceId = object.instance_id;
    wrapper.classList.toggle("is-selected", object.instance_id === selectedObjectId);
    wrapper.tabIndex = 0;
    wrapper.setAttribute("role", "button");
    const localizedAsset = localizedAssetsByKey.get(object.asset_key);
    const objectLabel = localizedAsset?.name
        || object.label
        || object.name
        || t("canvas.object");
    wrapper.setAttribute("aria-label", t("canvas.editObject", { label: objectLabel }));

    const image = document.createElement("img");
    image.className = "canvas-object-image";
    image.src = localizedAsset?.image_url || object.image_url;
    image.alt = objectLabel;
    image.draggable = false;
    image.addEventListener("error", () => {
        const fallback = document.createElement("span");
        // 保留 canvas-object-image 类，updateObjectElement 依赖它设置位移和缩放。
        fallback.className = "canvas-object-image canvas-object-fallback";
        fallback.textContent = objectLabel.slice(0, 2);
        image.replaceWith(fallback);
        updateObjectElement(wrapper, object);
    }, { once: true });

    const toolbar = document.createElement("div");
    toolbar.className = "canvas-object-toolbar";
    toolbar.append(
        createToolbarButton("−", t("canvas.zoomOut"), () => changeObjectScale(object.instance_id, -0.1)),
        createToolbarButton(
            `${Math.round((Number(object.scale) || 1) * 100)}%`,
            t("canvas.zoom"),
            () => {},
        ),
        createToolbarButton("+", t("canvas.zoomIn"), () => changeObjectScale(object.instance_id, 0.1)),
        createToolbarButton("⇧", t("canvas.bringForward"), () => bringObjectForward(object.instance_id)),
        createToolbarButton("↔", t("canvas.mirrorHorizontal"), () => toggleObjectMirror(object.instance_id)),
        createToolbarButton(t("canvas.delete"), t("canvas.deleteObject"), () => deleteObject(object.instance_id)),
    );

    const resizeHandle = document.createElement("button");
    resizeHandle.type = "button";
    resizeHandle.className = "canvas-resize-handle";
    resizeHandle.setAttribute("aria-label", t("canvas.resize"));
    resizeHandle.addEventListener("pointerdown", (event) => {
        resizeObject(event, wrapper, object);
    });

    const rotateHandle = document.createElement("button");
    rotateHandle.type = "button";
    rotateHandle.className = "canvas-rotate-handle";
    rotateHandle.textContent = "↻";
    rotateHandle.setAttribute("aria-label", t("canvas.rotate"));
    rotateHandle.addEventListener("pointerdown", (event) => {
        rotateObject(event, wrapper, object);
    });

    wrapper.append(image, toolbar, resizeHandle, rotateHandle);
    wrapper.addEventListener("pointerdown", () => {
        if (selectedObjectId !== object.instance_id) {
            selectObject(object.instance_id);
        }
    }, { capture: true });
    wrapper.addEventListener("pointerdown", (event) => {
        if (event.target.closest("button")) return;
        moveObject(event, wrapper, object);
    });
    wrapper.addEventListener("focus", () => {
        if (selectedObjectId !== object.instance_id) {
            selectObject(object.instance_id);
        }
    });
    updateObjectElement(wrapper, object);
    return wrapper;
}

function renderObjects(canvas) {
    const layer = document.querySelector("[data-canvas-object-layer]");
    if (!layer) return;
    layer.replaceChildren(...canvas.objects.map(createObjectElement));
}

function renderCanvas(context, canvas, animate = false) {
    const paper = document.querySelector("[data-canvas-paper]");
    if (!paper) return;

    paper.classList.remove("is-loading", "is-drop-target");
    paper.dataset.projectId = context.projectId === null ? "draft" : String(context.projectId);
    paper.dataset.storyStepId = String(context.stepId);
    paper.dataset.storyId = String(context.storyId);
    paper.dataset.stepOrder = String(context.stepOrder);

    document.querySelector("[data-canvas-page]").textContent =
        t("canvas.page", { order: context.stepOrder, total: context.totalSteps });
    document.querySelector("[data-canvas-title]").textContent =
        t("canvas.stepTitle", { title: context.storyTitle, order: context.stepOrder });
    document.querySelector("[data-canvas-description]").textContent =
        t("canvas.dragHint");
    document.querySelector("[data-canvas-empty]").hidden =
        canvas.objects.length > 0 || Boolean(canvas.background_key);

    const backgroundKey = canvas.background_key;
    const removeBackgroundButton = document.querySelector("[data-canvas-background-remove]");
    if (removeBackgroundButton) removeBackgroundButton.hidden = !backgroundKey;
    const localizedBackground = localizedAssetsByKey.get(backgroundKey);
    const backgroundUrl = canvas.background?.image_url
        || localizedBackground?.image_url
        || (typeof backgroundKey === "string" && backgroundKey
            ? `/static/images/${backgroundKey}.jpg`
            : "");
    paper.style.backgroundImage = backgroundUrl ? `url("${backgroundUrl}")` : "";
    paper.dataset.backgroundKey = backgroundKey === null ? "" : String(backgroundKey);
    renderObjects(canvas);

    paper.classList.remove("is-switching");
    if (animate) requestAnimationFrame(() => paper.classList.add("is-switching"));
}

function renderActiveCanvas() {
    const canvas = getActiveCanvas();
    if (canvas && activeContext) renderCanvas(activeContext, canvas);
}

function selectObject(instanceId) {
    selectedObjectId = instanceId;
    document.querySelectorAll(".canvas-object").forEach((element) => {
        element.classList.toggle(
            "is-selected",
            element.dataset.instanceId === selectedObjectId,
        );
    });
    const object = instanceId
        ? getActiveCanvas()?.objects.find((item) => item.instance_id === instanceId)
        : null;
    const localizedAsset = object
        ? localizedAssetsByKey.get(object.asset_key)
        : null;
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:canvas-object-selected", {
        detail: {
            context: activeContext ? { ...activeContext } : null,
            object: object ? {
                ...(localizedAsset || {}),
                ...object,
                audio_options: Array.isArray(localizedAsset?.audio_options)
                    ? localizedAsset.audio_options.map((option) => ({ ...option }))
                    : [],
            } : null,
        },
    }));
}

function selectBackground() {
    const canvas = getActiveCanvas();
    selectedObjectId = null;
    document.querySelectorAll(".canvas-object.is-selected").forEach(
        (element) => element.classList.remove("is-selected"),
    );
    const backgroundAsset = localizedAssetsByKey.get(canvas?.background_key);
    const background = canvas?.background_key
        ? {
            ...(backgroundAsset || {}),
            ...(canvas.background || {}),
            instance_id: BACKGROUND_AUDIO_INSTANCE_ID,
            asset_key: canvas.background_key,
            label: backgroundAsset?.name || canvas.background_key,
            image_url: canvas.background?.image_url || backgroundAsset?.image_url || null,
            selected_audio_key: canvas.background?.selected_audio_key ?? null,
            audio_url: canvas.background?.audio_url ?? null,
        }
        : null;
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:canvas-background-selected", {
        detail: {
            context: activeContext ? { ...activeContext } : null,
            background,
        },
    }));
}

function resolveAssetAudio(asset, audioSuggestion = null) {
    const audioOptions = Array.isArray(asset.audio_options) ? asset.audio_options : [];
    const recommendedAudio = audioSuggestion?.asset_key === asset.asset_key
        ? audioOptions.find(
            (option) => option.audio_key === audioSuggestion.selected_audio_key,
        ) || null
        : null;
    const defaultAudio = audioOptions.find(
        (option) => option.audio_key === asset.default_audio_key,
    ) || audioOptions.find((option) => option.is_default === true) || null;
    const selectedAudio = recommendedAudio || defaultAudio;
    return {
        audioKey: selectedAudio?.audio_key ?? asset.default_audio_key ?? null,
        audioUrl: selectedAudio?.audio_url
            ?? (recommendedAudio ? audioSuggestion?.audio_url : null)
            ?? asset.audio_url
            ?? null,
        effects: recommendedAudio && audioSuggestion?.effects
            && typeof audioSuggestion.effects === "object"
                ? { ...audioSuggestion.effects }
                : {},
        startOffset: recommendedAudio
            && Number.isFinite(Number(audioSuggestion?.start_offset_seconds))
                ? Math.max(0, Number(audioSuggestion.start_offset_seconds))
                : null,
    };
}

function addAssetToCanvas(asset, clientX, clientY, audioSuggestion = null) {
    const canvas = getActiveCanvas();
    const paper = document.querySelector("[data-canvas-paper]");
    if (isAIPreviewLocked || !canvas || !activeContext || paper.classList.contains("is-loading")) return;

    notifyHistoryCheckpoint();
    const rect = paper.getBoundingClientRect();
    const audioChoice = resolveAssetAudio(asset, audioSuggestion);
    const addedObject = {
        instance_id: createInstanceId(),
        asset_id: asset.id,
        object_id: asset.asset_key,
        asset_key: asset.asset_key,
        category: asset.category ?? null,
        label: asset.name,
        image_url: asset.image_url,
        audio_url: audioChoice.audioUrl,
        selected_audio_key: audioChoice.audioKey,
        source: asset.interaction_source === "AI" ? "AI" : "manual",
        effects: audioChoice.effects,
        start_offset_seconds: audioChoice.startOffset,
        x: clamp(clientX - rect.left, 0, rect.width),
        y: clamp(clientY - rect.top, 0, rect.height),
        scale: 1,
        rotation: 0,
        flip_x: false,
    };
    canvas.objects.push(addedObject);
    renderActiveCanvas();
    selectObject(addedObject.instance_id);
    notifyCanvasChanged();
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:canvas-object-added", {
        detail: {
            context: { ...activeContext },
            canvasWidth: rect.width,
            object: { ...addedObject },
        },
    }));
}

function addAssetToCanvasCenter(asset, audioSuggestion = null) {
    const paper = document.querySelector("[data-canvas-paper]");
    if (!paper) return;
    const rect = paper.getBoundingClientRect();
    const objectCount = getActiveCanvas()?.objects.length || 0;
    const stagger = (objectCount % 5 - 2) * 18;
    addAssetToCanvas(
        asset,
        rect.left + rect.width / 2 + stagger,
        rect.top + rect.height / 2 + stagger,
        audioSuggestion,
    );
}

function applyBackgroundToCanvas(asset, audioSuggestion = null) {
    const canvas = getActiveCanvas();
    const paper = document.querySelector("[data-canvas-paper]");
    if (
        isAIPreviewLocked
        || !canvas
        || !activeContext
        || paper?.classList.contains("is-loading")
        || asset?.category !== "background"
        || typeof asset.asset_key !== "string"
        || !asset.asset_key
    ) return;

    notifyHistoryCheckpoint();
    const audioChoice = resolveAssetAudio(asset, audioSuggestion);
    canvas.background_key = asset.asset_key;
    canvas.background = {
        asset_key: asset.asset_key,
        image_url: asset.image_url,
        selected_audio_key: audioChoice.audioKey,
        audio_url: audioChoice.audioUrl,
        start_offset_seconds: audioChoice.startOffset,
        effects: audioChoice.effects,
        source: asset.interaction_source === "AI" ? "AI" : "manual",
    };
    selectObject(null);
    renderActiveCanvas();
    notifyCanvasChanged();
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:canvas-background-changed", {
        detail: {
            context: { ...activeContext },
            background: {
                instance_id: BACKGROUND_AUDIO_INSTANCE_ID,
                asset_id: asset.id,
                asset_key: asset.asset_key,
                label: asset.name,
                image_url: asset.image_url,
                selected_audio_key: audioChoice.audioKey,
                audio_url: audioChoice.audioUrl,
                start_offset_seconds: audioChoice.startOffset,
                effects: audioChoice.effects,
                source: asset.interaction_source === "AI" ? "AI" : "manual",
            },
        },
    }));
    selectBackground();
}

function removeBackgroundFromCanvas() {
    const canvas = getActiveCanvas();
    const paper = document.querySelector("[data-canvas-paper]");
    if (isAIPreviewLocked || !canvas || !activeContext || paper?.classList.contains("is-loading")) return;
    if (!canvas.background_key) return;

    notifyHistoryCheckpoint();
    canvas.background_key = null;
    canvas.background = null;
    renderActiveCanvas();
    notifyCanvasChanged();
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:canvas-background-changed", {
        detail: {
            context: { ...activeContext },
            background: null,
        },
    }));
    selectBackground();
}

export function activateDraftCanvas(context) {
    const key = getCanvasKey(null, context.stepId);
    if (!canvasCache.has(key)) canvasCache.set(key, createEmptyCanvas());
    activeContext = { ...context, projectId: null };
    activeCanvasKey = key;
    selectedObjectId = null;
    renderCanvas(activeContext, canvasCache.get(key), true);
}

export function showRemoteCanvasLoading(context, projectId) {
    activeContext = { ...context, projectId };
    activeCanvasKey = getCanvasKey(projectId, context.stepId);
    selectedObjectId = null;

    const paper = document.querySelector("[data-canvas-paper]");
    if (!paper) return;
    paper.classList.add("is-loading");
    paper.dataset.projectId = String(projectId);
    paper.dataset.storyStepId = String(context.stepId);
    const removeBackgroundButton = document.querySelector("[data-canvas-background-remove]");
    if (removeBackgroundButton) removeBackgroundButton.hidden = true;
    document.querySelector("[data-canvas-page]").textContent =
        t("canvas.page", { order: context.stepOrder, total: context.totalSteps });
    document.querySelector("[data-canvas-title]").textContent = t("canvas.loading");
    document.querySelector("[data-canvas-description]").textContent =
        t("canvas.loadingSaved");
    document.querySelector("[data-canvas-empty]").hidden = false;
    document.querySelector("[data-canvas-object-layer]").replaceChildren();
}

export function restoreRemoteCanvas(context, projectId, canvas) {
    const key = getCanvasKey(projectId, context.stepId);
    const normalized = normalizeCanvas(canvas);
    canvasCache.set(key, normalized);
    activeContext = { ...context, projectId };
    activeCanvasKey = key;
    selectedObjectId = null;
    renderCanvas(activeContext, normalized, true);
}

export function storeRemoteCanvas(context, projectId, canvas, activate = false) {
    const realKey = getCanvasKey(projectId, context.stepId);
    const normalized = normalizeCanvas(canvas);
    canvasCache.set(realKey, normalized);
    canvasCache.delete(getCanvasKey(null, context.stepId));
    if (activate) {
        activeCanvasKey = realKey;
        activeContext = { ...context, projectId };
        selectedObjectId = null;
        renderCanvas(activeContext, normalized);
    }
}

export function getActiveCanvasSnapshot() {
    if (document.querySelector("[data-canvas-paper]")?.classList.contains("is-loading")) {
        return null;
    }
    const canvas = getActiveCanvas();
    return canvas && activeContext ? normalizeCanvas(canvas) : null;
}

export function getActiveCanvasContext() {
    return activeContext ? { ...activeContext } : null;
}

export function restoreActiveCanvasSnapshot(canvas) {
    if (!activeCanvasKey || !activeContext) return false;
    const normalized = normalizeCanvas(canvas);
    canvasCache.set(activeCanvasKey, normalized);
    selectedObjectId = null;
    renderCanvas(activeContext, normalized);
    return true;
}

export function setCanvasAIPreviewLocked(locked) {
    isAIPreviewLocked = Boolean(locked);
    const paper = document.querySelector("[data-canvas-paper]");
    paper?.classList.toggle("is-ai-preview", isAIPreviewLocked);
}

export function replaceActiveCanvasFromAI(aiCanvas, options = {}) {
    if (!activeCanvasKey || !activeContext) {
        throw new Error(t("canvas.noEditable"));
    }
    if (
        !aiCanvas
        || typeof aiCanvas !== "object"
        || Array.isArray(aiCanvas)
        || !Array.isArray(aiCanvas.objects)
    ) {
        throw new Error(t("canvas.aiInvalid"));
    }

    const objects = aiCanvas.objects.map((object) => {
        if (!object || typeof object.asset_key !== "string" || !object.asset_key) {
            throw new Error(t("canvas.aiAssetInvalid"));
        }

        const numericFields = ["x", "y", "scale", "rotation"];
        if (numericFields.some((field) => !Number.isFinite(Number(object[field])))) {
            throw new Error(t("canvas.aiCoordinateInvalid"));
        }

        return {
            instance_id: createInstanceId(),
            asset_id: object.asset_id ?? null,
            object_id: object.asset_key,
            asset_key: object.asset_key,
            category: object.category ?? null,
            label: object.name || object.asset_key,
            image_url: object.image_url || `/static/images/${object.asset_key}.png`,
            audio_url: object.audio_url ?? null,
            selected_audio_key: object.selected_audio_key ?? null,
            effects: object.effects && typeof object.effects === "object"
                ? { ...object.effects }
                : {},
            start_offset_seconds:
                object.start_offset_seconds !== null
                && object.start_offset_seconds !== undefined
                && Number.isFinite(Number(object.start_offset_seconds))
                    ? Math.max(0, Number(object.start_offset_seconds))
                    : null,
            x: Number(object.x),
            y: Number(object.y),
            scale: clamp(Number(object.scale), MIN_SCALE, MAX_SCALE),
            rotation: Number(object.rotation),
            flip_x: object.flip_x === true,
            source: "AI",
        };
    });

    const backgroundKey = aiCanvas.background_key ?? null;
    const background = backgroundKey !== null && aiCanvas.background?.image_url
        ? {
            asset_key: backgroundKey,
            image_url: aiCanvas.background.image_url,
            selected_audio_key: aiCanvas.background.selected_audio_key ?? null,
            audio_url: aiCanvas.background.audio_url ?? null,
            audio_enabled: aiCanvas.background.audio_enabled === true,
            start_offset_seconds:
                aiCanvas.background.start_offset_seconds !== null
                && aiCanvas.background.start_offset_seconds !== undefined
                && Number.isFinite(Number(aiCanvas.background.start_offset_seconds))
                    ? Math.max(0, Number(aiCanvas.background.start_offset_seconds))
                    : null,
            effects: aiCanvas.background.effects
                && typeof aiCanvas.background.effects === "object"
                    ? { ...aiCanvas.background.effects }
                    : {},
            source: "AI",
        }
        : null;

    canvasCache.set(activeCanvasKey, normalizeCanvas({
        objects,
        background_key: backgroundKey,
        background,
    }));
    selectedObjectId = null;
    renderActiveCanvas();
    notifyCanvasChanged();
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:canvas-objects-replaced", {
        detail: {
            context: { ...activeContext },
            canvasWidth: document.querySelector("[data-canvas-paper]")
                ?.getBoundingClientRect().width,
            objects: objects.map((object) => ({ ...object })),
            background: background ? {
                instance_id: BACKGROUND_AUDIO_INSTANCE_ID,
                asset_id: null,
                asset_key: backgroundKey,
                label: backgroundKey,
                image_url: background.image_url,
                selected_audio_key: background.selected_audio_key,
                audio_url: background.audio_url,
                audio_enabled: background.audio_enabled,
                start_offset_seconds: background.start_offset_seconds,
                effects: background.effects,
            } : null,
            responseToken: options.responseToken ?? null,
            suggestionId: options.suggestionId ?? null,
        },
    }));
}

export function discardActiveCanvasChanges() {
    if (!activeCanvasKey || !activeContext) return;

    if (activeContext.projectId === null) {
        canvasCache.set(activeCanvasKey, createEmptyCanvas());
    } else {
        // 已有项目再次进入该步骤时会从后端重新读取已保存版本。
        canvasCache.delete(activeCanvasKey);
    }
    selectedObjectId = null;
}

export function clearCanvasCache() {
    canvasCache.clear();
    activeCanvasKey = null;
    activeContext = null;
    selectedObjectId = null;
    isAIPreviewLocked = false;

    const paper = document.querySelector("[data-canvas-paper]");
    if (!paper) return;
    paper.classList.remove("is-loading", "is-drop-target");
    paper.removeAttribute("data-project-id");
    paper.removeAttribute("data-story-step-id");
    paper.removeAttribute("data-story-id");
    paper.removeAttribute("data-step-order");
    paper.removeAttribute("data-background-key");
    paper.style.backgroundImage = "";
    const removeBackgroundButton = document.querySelector("[data-canvas-background-remove]");
    if (removeBackgroundButton) removeBackgroundButton.hidden = true;
    document.querySelector("[data-canvas-object-layer]").replaceChildren();
    document.querySelector("[data-canvas-empty]").hidden = false;
    document.querySelector("[data-canvas-page]").textContent = t("canvas.noStep");
    document.querySelector("[data-canvas-title]").textContent = t("canvas.area");
    document.querySelector("[data-canvas-description]").textContent =
        t("canvas.chooseStep");
}

export function resetCanvas() {
    clearCanvasCache();
}

const paper = document.querySelector("[data-canvas-paper]");
paper?.addEventListener("dragover", (event) => {
    if (isAIPreviewLocked || !activeContext || paper.classList.contains("is-loading")) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
    paper.classList.add("is-drop-target");
});
paper?.addEventListener("dragleave", (event) => {
    if (!paper.contains(event.relatedTarget)) paper.classList.remove("is-drop-target");
});
paper?.addEventListener("drop", (event) => {
    event.preventDefault();
    paper.classList.remove("is-drop-target");
    const rawAsset = event.dataTransfer.getData(ASSET_DRAG_TYPE)
        || event.dataTransfer.getData("text/plain");
    try {
        const asset = JSON.parse(rawAsset);
        const audioSuggestion = asset?.ai_audio_suggestion || null;
        if (asset?.category === "background") applyBackgroundToCanvas(asset, audioSuggestion);
        else addAssetToCanvas(asset, event.clientX, event.clientY, audioSuggestion);
    } catch {
        // 忽略不是素材库产生的拖放数据。
    }
});
paper?.addEventListener("pointerdown", (event) => {
    if (
        event.target === paper
        || event.target.matches("[data-canvas-object-layer]")
        || event.target.closest("[data-canvas-empty]")
    ) {
        if (getActiveCanvas()?.background_key) selectBackground();
        else selectObject(null);
    }
});
document.querySelector("[data-canvas-background-remove]")?.addEventListener("click", (event) => {
    event.preventDefault();
    event.stopPropagation();
    removeBackgroundFromCanvas();
});

window.addEventListener("keydown", (event) => {
    if (!isAIPreviewLocked && (event.key === "Delete" || event.key === "Backspace") && selectedObjectId) {
        const tagName = document.activeElement?.tagName;
        if (tagName !== "INPUT" && tagName !== "TEXTAREA") {
            event.preventDefault();
            deleteObject(selectedObjectId);
        }
    }
});
window.addEventListener("puzzle-audiobook:reset", resetCanvas);
window.addEventListener("puzzle-audiobook:asset-activate", (event) => {
    const asset = event.detail?.asset;
    if (asset?.category === "background") {
        applyBackgroundToCanvas(asset, event.detail?.audioSuggestion);
    } else if (asset) {
        addAssetToCanvasCenter(asset, event.detail?.audioSuggestion);
    }
});
window.addEventListener("puzzle-audiobook:language-change", renderActiveCanvas);
window.addEventListener("puzzle-audiobook:localized-assets", (event) => {
    const assets = Array.isArray(event.detail?.assets) ? event.detail.assets : [];
    localizedAssetsByKey.clear();
    assets.forEach((asset) => localizedAssetsByKey.set(asset.asset_key, { ...asset }));
    renderActiveCanvas();
});
window.addEventListener("puzzle-audiobook:canvas-object-audio-choice-applied", (event) => {
    if (
        !activeContext
        || event.detail?.context?.stepId !== activeContext.stepId
        || !event.detail?.instanceId
    ) return;
    const object = getActiveCanvas()?.objects.find(
        (item) => item.instance_id === event.detail.instanceId,
    );
    if (!object) return;
    object.selected_audio_key = event.detail.audioKey ?? null;
    object.audio_url = event.detail.audioUrl ?? null;
    notifyCanvasChanged();
});
window.addEventListener("puzzle-audiobook:canvas-background-audio-choice-applied", (event) => {
    if (
        !activeContext
        || event.detail?.context?.stepId !== activeContext.stepId
    ) return;
    const canvas = getActiveCanvas();
    if (!canvas?.background_key || !canvas.background) return;
    canvas.background.selected_audio_key = event.detail.audioKey ?? null;
    canvas.background.audio_url = event.detail.audioUrl ?? null;
    if ("audio_enabled" in canvas.background) {
        canvas.background.audio_enabled = Boolean(event.detail.audioUrl);
    }
    notifyCanvasChanged();
});
window.addEventListener("puzzle-audiobook:localized-story", (event) => {
    if (
        !activeContext
        || event.detail?.storyId !== activeContext.storyId
        || event.detail?.stepId !== activeContext.stepId
    ) return;
    activeContext = {
        ...activeContext,
        storyTitle: event.detail.storyTitle,
        sentence: event.detail.sentence,
    };
    renderActiveCanvas();
});
