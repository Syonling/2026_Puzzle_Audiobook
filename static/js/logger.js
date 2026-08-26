import { getActiveCanvasContext, getActiveCanvasSnapshot } from "./canvas.js?v=20260826-7";
import { getActiveAudioSnapshot } from "./audio.js?v=20260826-7";

const QUEUE_KEY = "puzzleAudiobook.eventQueue";
const SESSION_KEY = "puzzleAudiobook.eventSessionId";
const EXPERIMENT_KEY = "puzzleAudiobook.experimentContext";
const USER_KEY = "puzzleAudiobook.user";
const ENDPOINT = "/logs/events/batch";
const FLUSH_INTERVAL = 5000;
const MAX_QUEUE_SIZE = 2000;

let queue = readJSON(localStorage, QUEUE_KEY, []);
if (!Array.isArray(queue)) queue = [];
let sessionId = sessionStorage.getItem(SESSION_KEY);
let pageContext = null;
let pageStartedAt = null;
let previousAudio = null;
let previousCanvas = null;
let flushInFlight = false;
let nextFlushAt = 0;
let activePreviewStartedAt = null;
let currentSuggestionId = null;
const objectSources = new Map();
const objectSuggestionIds = new Map();
const suggestedAssetKeys = new Set();

function createId(prefix) {
    return globalThis.crypto?.randomUUID?.()
        || `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

if (!sessionId) {
    sessionId = createId("session");
    sessionStorage.setItem(SESSION_KEY, sessionId);
}

function readJSON(storage, key, fallback) {
    try {
        const parsed = JSON.parse(storage.getItem(key));
        return parsed ?? fallback;
    } catch {
        return fallback;
    }
}

function clone(value) {
    if (value === null || value === undefined) return value;
    return typeof structuredClone === "function"
        ? structuredClone(value)
        : JSON.parse(JSON.stringify(value));
}

function getIdentity() {
    const experiment = readJSON(sessionStorage, EXPERIMENT_KEY,
        readJSON(localStorage, EXPERIMENT_KEY, {}));
    const user = readJSON(localStorage, USER_KEY, null);
    return {
        pair_id: experiment?.pair_id ?? user?.pair_id ?? null,
        participant_id: experiment?.participant_id ?? user?.participant_id ?? user?.id ?? null,
        condition: experiment?.condition ?? user?.condition ?? null,
    };
}

function persistQueue() {
    try {
        localStorage.setItem(QUEUE_KEY, JSON.stringify(queue.slice(-MAX_QUEUE_SIZE)));
    } catch {
        queue = queue.slice(-Math.floor(MAX_QUEUE_SIZE / 2));
    }
}

export function configureExperimentContext(context = {}) {
    sessionStorage.setItem(EXPERIMENT_KEY, JSON.stringify({
        pair_id: context.pair_id ?? null,
        participant_id: context.participant_id ?? null,
        condition: context.condition ?? null,
        experiment_id: context.experiment_id ?? null,
    }));
}

export function track(eventType, data = {}) {
    const context = getActiveCanvasContext() || pageContext || {};
    const identity = getIdentity();
    const event = {
        event_id: createId("event"),
        session_id: sessionId,
        pair_id: identity.pair_id,
        participant_id: identity.participant_id,
        condition: identity.condition,
        story_id: data.story_id ?? context.storyId ?? null,
        page_id: data.page_id ?? context.stepId ?? null,
        timestamp: new Date().toISOString(),
        event_type: eventType,
        target_id: data.target_id ?? null,
        target_type: data.target_type ?? null,
        source: data.source ?? null,
        event_data: clone(data.event_data || {}),
    };
    queue.push(event);
    if (queue.length > MAX_QUEUE_SIZE) queue = queue.slice(-MAX_QUEUE_SIZE);
    persistQueue();
    if (queue.length >= 20) flush();
    return event.event_id;
}

function snapshot(snapshotType, extra = {}) {
    const canvas = getActiveCanvasSnapshot();
    const audio = getActiveAudioSnapshot();
    if (!canvas || !audio) return;
    track("canvas_snapshot", {
        target_type: "page",
        event_data: {
            snapshot_type: snapshotType,
            snapshot_timestamp: new Date().toISOString(),
            icons: (canvas.objects || []).map((object, layer) => ({
                instance_id: object.instance_id,
                asset_id: object.asset_id ?? null,
                asset_key: object.asset_key,
                category: object.category ?? null,
                source: objectSources.get(object.instance_id) || object.source || "manual",
                x: object.x,
                y: object.y,
                width: 96 * (Number(object.scale) || 1),
                height: 96 * (Number(object.scale) || 1),
                scale: object.scale,
                rotation: object.rotation,
                layer,
            })),
            audio_clips: audioClips(audio).map((clip) => ({
                clip_id: clip.clip_id,
                icon_instance_id: clip.object_instance_id,
                audio_id: clip.audio_key || clip.clip_id,
                source: objectSources.get(clip.object_instance_id) || "manual",
                track_id: clip.track_id,
                start_time: clip.start_time,
                duration: clip.duration,
            })),
            canvas,
            audio,
            ...extra,
        },
    });
}

async function flush({ beacon = false } = {}) {
    if (flushInFlight || queue.length === 0 || Date.now() < nextFlushAt) return;
    const batch = queue.slice(0, 50);
    const body = JSON.stringify({ events: batch });
    if (beacon && navigator.sendBeacon) {
        navigator.sendBeacon(ENDPOINT, new Blob([body], { type: "application/json" }));
        return;
    }
    flushInFlight = true;
    try {
        const response = await fetch(ENDPOINT, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body,
        });
        if (!response.ok) throw new Error(String(response.status));
        const result = await response.json().catch(() => ({}));
        const accepted = new Set(
            Array.isArray(result.accepted_event_ids)
                ? result.accepted_event_ids
                : batch.map((event) => event.event_id),
        );
        queue = queue.filter((event) => !accepted.has(event.event_id));
        persistQueue();
        nextFlushAt = 0;
    } catch {
        nextFlushAt = Date.now() + 30000;
    } finally {
        flushInFlight = false;
    }
}

function objectState(object) {
    return {
        x: Number(object?.x) || 0,
        y: Number(object?.y) || 0,
        scale: Number(object?.scale) || 1,
        rotation: Number(object?.rotation) || 0,
        flip_x: object?.flip_x === true,
        asset_key: object?.asset_key || null,
    };
}

function rememberCanvas(canvas = getActiveCanvasSnapshot()) {
    previousCanvas = clone(canvas);
    canvas?.objects?.forEach((object) => {
        if (!objectSources.has(object.instance_id)) {
            objectSources.set(object.instance_id, object.source || "manual");
        }
    });
}

function handleObjectTransform(detail) {
    if (!detail?.final || !detail.object?.instance_id) return;
    const object = detail.object;
    const beforeObject = previousCanvas?.objects?.find(
        (candidate) => candidate.instance_id === object.instance_id,
    );
    const before = objectState(beforeObject || object);
    const after = objectState(object);
    const common = {
        target_id: object.instance_id,
        target_type: "icon",
        source: objectSources.get(object.instance_id) || "manual",
    };
    if (before.x !== after.x || before.y !== after.y) {
        track("icon_move", { ...common, event_data: {
            before, after, suggestion_id: objectSuggestionIds.get(object.instance_id) || null,
        } });
    }
    if (before.scale !== after.scale) {
        track("icon_resize", { ...common, event_data: {
            before, after, suggestion_id: objectSuggestionIds.get(object.instance_id) || null,
        } });
    }
    if (before.rotation !== after.rotation || before.flip_x !== after.flip_x) {
        track("icon_transform", { ...common, event_data: {
            before, after, suggestion_id: objectSuggestionIds.get(object.instance_id) || null,
        } });
    }
    rememberCanvas();
}

function audioClips(audio) {
    return audio?.tracks?.flatMap((track) => track.clips.map(
        (clip) => ({ ...clip, track_id: track.id }),
    )) || [];
}

function handleAudioChange() {
    const current = getActiveAudioSnapshot();
    if (!current) return;
    if (!previousAudio) {
        previousAudio = clone(current);
        return;
    }
    const beforeById = new Map(audioClips(previousAudio).map((clip) => [clip.clip_id, clip]));
    const afterById = new Map(audioClips(current).map((clip) => [clip.clip_id, clip]));
    afterById.forEach((clip, clipId) => {
        const before = beforeById.get(clipId);
        const source = objectSources.get(clip.object_instance_id) || "manual";
        const common = {
            target_id: clipId,
            target_type: "audio",
            source,
            event_data: {
                icon_id: clip.object_instance_id,
                audio_id: clip.audio_key || clipId,
                suggestion_id: objectSuggestionIds.get(clip.object_instance_id) || null,
            },
        };
        if (!before) {
            track("audio_add", common);
            return;
        }
        if (before.audio_key !== clip.audio_key || before.audio_url !== clip.audio_url) {
            track("audio_replace", {
                ...common,
                event_data: {
                    ...common.event_data,
                    old_audio_id: before.audio_key || before.clip_id,
                    new_audio_id: clip.audio_key || clip.clip_id,
                },
            });
        }
        if (before.start_time !== clip.start_time) {
            track("audio_move", {
                ...common,
                event_data: { ...common.event_data, from: before.start_time, to: clip.start_time },
            });
        }
        if (before.trim_start !== clip.trim_start || before.trim_end !== clip.trim_end) {
            track("audio_trim", {
                ...common,
                event_data: {
                    ...common.event_data,
                    before: { start: before.trim_start, end: before.trim_end },
                    after: { start: clip.trim_start, end: clip.trim_end },
                },
            });
        }
    });
    beforeById.forEach((clip, clipId) => {
        if (afterById.has(clipId)) return;
        track("audio_delete", {
            target_id: clipId,
            target_type: "audio",
            source: objectSources.get(clip.object_instance_id) || "manual",
            event_data: {
                icon_id: clip.object_instance_id,
                audio_id: clip.audio_key || clipId,
            },
        });
    });
    previousAudio = clone(current);
}

function endCurrentPage(reason) {
    if (!pageContext || !pageStartedAt) return;
    track("page_end", {
        story_id: pageContext.storyId,
        page_id: pageContext.stepId,
        target_type: "page",
        event_data: {
            reason,
            started_at: pageStartedAt,
            duration_ms: Math.max(0, Date.now() - Date.parse(pageStartedAt)),
        },
    });
}

window.addEventListener("puzzle-audiobook:step-change", (event) => {
    const next = event.detail;
    if (pageContext?.stepId !== next?.stepId) {
        const previous = pageContext ? { ...pageContext } : null;
        endCurrentPage("page_switch");
        if (previous) {
            track("page_switch", {
                story_id: next?.storyId,
                page_id: next?.stepId,
                target_type: "page",
                event_data: {
                    from_page_id: previous.stepId,
                    to_page_id: next?.stepId ?? null,
                },
            });
        }
    }
    pageContext = next ? { ...next } : null;
    pageStartedAt = new Date().toISOString();
    previousCanvas = null;
    previousAudio = null;
    objectSources.clear();
    objectSuggestionIds.clear();
    track("page_start", {
        story_id: next?.storyId,
        page_id: next?.stepId,
        target_type: "page",
        event_data: { step_order: next?.stepOrder },
    });
});

window.addEventListener("puzzle-audiobook:page-state-ready", () => {
    rememberCanvas();
    previousAudio = clone(getActiveAudioSnapshot());
    snapshot("page_start");
});

window.addEventListener("puzzle-audiobook:canvas-object-added", (event) => {
    const object = event.detail?.object;
    if (!object) return;
    const source = object.source === "AI" || suggestedAssetKeys.has(object.asset_key)
        ? "AI"
        : "manual";
    objectSources.set(object.instance_id, source);
    if (source === "AI" && currentSuggestionId) {
        objectSuggestionIds.set(object.instance_id, currentSuggestionId);
    }
    track("icon_add", {
        target_id: object.instance_id,
        target_type: "icon",
        source,
        event_data: {
            icon_id: object.instance_id,
            asset_id: object.asset_id,
            asset_key: object.asset_key,
            category: object.category ?? null,
            initial_state: objectState(object),
            suggestion_id: source === "AI" ? currentSuggestionId : null,
        },
    });
    if (source === "AI" && currentSuggestionId) {
        track("ai_item_accepted", {
            target_id: object.instance_id,
            target_type: "icon",
            source: "AI",
            event_data: {
                suggestion_id: currentSuggestionId,
                asset_key: object.asset_key,
            },
        });
    }
    rememberCanvas();
});
window.addEventListener("puzzle-audiobook:canvas-object-transform", (event) => {
    handleObjectTransform(event.detail);
});
window.addEventListener("puzzle-audiobook:canvas-object-deleted", (event) => {
    const object = event.detail?.object;
    if (!object) return;
    track("icon_delete", {
        target_id: object.instance_id,
        target_type: "icon",
        source: objectSources.get(object.instance_id) || "manual",
        event_data: { state: objectState(object), asset_id: object.asset_id },
    });
    objectSources.delete(object.instance_id);
    objectSuggestionIds.delete(object.instance_id);
    rememberCanvas();
});
window.addEventListener("puzzle-audiobook:canvas-objects-replaced", (event) => {
    event.detail?.objects?.forEach((object) => {
        objectSources.set(object.instance_id, "AI");
        if (currentSuggestionId) objectSuggestionIds.set(object.instance_id, currentSuggestionId);
    });
    rememberCanvas();
    snapshot("ai_result_applied");
});
window.addEventListener("puzzle-audiobook:asset-suggestions", (event) => {
    suggestedAssetKeys.clear();
    event.detail?.assetKeys?.forEach((key) => suggestedAssetKeys.add(key));
});
window.addEventListener("puzzle-audiobook:audio-change", handleAudioChange);
window.addEventListener("puzzle-audiobook:timer-event", (event) => {
    track(event.detail?.eventType || "timer_event", { event_data: event.detail });
});
window.addEventListener("puzzle-audiobook:ai-event", (event) => {
    const detail = event.detail || {};
    if (
        detail.eventType === "ai_result_received"
        || detail.eventType === "ai_result_displayed"
    ) {
        currentSuggestionId = detail.suggestionId || null;
    } else if (detail.eventType === "ai_rejected") {
        currentSuggestionId = null;
    }
    track(detail.eventType || "ai_event", {
        target_id: detail.suggestionId || null,
        target_type: "ai_suggestion",
        source: "AI",
        event_data: detail,
    });
});
window.addEventListener("puzzle-audiobook:project-saved", (event) => {
    const canvas = getActiveCanvasSnapshot();
    const audio = getActiveAudioSnapshot();
    const icons = canvas?.objects || [];
    const clips = audioClips(audio).filter((clip) => clip.track_id !== "narration");
    track("page_submit", {
        target_type: "page",
        event_data: {
            project_id: event.detail?.projectId,
            submitted_at: event.detail?.savedAt || new Date().toISOString(),
            final_icon_count: icons.length,
            final_audio_count: clips.length,
            manual_icon_count: icons.filter(
                (icon) => objectSources.get(icon.instance_id) !== "AI",
            ).length,
            ai_icon_count: icons.filter(
                (icon) => objectSources.get(icon.instance_id) === "AI",
            ).length,
            manual_audio_count: clips.filter(
                (clip) => objectSources.get(clip.object_instance_id) !== "AI",
            ).length,
            ai_audio_count: clips.filter(
                (clip) => objectSources.get(clip.object_instance_id) === "AI",
            ).length,
            final_canvas_json: canvas,
        },
    });
    snapshot("page_submit", { project_id: event.detail?.projectId });
});
window.addEventListener("puzzle-audiobook:history-applied", (event) => {
    track(event.detail?.direction === "redo" ? "redo" : "undo", {
        target_type: "history",
        event_data: { operation_type: event.detail?.operationType || "state_change" },
    });
});
window.addEventListener("puzzle-audiobook:authenticated", (event) => {
    track("login_succeeded", {
        target_id: event.detail?.user?.id ?? null,
        target_type: "participant",
    });
});
window.addEventListener("puzzle-audiobook:session-ending", () => {
    track("session_ended", { target_type: "session" });
    persistQueue();
});

window.addEventListener("puzzle-audiobook:audio-transport", (event) => {
    const action = event.detail?.action;
    if (action === "play") {
        activePreviewStartedAt = new Date().toISOString();
        track("page_preview_start", {
            target_type: "page",
            event_data: {
                started_at: activePreviewStartedAt,
                timeline_position: event.detail?.position ?? 0,
            },
        });
    } else if (action === "pause" || action === "stop") {
        if (!activePreviewStartedAt) return;
        track("page_preview_end", {
            target_type: "page",
            event_data: {
                started_at: activePreviewStartedAt,
                ended_at: new Date().toISOString(),
                duration_ms: Date.now() - Date.parse(activePreviewStartedAt),
                action,
                timeline_position: event.detail?.position ?? null,
            },
        });
        activePreviewStartedAt = null;
    }
});

window.addEventListener("pagehide", () => {
    endCurrentPage("page_hide");
    persistQueue();
    flush({ beacon: true });
});
window.addEventListener("online", () => flush());
window.setInterval(() => flush(), FLUSH_INTERVAL);
track("session_started", { event_data: { user_agent: navigator.userAgent } });
