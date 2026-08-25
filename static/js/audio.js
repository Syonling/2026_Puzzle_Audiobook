import { t } from "./i18n.js?v=20260825-1";

const DEFAULT_DURATION = 15;
// 保留既有 ID 以兼容已保存项目；数组顺序就是界面与后端序列化顺序。
const TRACK_IDS = Object.freeze(["narration", "free", "effects"]);
const LOCKED_TRACK_ID = "narration";
const NARRATION_AUDIO_INSTANCE_ID = "story-step-narration";
const BACKGROUND_AUDIO_INSTANCE_ID = "canvas-background";
const FADE_PRESET_DURATION = 4;
const REVERB_PRESET_WET = 0.62;
const REVERB_PRESET_DECAY = 2.4;
const ECHO_PRESET_WET = 0.38;
const ECHO_PRESET_DELAY = 0.36;
const ECHO_PRESET_FEEDBACK = 0.32;

const timelineRoot = document.querySelector("[data-audio-timeline]");
const editor = document.querySelector("[data-audio-editor]");
const ruler = document.querySelector("[data-audio-ruler]");
const playhead = document.querySelector("[data-audio-playhead]");
const status = document.querySelector("[data-audio-status]");
const playButton = document.querySelector("[data-audio-play]");
const pauseButton = document.querySelector("[data-audio-pause]");
const stopButton = document.querySelector("[data-audio-stop]");
const effectSelection = document.querySelector("[data-audio-effect-selection]");
const effectButtons = [...document.querySelectorAll("[data-audio-effect]")];
const effectUndoButton = document.querySelector("[data-audio-effect-undo]");
const effectResetButton = document.querySelector("[data-audio-effect-reset]");
const backgroundVolumeControl = document.querySelector("[data-background-volume-control]");
const backgroundVolumeInput = document.querySelector("[data-background-volume]");
const backgroundVolumeOutput = document.querySelector("[data-background-volume-output]");
const backgroundVolumeNumberInput = document.querySelector("[data-background-volume-number]");
const backgroundVolumeUnit = document.querySelector("[data-background-volume-unit]");
const trackMuteButtons = [...document.querySelectorAll("[data-track-mute]")];
const objectAudioPicker = document.querySelector("[data-object-audio-picker]");
const objectAudioCurrent = document.querySelector("[data-object-audio-current]");
const objectAudioName = document.querySelector("[data-object-audio-name]");
const objectAudioOptions = document.querySelector("[data-object-audio-options]");
const objectAudioError = document.querySelector("[data-object-audio-error]");
const objectAudioEmpty = document.querySelector("[data-object-audio-empty]");
const assistantToolButtons = [...document.querySelectorAll("[data-assistant-tool]")];
const assistantToolPanels = [...document.querySelectorAll("[data-assistant-panel]")];

const audioCache = new Map();
const bufferCache = new Map();
const reverbImpulseCache = new Map();
const localizedAssetsByKey = new Map();
let activeContext = null;
let activeAudioKey = null;
let currentTime = 0;
let isPlaying = false;
let isPreparing = false;
let playbackRevision = 0;
let playbackStartedAt = 0;
let playbackStartPosition = 0;
let animationFrame = 0;
let audioContext = null;
let activeSources = [];
let activeClipNodes = new Map();
let playbackMasterGain = null;
const mutedTrackIds = new Set();
const pendingObjectTransforms = new Map();
const processedAIObjectResponses = new Set();
const processedAIBackgroundResponses = new Set();
let objectTransformFrame = 0;
let audioMutationRevision = 0;
let isAIPreviewLocked = false;
let selectedClipId = null;
let previousClipEditSnapshot = null;
let isEditingBackgroundVolume = false;
let isEditingBackgroundVolumeNumber = false;
let backgroundVolumeChanged = false;
let selectedCanvasObject = null;
let objectAudioChoiceRevision = 0;
let isChangingObjectAudio = false;

function createDefaultEffects() {
    return {
        fade_in: { enabled: false, duration: FADE_PRESET_DURATION },
        fade_out: { enabled: false, duration: FADE_PRESET_DURATION },
        reverb: { enabled: false, wet: REVERB_PRESET_WET, decay: REVERB_PRESET_DECAY },
        echo: {
            enabled: false,
            wet: ECHO_PRESET_WET,
            delay: ECHO_PRESET_DELAY,
            feedback: ECHO_PRESET_FEEDBACK,
        },
    };
}

function normalizeEffects(effects) {
    const defaults = createDefaultEffects();
    const source = effects && typeof effects === "object" ? effects : {};
    const echoSource = source.echo || (source.space?.enabled ? {
        enabled: true,
        wet: ECHO_PRESET_WET,
        delay: ECHO_PRESET_DELAY,
        feedback: ECHO_PRESET_FEEDBACK,
    } : {});
    const numberOrDefault = (value, fallback) => (
        Number.isFinite(Number(value)) ? Number(value) : fallback
    );
    return {
        fade_in: {
            enabled: source.fade_in?.enabled === true,
            duration: Math.min(5, Math.max(FADE_PRESET_DURATION, numberOrDefault(source.fade_in?.duration, defaults.fade_in.duration))),
        },
        fade_out: {
            enabled: source.fade_out?.enabled === true,
            duration: Math.min(5, Math.max(FADE_PRESET_DURATION, numberOrDefault(source.fade_out?.duration, defaults.fade_out.duration))),
        },
        reverb: {
            enabled: source.reverb?.enabled === true,
            wet: Math.min(1, Math.max(REVERB_PRESET_WET, numberOrDefault(source.reverb?.wet, defaults.reverb.wet))),
            decay: Math.min(4, Math.max(REVERB_PRESET_DECAY, numberOrDefault(source.reverb?.decay, defaults.reverb.decay))),
        },
        echo: {
            enabled: echoSource.enabled === true,
            wet: Math.min(0.7, Math.max(0, numberOrDefault(echoSource.wet, defaults.echo.wet))),
            delay: Math.min(1, Math.max(0.1, numberOrDefault(echoSource.delay, defaults.echo.delay))),
            feedback: Math.min(0.65, Math.max(0, numberOrDefault(echoSource.feedback, defaults.echo.feedback))),
        },
    };
}

function cloneEffects(effects) {
    return typeof structuredClone === "function"
        ? structuredClone(effects)
        : JSON.parse(JSON.stringify(effects));
}

function createInstanceId() {
    return globalThis.crypto?.randomUUID?.()
        || "clip-" + Date.now() + "-" + Math.random().toString(16).slice(2);
}

function createEmptyAudio() {
    return {
        duration: DEFAULT_DURATION,
        tracks: TRACK_IDS.map((id) => ({ id, clips: [] })),
    };
}

function normalizeClip(clip) {
    if (!clip || typeof clip !== "object" || !clip.audio_url) return null;
    const legacyDuration = Math.max(0.1, Number(clip.duration) || 1);
    const trimStart = Math.max(0, Number(clip.trim_start) || 0);
    const sourceDuration = Math.max(
        legacyDuration,
        trimStart + legacyDuration,
        Number(clip.source_duration) || 0,
    );
    const requestedTrimEnd = Number.isFinite(Number(clip.trim_end))
        ? Number(clip.trim_end)
        : trimStart + legacyDuration;
    const trimEnd = Math.min(
        sourceDuration,
        Math.max(trimStart + 0.1, requestedTrimEnd),
    );
    return {
        clip_id: clip.clip_id || createInstanceId(),
        object_instance_id: clip.object_instance_id || null,
        asset_id: clip.asset_id ?? null,
        asset_key: clip.asset_key || "",
        audio_key: clip.audio_key || null,
        name: clip.name || clip.asset_key || t("audio.clip"),
        audio_url: clip.audio_url,
        start_time: Math.max(0, Number(clip.start_time) || 0),
        source_duration: sourceDuration,
        trim_start: trimStart,
        trim_end: trimEnd,
        duration: trimEnd - trimStart,
        volume: Number.isFinite(Number(clip.volume))
            ? Math.min(2, Math.max(0, Number(clip.volume)))
            : 1,
        pan: Number.isFinite(Number(clip.pan))
            ? Math.min(1, Math.max(-1, Number(clip.pan)))
            : 0,
        effects: normalizeEffects(clip.effects),
    };
}

function normalizeAudio(audio) {
    const sourceTracks = Array.isArray(audio?.tracks) ? audio.tracks : [];
    const tracks = TRACK_IDS.map((id) => {
        const source = sourceTracks.find((track) => track?.id === id);
        return {
            id,
            clips: Array.isArray(source?.clips)
                ? source.clips.map(normalizeClip).filter(Boolean)
                : [],
        };
    });
    const maxEnd = tracks.flatMap((track) => track.clips).reduce(
        (maximum, clip) => Math.max(maximum, clip.start_time + clip.duration),
        0,
    );
    return {
        duration: Math.max(DEFAULT_DURATION, Number(audio?.duration) || 0, maxEnd),
        tracks,
    };
}

function getAudioKey(projectId, stepId) {
    return (projectId === null ? "draft" : projectId) + ":" + stepId;
}

function getActiveAudio() {
    return activeAudioKey ? audioCache.get(activeAudioKey) : null;
}

function getTrack(audio, trackId) {
    return audio?.tracks.find((track) => track.id === trackId);
}

function syncNarrationToStep(audio, context) {
    const track = getTrack(audio, LOCKED_TRACK_ID);
    if (!track) return;

    const audioUrl = context?.audioUrl || null;
    const existing = track.clips.find((clip) => clip.audio_url === audioUrl)
        || track.clips[0]
        || null;
    track.clips = [];
    if (!audioUrl) return;

    const keepExistingSettings = existing?.audio_url === audioUrl;
    const clip = normalizeClip({
        ...(keepExistingSettings ? existing : {}),
        clip_id: keepExistingSettings ? existing.clip_id : `narration-${context.stepId}`,
        object_instance_id: NARRATION_AUDIO_INSTANCE_ID,
        asset_key: "story_narration",
        name: context.sentence || t("audio.narration"),
        audio_url: audioUrl,
        start_time: 0,
        source_duration: keepExistingSettings ? existing.source_duration : 1,
        trim_start: keepExistingSettings ? existing.trim_start : 0,
        trim_end: keepExistingSettings ? existing.trim_end : 1,
        duration: keepExistingSettings ? existing.duration : 1,
        volume: keepExistingSettings ? existing.volume : 1,
        pan: 0,
    });
    if (!clip) return;
    track.clips.push(clip);

    const expectedKey = getAudioKey(context.projectId ?? null, context.stepId);
    loadAudioBuffer(audioUrl).then((buffer) => {
        if (activeAudioKey !== expectedKey || !track.clips.includes(clip)) return;
        const sourceDuration = Math.max(0.1, buffer.duration);
        clip.source_duration = sourceDuration;
        if (!keepExistingSettings) {
            clip.trim_start = 0;
            clip.trim_end = sourceDuration;
            clip.duration = sourceDuration;
        } else {
            clip.trim_start = Math.min(clip.trim_start, sourceDuration - 0.1);
            clip.trim_end = Math.min(sourceDuration, Math.max(clip.trim_start + 0.1, clip.trim_end));
            clip.duration = clip.trim_end - clip.trim_start;
        }
        const activeAudio = getActiveAudio();
        if (activeAudio) {
            activeAudio.duration = Math.max(
                DEFAULT_DURATION,
                ...activeAudio.tracks.flatMap((item) => item.clips)
                    .map((item) => item.start_time + item.duration),
            );
        }
        renderAudio();
    }).catch(() => {
        if (status && activeAudioKey === expectedKey) status.textContent = t("audio.fileFailed");
    });
}

function setAssistantTool(tool) {
    const nextTool = tool === "audio" ? "audio" : "ai";
    assistantToolButtons.forEach((button) => {
        const isActive = button.dataset.assistantTool === nextTool;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-selected", String(isActive));
        button.tabIndex = isActive ? 0 : -1;
    });
    assistantToolPanels.forEach((panel) => {
        panel.hidden = panel.dataset.assistantPanel !== nextTool;
    });
}

function getTrackDisplayName(trackId) {
    if (trackId === "narration") return t("audio.narration");
    if (trackId === "free") return t("audio.background");
    return t("audio.effects");
}

function updateTrackMuteButtons() {
    trackMuteButtons.forEach((button) => {
        const trackId = button.dataset.trackMute;
        const isMuted = mutedTrackIds.has(trackId);
        const trackName = getTrackDisplayName(trackId);
        button.innerHTML = isMuted
            ? '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 8h3l4-3v10l-4-3H3Z"/><path d="m13 8 4 4m0-4-4 4"/></svg>'
            : '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 8h3l4-3v10l-4-3H3Z"/><path d="M13 7.2a4 4 0 0 1 0 5.6"/><path d="M15 5.2a6.7 6.7 0 0 1 0 9.6"/></svg>';
        button.classList.toggle("is-muted", isMuted);
        button.setAttribute("aria-pressed", String(isMuted));
        button.setAttribute(
            "aria-label",
            t(isMuted ? "audio.unmuteTrack" : "audio.muteTrack", { track: trackName }),
        );
        button.closest("[data-audio-track]")?.classList.toggle("is-muted", isMuted);
    });
}

function setTrackMuted(trackId, muted) {
    if (!TRACK_IDS.includes(trackId)) return;
    if (muted) mutedTrackIds.add(trackId);
    else mutedTrackIds.delete(trackId);
    activeClipNodes.forEach((nodes) => {
        if (nodes.trackId === trackId && nodes.muteGain && audioContext) {
            nodes.muteGain.gain.setTargetAtTime(
                muted ? 0 : 1,
                audioContext.currentTime,
                0.015,
            );
        }
    });
    updateTrackMuteButtons();
}

function resetTrackMutes() {
    mutedTrackIds.clear();
    activeClipNodes.forEach((nodes) => {
        if (nodes.muteGain) {
            if (audioContext) {
                nodes.muteGain.gain.setTargetAtTime(1, audioContext.currentTime, 0.015);
            } else {
                nodes.muteGain.gain.value = 1;
            }
        }
    });
    updateTrackMuteButtons();
}

function getObjectClip(instanceId) {
    if (!instanceId) return null;
    return getActiveAudio()?.tracks.flatMap((track) => track.clips).find(
        (clip) => clip.object_instance_id === instanceId,
    ) || null;
}

function getAudioOptionsForObject(object) {
    if (!object?.asset_key) return [];
    const asset = localizedAssetsByKey.get(object.asset_key);
    const options = Array.isArray(asset?.audio_options)
        ? asset.audio_options.filter(
            (option) => option?.audio_key && option?.audio_url,
        ).sort((left, right) => Number(left.sort_order) - Number(right.sort_order))
        : [];
    if (options.length > 0) return options;
    const fallbackUrl = asset?.audio_url || object.audio_url;
    if (!fallbackUrl) return [];
    return [{
        audio_key: asset?.default_audio_key || object.selected_audio_key || `${object.asset_key}_default`,
        name: asset?.name || object.label || object.asset_key,
        audio_url: fallbackUrl,
        is_default: true,
        sort_order: 0,
    }];
}

function getSelectedObjectAudioKey(object, options) {
    const clip = getObjectClip(object?.instance_id);
    if (clip?.audio_key) return clip.audio_key;
    const matchingOption = options.find(
        (option) => option.audio_url === clip?.audio_url,
    );
    if (matchingOption) return matchingOption.audio_key;
    if (object?.selected_audio_key !== undefined) return object.selected_audio_key;
    if (clip?.audio_url) {
        return options.find((option) => option.audio_url === clip.audio_url)?.audio_key ?? null;
    }
    return null;
}

function createObjectAudioOption(option, selectedKey) {
    const isSilent = option === null;
    const audioKey = isSilent ? null : option.audio_key;
    const label = isSilent ? t("audioPicker.silent") : option.name;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "object-audio-option";
    button.classList.toggle("is-active", audioKey === selectedKey);
    button.disabled = isChangingObjectAudio || isAIPreviewLocked;
    button.setAttribute("aria-pressed", String(audioKey === selectedKey));
    button.title = label;

    const icon = document.createElement("span");
    icon.className = "object-audio-option-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = isSilent ? "🔇" : "🔊";
    const text = document.createElement("span");
    text.className = "object-audio-option-label";
    text.textContent = label;
    button.append(icon, text);
    button.addEventListener("click", () => changeSelectedObjectAudio(option));
    return button;
}

function renderObjectAudioPicker() {
    if (!objectAudioPicker) return;
    const object = selectedCanvasObject;
    const options = getAudioOptionsForObject(object);
    if (!object || options.length === 0) {
        objectAudioPicker.hidden = true;
        if (objectAudioEmpty) objectAudioEmpty.hidden = false;
        objectAudioOptions?.replaceChildren();
        return;
    }
    if (objectAudioEmpty) objectAudioEmpty.hidden = true;
    const asset = localizedAssetsByKey.get(object.asset_key);
    const iconName = asset?.name || object.label || object.asset_key;
    const selectedKey = getSelectedObjectAudioKey(object, options);
    const selectedOption = options.find((option) => option.audio_key === selectedKey);
    const selectedName = selectedOption?.name || t("audioPicker.silent");
    if (objectAudioCurrent) objectAudioCurrent.textContent = selectedName;
    if (objectAudioName) {
        objectAudioName.textContent = t("audioPicker.iconAndAudio", {
            icon: iconName,
            audio: selectedName,
        });
    }
    objectAudioOptions?.replaceChildren(
        ...options.map((option) => createObjectAudioOption(option, selectedKey)),
        createObjectAudioOption(null, selectedKey),
    );
    objectAudioPicker.hidden = false;
}

function setObjectAudioError(message = "") {
    if (!objectAudioError) return;
    objectAudioError.textContent = message;
    objectAudioError.hidden = !message;
}

function notifyCanvasObjectAudioChoice(object, option) {
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:canvas-object-audio-choice-applied", {
        detail: {
            context: activeContext ? { ...activeContext } : null,
            instanceId: object.instance_id,
            audioKey: option?.audio_key ?? null,
            audioUrl: option?.audio_url ?? null,
        },
    }));
}

async function changeSelectedObjectAudio(option) {
    const object = selectedCanvasObject;
    if (!object?.instance_id || isChangingObjectAudio || isAIPreviewLocked) return;
    const options = getAudioOptionsForObject(object);
    const selectedKey = getSelectedObjectAudioKey(object, options);
    const nextKey = option?.audio_key ?? null;
    if (selectedKey === nextKey) return;

    const revision = ++objectAudioChoiceRevision;
    isChangingObjectAudio = true;
    setObjectAudioError(option ? t("audioPicker.switching") : "");
    renderObjectAudioPicker();

    let buffer = null;
    try {
        if (option) buffer = await loadAudioBuffer(option.audio_url);
        if (
            revision !== objectAudioChoiceRevision
            || selectedCanvasObject?.instance_id !== object.instance_id
            || activeContext?.stepId !== object.selectionStepId
        ) return;

        const audio = getActiveAudio();
        const track = getTrack(audio, "effects");
        if (!audio || !track) return;
        notifyHistoryCheckpoint();
        haltPlayback();
        const existingClip = getObjectClip(object.instance_id);

        if (!option) {
            audio.tracks.forEach((audioTrack) => {
                audioTrack.clips = audioTrack.clips.filter(
                    (clip) => clip.object_instance_id !== object.instance_id,
                );
            });
        } else {
            const duration = Math.max(0.1, buffer.duration);
            const canvasWidth = document.querySelector("[data-canvas-paper]")
                ?.getBoundingClientRect().width;
            const derivedAudio = deriveAudioFromObject(object, canvasWidth);
            const clip = existingClip || normalizeClip({
                clip_id: createInstanceId(),
                object_instance_id: object.instance_id,
                asset_id: object.asset_id,
                asset_key: object.asset_key,
                start_time: track.clips.reduce(
                    (maximum, candidate) => Math.max(maximum, candidate.start_time + candidate.duration),
                    0,
                ),
                volume: derivedAudio.volume,
                pan: derivedAudio.pan,
                audio_url: option.audio_url,
                source_duration: duration,
                trim_start: 0,
                trim_end: duration,
                duration,
            });
            clip.audio_key = option.audio_key;
            clip.audio_url = option.audio_url;
            clip.name = option.name;
            clip.source_duration = duration;
            clip.trim_start = 0;
            clip.trim_end = duration;
            clip.duration = duration;
            clip.effects = createDefaultEffects();
            audio.tracks.forEach((audioTrack) => {
                audioTrack.clips = audioTrack.clips.filter(
                    (candidate) => candidate.object_instance_id !== object.instance_id,
                );
            });
            track.clips.push(clip);
        }

        selectedCanvasObject = {
            ...object,
            selected_audio_key: nextKey,
            audio_url: option?.audio_url ?? null,
        };
        previousClipEditSnapshot = null;
        if (existingClip?.clip_id === selectedClipId && !option) clearEffectsSelection();
        notifyCanvasObjectAudioChoice(object, option);
        renderAudio();
        notifyAudioChanged();
        setObjectAudioError();
    } catch {
        if (revision === objectAudioChoiceRevision) setObjectAudioError(t("audioPicker.failed"));
    } finally {
        if (revision === objectAudioChoiceRevision) {
            isChangingObjectAudio = false;
            renderObjectAudioPicker();
        }
    }
}

function getSelectedEditableClip() {
    if (!selectedClipId) return null;
    return getActiveAudio()?.tracks
        .filter((track) => track.id !== LOCKED_TRACK_ID)
        .flatMap((track) => track.clips)
        .find((clip) => clip.clip_id === selectedClipId) || null;
}

function getSelectedBackgroundClip() {
    const clip = getSelectedEditableClip();
    return clip?.object_instance_id === BACKGROUND_AUDIO_INSTANCE_ID ? clip : null;
}

function updateBackgroundVolumeControl() {
    const clip = getSelectedBackgroundClip();
    if (!backgroundVolumeControl) return;
    backgroundVolumeControl.hidden = !clip;
    if (!clip) {
        isEditingBackgroundVolumeNumber = false;
        if (backgroundVolumeNumberInput) backgroundVolumeNumberInput.hidden = true;
        if (backgroundVolumeUnit) backgroundVolumeUnit.hidden = true;
        if (backgroundVolumeOutput) backgroundVolumeOutput.hidden = false;
        return;
    }
    const volume = Math.min(2, Math.max(0, Number(clip.volume) || 0));
    if (backgroundVolumeInput && !isEditingBackgroundVolume) {
        backgroundVolumeInput.value = String(volume);
    }
    if (backgroundVolumeInput) backgroundVolumeInput.disabled = isAIPreviewLocked;
    if (backgroundVolumeNumberInput) {
        backgroundVolumeNumberInput.disabled = isAIPreviewLocked;
        if (!isEditingBackgroundVolumeNumber) {
            backgroundVolumeNumberInput.value = String(Math.round(volume * 100));
        }
    }
    if (backgroundVolumeOutput) {
        backgroundVolumeOutput.value = `${Math.round(volume * 100)}%`;
        backgroundVolumeOutput.textContent = backgroundVolumeOutput.value;
    }
}

function beginBackgroundVolumeNumberEdit() {
    const clip = getSelectedBackgroundClip();
    if (
        !clip
        || isAIPreviewLocked
        || !backgroundVolumeNumberInput
        || !backgroundVolumeOutput
    ) return;
    isEditingBackgroundVolumeNumber = true;
    backgroundVolumeNumberInput.value = String(
        Math.round(Math.min(2, Math.max(0, Number(clip.volume) || 0)) * 100),
    );
    backgroundVolumeOutput.hidden = true;
    backgroundVolumeNumberInput.hidden = false;
    if (backgroundVolumeUnit) backgroundVolumeUnit.hidden = false;
    backgroundVolumeNumberInput.focus();
    backgroundVolumeNumberInput.select();
}

function finishBackgroundVolumeNumberEdit({ commit = true } = {}) {
    if (!isEditingBackgroundVolumeNumber) return;
    if (commit && backgroundVolumeNumberInput) {
        const percentage = Number(backgroundVolumeNumberInput.value);
        if (Number.isFinite(percentage)) {
            setSelectedBackgroundVolume(
                Math.min(200, Math.max(0, percentage)) / 100,
            );
            commitBackgroundVolumeEdit();
        }
    }
    isEditingBackgroundVolumeNumber = false;
    if (backgroundVolumeNumberInput) backgroundVolumeNumberInput.hidden = true;
    if (backgroundVolumeUnit) backgroundVolumeUnit.hidden = true;
    if (backgroundVolumeOutput) backgroundVolumeOutput.hidden = false;
    updateBackgroundVolumeControl();
}

function beginBackgroundVolumeEdit() {
    const clip = getSelectedBackgroundClip();
    if (isEditingBackgroundVolume || !clip || isAIPreviewLocked) return;
    isEditingBackgroundVolume = true;
    backgroundVolumeChanged = false;
    previousClipEditSnapshot = {
        clipId: clip.clip_id,
        effects: cloneEffects(clip.effects),
        volume: clip.volume,
    };
    notifyHistoryCheckpoint();
}

function commitBackgroundVolumeEdit() {
    if (!isEditingBackgroundVolume) return;
    isEditingBackgroundVolume = false;
    const changed = backgroundVolumeChanged;
    backgroundVolumeChanged = false;
    if (changed) notifyAudioChanged();
    updateEffectControls();
}

function setSelectedBackgroundVolume(value) {
    const clip = getSelectedBackgroundClip();
    if (!clip || isAIPreviewLocked) return;
    const volume = Math.min(2, Math.max(0, Number(value) || 0));
    if (clip.volume === volume) return;
    if (!isEditingBackgroundVolume) beginBackgroundVolumeEdit();
    clip.volume = volume;
    backgroundVolumeChanged = true;
    const nodes = activeClipNodes.get(clip.clip_id);
    if (nodes && audioContext) {
        nodes.gain.gain.setTargetAtTime(volume, audioContext.currentTime, 0.015);
    }
    if (backgroundVolumeOutput) {
        backgroundVolumeOutput.value = `${Math.round(volume * 100)}%`;
        backgroundVolumeOutput.textContent = backgroundVolumeOutput.value;
    }
}

function updateEffectControls() {
    const clip = getSelectedEditableClip();
    if (!clip && selectedClipId) selectedClipId = null;
    const selectedClip = clip || null;
    if (effectSelection) {
        effectSelection.textContent = selectedClip
            ? (localizedAssetsByKey.get(selectedClip.asset_key)?.name || selectedClip.name)
            : t("audio.selectClip");
    }
    effectButtons.forEach((button) => {
        const effectName = button.dataset.audioEffect;
        button.disabled = !selectedClip || isAIPreviewLocked;
        button.classList.toggle(
            "is-active",
            Boolean(selectedClip?.effects?.[effectName]?.enabled),
        );
        button.setAttribute(
            "aria-pressed",
            String(Boolean(selectedClip?.effects?.[effectName]?.enabled)),
        );
    });
    if (effectUndoButton) {
        effectUndoButton.disabled =
            !selectedClip
            || !previousClipEditSnapshot
            || previousClipEditSnapshot.clipId !== selectedClip.clip_id
            || isAIPreviewLocked;
    }
    if (effectResetButton) {
        const hasEnabledEffect = Boolean(selectedClip) && Object.values(
            selectedClip.effects,
        ).some((effect) => effect.enabled);
        const canResetBackgroundVolume =
            selectedClip?.object_instance_id === BACKGROUND_AUDIO_INSTANCE_ID
            && selectedClip.volume !== 1;
        effectResetButton.disabled =
            !selectedClip
            || (!hasEnabledEffect && !canResetBackgroundVolume)
            || isAIPreviewLocked;
    }
    updateBackgroundVolumeControl();
}

function selectEditableClip(clipId) {
    commitBackgroundVolumeEdit();
    if (selectedClipId !== clipId) previousClipEditSnapshot = null;
    selectedClipId = clipId;
    document.querySelectorAll(".audio-clip").forEach((element) => {
        element.classList.toggle("is-selected", element.dataset.clipId === clipId);
    });
    updateEffectControls();
}

function mutateSelectedEffects(mutator) {
    const clip = getSelectedEditableClip();
    if (!clip || isAIPreviewLocked) return;
    previousClipEditSnapshot = {
        clipId: clip.clip_id,
        effects: cloneEffects(clip.effects),
        volume: clip.volume,
    };
    notifyHistoryCheckpoint();
    haltPlayback();
    mutator(clip.effects, clip);
    renderAudio();
    notifyAudioChanged();
}

function clearEffectsSelection() {
    commitBackgroundVolumeEdit();
    selectedClipId = null;
    previousClipEditSnapshot = null;
    updateEffectControls();
}

function clearObjectAudioSelection() {
    objectAudioChoiceRevision += 1;
    isChangingObjectAudio = false;
    selectedCanvasObject = null;
    setAssistantTool("ai");
    setObjectAudioError();
    renderObjectAudioPicker();
}

function getTimelineDuration(audio = getActiveAudio()) {
    if (!audio) return DEFAULT_DURATION;
    const maxEnd = audio.tracks.flatMap((track) => track.clips).reduce(
        (maximum, clip) => Math.max(maximum, clip.start_time + clip.duration),
        0,
    );
    audio.duration = Math.max(DEFAULT_DURATION, Math.ceil(maxEnd / 5) * 5);
    return audio.duration;
}

function serializeAudio(audio) {
    const normalized = normalizeAudio(audio);
    normalized.duration = getTimelineDuration(normalized);
    return normalized;
}

function formatTime(seconds) {
    const safeSeconds = Math.max(0, Number(seconds) || 0);
    const minutes = Math.floor(safeSeconds / 60);
    const remainder = Math.floor(safeSeconds % 60);
    return minutes + ":" + String(remainder).padStart(2, "0");
}

function notifyAudioChanged() {
    if (!activeContext) return;
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:audio-change", {
        detail: { ...activeContext },
    }));
}

function notifyHistoryCheckpoint() {
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:history-checkpoint"));
}

function renderRuler(duration) {
    if (!ruler) return;
    const interval = duration <= 20 ? 2 : duration <= 60 ? 5 : 10;
    const ticks = [];
    for (let second = 0; second <= duration; second += interval) {
        const tick = document.createElement("span");
        tick.className = "audio-time-tick";
        tick.style.left = (second / duration * 100) + "%";
        const label = document.createElement("span");
        label.textContent = t("audio.seconds", { value: second });
        tick.append(label);
        ticks.push(tick);
    }
    ruler.replaceChildren(...ticks);
}

function movePlayheadElement() {
    const lane = document.querySelector("[data-audio-lane=\"effects\"]");
    if (!playhead || !editor || !lane) return;
    const editorRect = editor.getBoundingClientRect();
    const laneRect = lane.getBoundingClientRect();
    const duration = getTimelineDuration();
    const ratio = Math.min(1, Math.max(0, currentTime / duration));
    playhead.style.left = (laneRect.left - editorRect.left + laneRect.width * ratio) + "px";
}

function createClipElement(clip, duration, trackId) {
    const displayName = localizedAssetsByKey.get(clip.asset_key)?.name || clip.name;
    const button = document.createElement("div");
    button.className = "audio-clip";
    button.tabIndex = 0;
    button.setAttribute("role", "button");
    button.dataset.clipId = clip.clip_id;
    const isLockedTrack = trackId === LOCKED_TRACK_ID;
    button.classList.toggle("is-track-locked", isLockedTrack);
    button.classList.toggle("is-selected", !isLockedTrack && clip.clip_id === selectedClipId);
    button.style.left = (clip.start_time / duration * 100) + "%";
    button.style.width = (clip.duration / duration * 100) + "%";
    button.title = t("audio.clipDetail", {
        name: displayName,
        duration: clip.duration.toFixed(1),
    });
    button.setAttribute("aria-label", isLockedTrack
        ? t("audio.fixedClip", { name: displayName })
        : t("audio.dragClip", { name: displayName }));
    if (!isLockedTrack) {
        button.addEventListener("pointerdown", (event) => {
            selectEditableClip(clip.clip_id);
            beginClipDrag(event, clip, button);
        });
        button.addEventListener("keydown", (event) => {
            if (event.key !== "Enter" && event.key !== " ") return;
            event.preventDefault();
            event.stopPropagation();
            selectEditableClip(clip.clip_id);
        });
    }
    const label = document.createElement("span");
    label.className = "audio-clip-name";
    label.textContent = displayName;
    const trimHandle = document.createElement("span");
    trimHandle.className = "audio-clip-trim-handle";
    trimHandle.setAttribute("role", "slider");
    trimHandle.setAttribute("aria-label", t("audio.trim"));
    trimHandle.setAttribute("aria-valuemin", "0.1");
    trimHandle.setAttribute("aria-valuemax", String(clip.source_duration));
    trimHandle.setAttribute("aria-valuenow", String(clip.duration));
    if (!isLockedTrack) {
        trimHandle.addEventListener("pointerdown", (event) => {
            beginTrimDrag(event, clip, button);
        });
    }
    if (isLockedTrack) button.append(trimHandle);
    else button.append(label, trimHandle);
    return button;
}

function updateTransport() {
    const hasClips = Boolean(getActiveAudio()?.tracks.some((track) => track.clips.length));
    if (playButton) playButton.disabled = !hasClips || isPlaying || isPreparing;
    if (pauseButton) pauseButton.disabled = !isPlaying || isPreparing;
    if (stopButton) stopButton.disabled = !hasClips || (!isPlaying && !isPreparing && currentTime === 0);
    if (status) {
        status.textContent = activeContext
            ? t("audio.stepStatus", { order: activeContext.stepOrder, time: formatTime(currentTime) })
            : t("audio.noStep", { time: formatTime(currentTime) });
    }
}

function renderAudio() {
    const audio = getActiveAudio();
    const duration = getTimelineDuration(audio);
    renderRuler(duration);
    TRACK_IDS.forEach((trackId) => {
        const layer = document.querySelector("[data-audio-clips=\"" + trackId + "\"]");
        const track = getTrack(audio, trackId);
        if (layer) layer.replaceChildren(...(track?.clips || []).map(
            (clip) => createClipElement(clip, duration, trackId),
        ));
    });
    if (timelineRoot) timelineRoot.classList.toggle("is-empty", !audio);
    updateTrackMuteButtons();
    updateEffectControls();
    updateTransport();
    requestAnimationFrame(movePlayheadElement);
}

function stopSources() {
    activeSources.forEach((source) => {
        try {
            source.stop();
        } catch {
            // 已停止的 AudioBufferSourceNode 无需再次处理。
        }
    });
    activeSources = [];
    activeClipNodes.clear();
    if (playbackMasterGain) {
        try {
            playbackMasterGain.gain.value = 0;
            playbackMasterGain.disconnect();
        } catch {
            // 已断开的总输出节点无需再次处理。
        }
        playbackMasterGain = null;
    }
}

function haltPlayback() {
    playbackRevision += 1;
    isPlaying = false;
    isPreparing = false;
    cancelAnimationFrame(animationFrame);
    stopSources();
}

function pausePlayback() {
    if (!isPlaying || !audioContext) return;
    currentTime = Math.min(
        getTimelineDuration(),
        playbackStartPosition + audioContext.currentTime - playbackStartedAt,
    );
    haltPlayback();
    renderAudio();
}

function stopPlayback() {
    haltPlayback();
    currentTime = 0;
    renderAudio();
}

function getWebAudioContext() {
    const Context = globalThis.AudioContext || globalThis.webkitAudioContext;
    if (!Context) throw new Error(t("audio.unsupported"));
    if (!audioContext) audioContext = new Context();
    return audioContext;
}

function loadAudioBuffer(url) {
    if (!bufferCache.has(url)) {
        const promise = fetch(url, { credentials: "same-origin" })
            .then((response) => {
                if (!response.ok) throw new Error(t("audio.fileFailed"));
                return response.arrayBuffer();
            })
            .then((buffer) => getWebAudioContext().decodeAudioData(buffer));
        bufferCache.set(url, promise);
    }
    return bufferCache.get(url);
}

function getReverbImpulse(context, decay) {
    const safeDecay = Math.min(4, Math.max(0.2, Number(decay) || 1.5));
    const cacheKey = `${context.sampleRate}:${safeDecay.toFixed(2)}`;
    if (reverbImpulseCache.has(cacheKey)) return reverbImpulseCache.get(cacheKey);
    const frameCount = Math.max(1, Math.floor(context.sampleRate * safeDecay));
    const impulse = context.createBuffer(2, frameCount, context.sampleRate);
    for (let channel = 0; channel < impulse.numberOfChannels; channel += 1) {
        const data = impulse.getChannelData(channel);
        for (let frame = 0; frame < frameCount; frame += 1) {
            const envelope = Math.pow(1 - frame / frameCount, 2.2);
            data[frame] = (Math.random() * 2 - 1) * envelope;
        }
    }
    reverbImpulseCache.set(cacheKey, impulse);
    return impulse;
}

function connectDryWetEffect(context, input, effectNode, wetAmount) {
    const wet = Math.min(1, Math.max(0, Number(wetAmount) || 0));
    const dryGain = context.createGain();
    const wetGain = context.createGain();
    const output = context.createGain();
    dryGain.gain.value = 1 - wet;
    wetGain.gain.value = wet;
    input.connect(dryGain).connect(output);
    input.connect(effectNode).connect(wetGain).connect(output);
    return output;
}

function connectEchoEffect(context, input, effect) {
    const output = context.createGain();
    const dryGain = context.createGain();
    const wetGain = context.createGain();
    const delay = context.createDelay(1);
    const feedback = context.createGain();
    const wet = Math.min(0.7, Math.max(0, Number(effect.wet) || 0));
    dryGain.gain.value = 1 - wet;
    wetGain.gain.value = wet;
    delay.delayTime.value = Math.min(1, Math.max(0.1, Number(effect.delay) || ECHO_PRESET_DELAY));
    feedback.gain.value = Math.min(
        0.65,
        Math.max(0, Number(effect.feedback) || ECHO_PRESET_FEEDBACK),
    );
    input.connect(dryGain).connect(output);
    input.connect(delay).connect(wetGain).connect(output);
    delay.connect(feedback).connect(delay);
    return output;
}

function getEnvelopeValue(clip, localTime) {
    const effects = clip.effects || createDefaultEffects();
    let value = 1;
    if (effects.fade_in.enabled) {
        const duration = Math.min(clip.duration, effects.fade_in.duration);
        value = Math.min(value, duration > 0 ? localTime / duration : 1);
    }
    if (effects.fade_out.enabled) {
        const duration = Math.min(clip.duration, effects.fade_out.duration);
        const remaining = clip.duration - localTime;
        value = Math.min(value, duration > 0 ? remaining / duration : 1);
    }
    return Math.min(1, Math.max(0, value));
}

function configureEnvelope(gainNode, clip, localOffset, when, available) {
    const effects = clip.effects || createDefaultEffects();
    if (!effects.fade_in.enabled && !effects.fade_out.enabled) {
        gainNode.gain.setValueAtTime(1, when);
        return;
    }
    const sampleCount = Math.max(2, Math.min(256, Math.ceil(available * 30)));
    const curve = new Float32Array(sampleCount);
    for (let index = 0; index < sampleCount; index += 1) {
        const progress = index / (sampleCount - 1);
        curve[index] = getEnvelopeValue(clip, localOffset + available * progress);
    }
    gainNode.gain.setValueCurveAtTime(curve, when, Math.max(0.001, available));
}

function buildClipEffectChain(context, source, clip, localOffset, when, available) {
    const effects = clip.effects || createDefaultEffects();
    const envelope = context.createGain();
    configureEnvelope(envelope, clip, localOffset, when, available);
    source.connect(envelope);
    let output = envelope;

    if (effects.reverb.enabled) {
        const convolver = context.createConvolver();
        convolver.buffer = getReverbImpulse(context, effects.reverb.decay);
        output = connectDryWetEffect(context, output, convolver, effects.reverb.wet);
    }
    if (effects.echo.enabled) {
        output = connectEchoEffect(context, output, effects.echo);
    }
    return output;
}

function animatePlayback(revision, startPosition) {
    if (!isPlaying || revision !== playbackRevision || !audioContext) return;
    currentTime = Math.min(
        getTimelineDuration(),
        startPosition + audioContext.currentTime - playbackStartedAt,
    );
    movePlayheadElement();
    updateTransport();
    if (currentTime >= getTimelineDuration()) {
        stopPlayback();
        return;
    }
    animationFrame = requestAnimationFrame(() => animatePlayback(revision, startPosition));
}

async function playTimeline() {
    const audio = getActiveAudio();
    const clipEntries = audio?.tracks.flatMap((track) => track.clips.map(
        (clip) => ({ clip, trackId: track.id }),
    )) || [];
    if (clipEntries.length === 0 || isPlaying || isPreparing) return;

    haltPlayback();
    const revision = playbackRevision;
    const startPosition = currentTime >= getTimelineDuration() ? 0 : currentTime;
    currentTime = startPosition;
    isPreparing = true;
    if (status) status.textContent = t("audio.preparing");
    updateTransport();

    try {
        const context = getWebAudioContext();
        await context.resume();
        const buffers = await Promise.all(clipEntries.map(
            ({ clip }) => loadAudioBuffer(clip.audio_url),
        ));
        if (revision !== playbackRevision) return;

        isPreparing = false;
        isPlaying = true;
        playbackStartedAt = context.currentTime;
        playbackStartPosition = startPosition;
        playbackMasterGain = context.createGain();
        playbackMasterGain.gain.value = 1;
        playbackMasterGain.connect(context.destination);
        clipEntries.forEach(({ clip, trackId }, index) => {
            const clipEnd = clip.start_time + clip.duration;
            if (clipEnd <= startPosition) return;
            const source = context.createBufferSource();
            const gain = context.createGain();
            const muteGain = context.createGain();
            const panner = typeof context.createStereoPanner === "function"
                ? context.createStereoPanner()
                : null;
            source.buffer = buffers[index];
            gain.gain.value = clip.volume;
            muteGain.gain.value = mutedTrackIds.has(trackId) ? 0 : 1;
            const delay = Math.max(0, clip.start_time - startPosition);
            const offset = Math.max(0, startPosition - clip.start_time);
            const sourceOffset = clip.trim_start + offset;
            const available = Math.min(
                clip.duration - offset,
                source.buffer.duration - sourceOffset,
            );
            if (available <= 0) return;
            const when = context.currentTime + delay;
            const effectOutput = buildClipEffectChain(
                context,
                source,
                clip,
                offset,
                when,
                available,
            );
            if (panner) {
                panner.pan.value = clip.pan;
                effectOutput.connect(gain).connect(panner).connect(muteGain).connect(playbackMasterGain);
            } else {
                effectOutput.connect(gain).connect(muteGain).connect(playbackMasterGain);
            }
            activeClipNodes.set(clip.clip_id, { gain, panner, muteGain, trackId });
            source.start(when, sourceOffset, available);
            activeSources.push(source);
        });
        updateTransport();
        animatePlayback(revision, startPosition);
    } catch (error) {
        haltPlayback();
        updateTransport();
        if (status) status.textContent = error.message || t("audio.playFailed");
    }
}

function setPlayheadFromClientX(clientX) {
    const lane = document.querySelector("[data-audio-lane=\"effects\"]");
    if (!lane) return;
    const rect = lane.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (clientX - rect.left) / rect.width));
    currentTime = ratio * getTimelineDuration();
    movePlayheadElement();
    updateTransport();
}

function beginPlayheadDrag(event) {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    haltPlayback();

    function onMove(pointerEvent) {
        setPlayheadFromClientX(pointerEvent.clientX);
    }
    function onEnd(pointerEvent) {
        setPlayheadFromClientX(pointerEvent.clientX);
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onEnd);
    }
    setPlayheadFromClientX(event.clientX);
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onEnd, { once: true });
}

function beginClipDrag(event, clip, element) {
    if (event.button !== 0 || isAIPreviewLocked) return;
    event.preventDefault();
    event.stopPropagation();
    haltPlayback();
    const lane = event.currentTarget.closest("[data-audio-lane]");
    if (!lane) return;
    const sourceTrackId = lane.dataset.audioLane;
    if (sourceTrackId === LOCKED_TRACK_ID) return;
    const requiredTrackId = clip.object_instance_id === BACKGROUND_AUDIO_INSTANCE_ID
        ? "free"
        : "effects";
    let targetTrackId = sourceTrackId;
    const duration = getTimelineDuration();
    const originalStart = clip.start_time;
    const startX = event.clientX;
    let changed = false;
    let historyCaptured = false;
    element.classList.add("is-dragging");

    function onMove(pointerEvent) {
        const hoveredLane = document.elementFromPoint(
            pointerEvent.clientX,
            pointerEvent.clientY,
        )?.closest("[data-audio-lane]");
        const eligibleLane = hoveredLane?.dataset.audioLane === requiredTrackId
            ? hoveredLane
            : null;
        if (hoveredLane && hoveredLane.dataset.audioLane !== requiredTrackId) {
            targetTrackId = sourceTrackId;
        }
        document.querySelectorAll("[data-audio-lane]").forEach((candidate) => {
            candidate.classList.toggle("is-clip-drop-target", candidate === eligibleLane);
        });
        if (eligibleLane) targetTrackId = eligibleLane.dataset.audioLane;
        const laneWidth = (eligibleLane || lane).getBoundingClientRect().width;
        const deltaTime = (pointerEvent.clientX - startX) / laneWidth * duration;
        const nextStart = Math.max(0, Math.min(duration - clip.duration, originalStart + deltaTime));
        if (!historyCaptured && nextStart !== originalStart) {
            notifyHistoryCheckpoint();
            historyCaptured = true;
        }
        changed = changed || nextStart !== originalStart;
        clip.start_time = nextStart;
        element.style.left = (nextStart / duration * 100) + "%";
    }
    function onEnd() {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onEnd);
        clip.start_time = Math.round(clip.start_time * 10) / 10;
        document.querySelectorAll("[data-audio-lane].is-clip-drop-target").forEach(
            (candidate) => candidate.classList.remove("is-clip-drop-target"),
        );
        if (targetTrackId !== sourceTrackId) {
            const audio = getActiveAudio();
            const sourceTrack = getTrack(audio, sourceTrackId);
            const targetTrack = getTrack(audio, targetTrackId);
            if (sourceTrack && targetTrack) {
                sourceTrack.clips = sourceTrack.clips.filter(
                    (candidate) => candidate.clip_id !== clip.clip_id,
                );
                targetTrack.clips.push(clip);
                changed = true;
            }
        }
        element.classList.remove("is-dragging");
        renderAudio();
        if (changed) notifyAudioChanged();
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onEnd, { once: true });
}

function beginTrimDrag(event, clip, element) {
    if (event.button !== 0 || isAIPreviewLocked) return;
    event.preventDefault();
    event.stopPropagation();
    haltPlayback();
    const lane = element.closest("[data-audio-lane]");
    if (!lane) return;
    if (lane.dataset.audioLane === LOCKED_TRACK_ID) return;
    const laneWidth = lane.getBoundingClientRect().width;
    const timelineDuration = getTimelineDuration();
    const originalTrimEnd = clip.trim_end;
    const startX = event.clientX;
    let changed = false;
    let historyCaptured = false;
    element.classList.add("is-trimming");

    function onMove(pointerEvent) {
        const deltaTime = (pointerEvent.clientX - startX) / laneWidth * timelineDuration;
        const nextTrimEnd = Math.min(
            clip.source_duration,
            Math.max(clip.trim_start + 0.1, originalTrimEnd + deltaTime),
        );
        if (!historyCaptured && nextTrimEnd !== originalTrimEnd) {
            notifyHistoryCheckpoint();
            historyCaptured = true;
        }
        changed = changed || nextTrimEnd !== originalTrimEnd;
        clip.trim_end = nextTrimEnd;
        clip.duration = nextTrimEnd - clip.trim_start;
        element.style.width = (clip.duration / timelineDuration * 100) + "%";
        const displayName = localizedAssetsByKey.get(clip.asset_key)?.name || clip.name;
        element.title = t("audio.clipDetail", {
            name: displayName,
            duration: clip.duration.toFixed(1),
        });
    }
    function onEnd() {
        window.removeEventListener("pointermove", onMove);
        window.removeEventListener("pointerup", onEnd);
        clip.trim_end = Math.min(
            clip.source_duration,
            Math.max(clip.trim_start + 0.1, Math.round(clip.trim_end * 10) / 10),
        );
        clip.duration = Math.max(0.1, clip.trim_end - clip.trim_start);
        element.classList.remove("is-trimming");
        renderAudio();
        if (changed) notifyAudioChanged();
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onEnd, { once: true });
}

function deriveAudioFromObject(object, canvasWidth) {
    const scale = Math.max(0.35, Number(object?.scale) || 1);
    const safeWidth = Math.max(1, Number(canvasWidth) || 1);
    const x = Math.min(safeWidth, Math.max(0, Number(object?.x) || 0));
    return {
        volume: Math.min(2, Math.max(0.5, 0.5 + (scale - 0.35) / (3 - 0.35) * 1.5)),
        pan: Math.min(1, Math.max(-1, x / safeWidth * 2 - 1)),
    };
}

function syncClipToObject(object, canvasWidth) {
    const audio = getActiveAudio();
    if (!audio || !object?.instance_id) return false;
    const derived = deriveAudioFromObject(object, canvasWidth);
    let changed = false;
    audio.tracks.forEach((track) => {
        track.clips.forEach((clip) => {
            if (clip.object_instance_id !== object.instance_id) return;
            changed = changed || clip.volume !== derived.volume || clip.pan !== derived.pan;
            clip.volume = derived.volume;
            clip.pan = derived.pan;
            const nodes = activeClipNodes.get(clip.clip_id);
            if (nodes && audioContext) {
                nodes.gain.gain.setTargetAtTime(clip.volume, audioContext.currentTime, 0.015);
                nodes.panner?.pan.setTargetAtTime(clip.pan, audioContext.currentTime, 0.015);
            }
        });
    });
    return changed;
}

function applyObjectTransform(detail) {
    if (!activeContext || detail?.context?.stepId !== activeContext.stepId) return;
    syncClipToObject(detail.object, detail.canvasWidth);
}

function scheduleObjectTransform(detail) {
    const instanceId = detail?.object?.instance_id;
    if (!instanceId) return;
    if (detail.final) {
        pendingObjectTransforms.delete(instanceId);
        applyObjectTransform(detail);
        return;
    }
    pendingObjectTransforms.set(instanceId, detail);
    if (objectTransformFrame) return;
    objectTransformFrame = requestAnimationFrame(() => {
        objectTransformFrame = 0;
        const transforms = [...pendingObjectTransforms.values()];
        pendingObjectTransforms.clear();
        transforms.forEach(applyObjectTransform);
    });
}

export function syncAudioToCanvasObjects(objects, canvasWidth) {
    if (!Array.isArray(objects)) return;
    let changed = false;
    objects.forEach((object) => {
        changed = syncClipToObject(object, canvasWidth) || changed;
    });
    if (changed) renderAudio();
}

async function handleCanvasObjectAdded(detail) {
    const object = detail?.object;
    if (!object?.audio_url || !activeContext || detail.context?.stepId !== activeContext.stepId) {
        return;
    }
    const audio = getActiveAudio();
    const track = getTrack(audio, detail.trackId || "effects");
    if (!audio || !track) return;
    const rawStartOffset = object.start_offset_seconds;
    const hasExplicitStartOffset =
        rawStartOffset !== null
        && rawStartOffset !== undefined
        && Number.isFinite(Number(rawStartOffset));
    const startTime = hasExplicitStartOffset
        ? Math.max(0, Number(rawStartOffset))
        : track.clips.reduce(
            (maximum, clip) => Math.max(maximum, clip.start_time + clip.duration),
            0,
        );
    const matchedAudioOption = getAudioOptionsForObject(object).find(
        (option) => option.audio_url === object.audio_url,
    );
    const clip = normalizeClip({
        clip_id: createInstanceId(),
        object_instance_id: object.instance_id,
        asset_id: object.asset_id,
        asset_key: object.asset_key,
        audio_key: object.selected_audio_key !== undefined
            ? object.selected_audio_key
            : matchedAudioOption?.audio_key ?? null,
        name: object.label || object.asset_key,
        audio_url: object.audio_url,
        start_time: startTime,
        source_duration: 1,
        trim_start: 0,
        trim_end: 1,
        duration: 1,
        effects: object.effects,
        ...(detail.audioProperties || deriveAudioFromObject(object, detail.canvasWidth)),
    });
    track.clips.push(clip);
    renderAudio();
    renderObjectAudioPicker();
    notifyAudioChanged();

    const expectedKey = activeAudioKey;
    const mutationRevision = audioMutationRevision;
    try {
        const buffer = await loadAudioBuffer(clip.audio_url);
        if (
            audioMutationRevision !== mutationRevision
            || activeAudioKey !== expectedKey
            || !track.clips.includes(clip)
        ) return;
        const previousEnd = clip.start_time + clip.duration;
        const durationDelta = Math.max(0.1, buffer.duration) - clip.duration;
        clip.source_duration = Math.max(0.1, buffer.duration);
        clip.trim_start = 0;
        clip.trim_end = clip.source_duration;
        clip.duration = Math.max(0.1, buffer.duration);
        if (durationDelta !== 0 && !hasExplicitStartOffset) {
            track.clips.forEach((followingClip) => {
                if (followingClip !== clip && followingClip.start_time >= previousEnd) {
                    followingClip.start_time = Math.max(0, followingClip.start_time + durationDelta);
                }
            });
        }
        renderAudio();
        renderObjectAudioPicker();
        notifyAudioChanged();
    } catch {
        if (status && activeAudioKey === expectedKey) status.textContent = t("audio.fileFailed");
    }
}

async function handleCanvasBackgroundChanged(detail) {
    if (!activeContext || detail.context?.stepId !== activeContext.stepId) return;
    const audio = getActiveAudio();
    if (!audio) return;
    if (detail.responseToken) {
        if (processedAIBackgroundResponses.has(detail.responseToken)) return;
        processedAIBackgroundResponses.add(detail.responseToken);
    }

    haltPlayback();
    currentTime = 0;
    let removedPrevious = false;
    audio.tracks.forEach((track) => {
        const originalLength = track.clips.length;
        track.clips = track.clips.filter(
            (clip) => clip.object_instance_id !== BACKGROUND_AUDIO_INSTANCE_ID,
        );
        removedPrevious = removedPrevious || track.clips.length !== originalLength;
    });

    const background = detail.background;
    if (background?.audio_url && background.audio_enabled !== false) {
        await handleCanvasObjectAdded({
            context: detail.context,
            object: {
                ...background,
                instance_id: BACKGROUND_AUDIO_INSTANCE_ID,
            },
            trackId: "free",
            audioProperties: { volume: 1, pan: 0 },
        });
    } else {
        renderAudio();
        if (removedPrevious) notifyAudioChanged();
    }
}

function handleCanvasObjectDeleted(detail) {
    if (!activeContext || detail.context?.stepId !== activeContext.stepId) return;
    if (selectedCanvasObject?.instance_id === detail.object?.instance_id) {
        clearObjectAudioSelection();
    }
    const audio = getActiveAudio();
    if (!audio) return;
    let changed = false;
    audio.tracks.forEach((track) => {
        const originalLength = track.clips.length;
        track.clips = track.clips.filter(
            (clip) => clip.object_instance_id !== detail.object?.instance_id,
        );
        changed = changed || track.clips.length !== originalLength;
    });
    if (changed) {
        haltPlayback();
        currentTime = 0;
        renderAudio();
        notifyAudioChanged();
    }
}

async function handleCanvasObjectsReplaced(detail) {
    if (!activeContext || detail.context?.stepId !== activeContext.stepId) return;
    clearObjectAudioSelection();
    const audio = getActiveAudio();
    if (!audio) return;
    if (detail.responseToken) {
        if (processedAIObjectResponses.has(detail.responseToken)) return;
        processedAIObjectResponses.add(detail.responseToken);
    }
    haltPlayback();
    currentTime = 0;
    audio.tracks.forEach((track) => {
        track.clips = track.clips.filter(
            (clip) => (
                !clip.object_instance_id
                || clip.object_instance_id === NARRATION_AUDIO_INSTANCE_ID
            ),
        );
    });
    renderAudio();

    const objects = Array.isArray(detail.objects) ? detail.objects : [];
    for (const object of objects) {
        if (object?.audio_url) {
            await handleCanvasObjectAdded({
                context: detail.context,
                canvasWidth: detail.canvasWidth,
                object,
            });
        }
    }
    await handleCanvasBackgroundChanged({
        context: detail.context,
        background: detail.background ?? null,
        responseToken: detail.responseToken,
    });
    notifyAudioChanged();
}

export function activateDraftAudio(context) {
    haltPlayback();
    resetTrackMutes();
    clearEffectsSelection();
    clearObjectAudioSelection();
    currentTime = 0;
    const key = getAudioKey(null, context.stepId);
    activeContext = { ...context, projectId: null };
    if (!audioCache.has(key)) audioCache.set(key, createEmptyAudio());
    activeAudioKey = key;
    syncNarrationToStep(audioCache.get(key), activeContext);
    renderAudio();
}

export function showRemoteAudioLoading(context, projectId) {
    haltPlayback();
    resetTrackMutes();
    clearEffectsSelection();
    clearObjectAudioSelection();
    currentTime = 0;
    activeContext = { ...context, projectId };
    activeAudioKey = getAudioKey(projectId, context.stepId);
    if (status) status.textContent = t("audio.loading");
    TRACK_IDS.forEach((trackId) => {
        document.querySelector("[data-audio-clips=\"" + trackId + "\"]")?.replaceChildren();
    });
    updateTransport();
    movePlayheadElement();
}

export function restoreRemoteAudio(context, projectId, audio) {
    resetTrackMutes();
    const key = getAudioKey(projectId, context.stepId);
    activeContext = { ...context, projectId };
    audioCache.set(key, normalizeAudio(audio));
    activeAudioKey = key;
    syncNarrationToStep(audioCache.get(key), activeContext);
    currentTime = 0;
    clearEffectsSelection();
    clearObjectAudioSelection();
    renderAudio();
}

export function storeRemoteAudio(context, projectId, audio, activate = false) {
    const key = getAudioKey(projectId, context.stepId);
    audioCache.set(key, normalizeAudio(audio));
    audioCache.delete(getAudioKey(null, context.stepId));
    if (activate) {
        activeContext = { ...context, projectId };
        activeAudioKey = key;
        currentTime = 0;
        renderAudio();
    }
}

export function getActiveAudioSnapshot() {
    const audio = getActiveAudio();
    return audio && activeContext ? serializeAudio(audio) : null;
}

export function restoreActiveAudioSnapshot(audio) {
    if (!activeAudioKey || !activeContext) return false;
    audioMutationRevision += 1;
    haltPlayback();
    cancelAnimationFrame(objectTransformFrame);
    objectTransformFrame = 0;
    pendingObjectTransforms.clear();
    previousClipEditSnapshot = null;
    clearObjectAudioSelection();
    currentTime = 0;
    audioCache.set(activeAudioKey, normalizeAudio(audio));
    renderAudio();
    return true;
}

export function setAudioAIPreviewLocked(locked) {
    isAIPreviewLocked = Boolean(locked);
    timelineRoot?.classList.toggle("is-ai-preview", isAIPreviewLocked);
    updateEffectControls();
    renderObjectAudioPicker();
}

export function discardActiveAudioChanges() {
    if (!activeAudioKey || !activeContext) return;
    haltPlayback();
    currentTime = 0;
    clearEffectsSelection();
    if (activeContext.projectId === null) audioCache.set(activeAudioKey, createEmptyAudio());
    else audioCache.delete(activeAudioKey);
}

export function clearAudioCache() {
    audioMutationRevision += 1;
    haltPlayback();
    cancelAnimationFrame(objectTransformFrame);
    objectTransformFrame = 0;
    pendingObjectTransforms.clear();
    processedAIObjectResponses.clear();
    processedAIBackgroundResponses.clear();
    currentTime = 0;
    audioCache.clear();
    activeContext = null;
    activeAudioKey = null;
    isAIPreviewLocked = false;
    resetTrackMutes();
    clearEffectsSelection();
    clearObjectAudioSelection();
    renderAudio();
}

playButton?.addEventListener("click", playTimeline);
pauseButton?.addEventListener("click", pausePlayback);
stopButton?.addEventListener("click", stopPlayback);
assistantToolButtons.forEach((button) => {
    button.addEventListener("click", () => setAssistantTool(button.dataset.assistantTool));
});
trackMuteButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const trackId = button.dataset.trackMute;
        setTrackMuted(trackId, !mutedTrackIds.has(trackId));
    });
});
effectButtons.forEach((button) => {
    button.addEventListener("click", () => {
        const effectName = button.dataset.audioEffect;
        mutateSelectedEffects((effects) => {
            const nextEnabled = !effects[effectName].enabled;
            effects[effectName].enabled = nextEnabled;
            if (nextEnabled && (effectName === "fade_in" || effectName === "fade_out")) {
                effects[effectName].duration = FADE_PRESET_DURATION;
            }
            if (nextEnabled && effectName === "reverb") {
                effects.reverb.wet = REVERB_PRESET_WET;
                effects.reverb.decay = REVERB_PRESET_DECAY;
            }
            if (nextEnabled && effectName === "echo") {
                effects.echo.wet = ECHO_PRESET_WET;
                effects.echo.delay = ECHO_PRESET_DELAY;
                effects.echo.feedback = ECHO_PRESET_FEEDBACK;
            }
        });
    });
});
effectUndoButton?.addEventListener("click", () => {
    const clip = getSelectedEditableClip();
    if (
        !clip
        || !previousClipEditSnapshot
        || previousClipEditSnapshot.clipId !== clip.clip_id
        || isAIPreviewLocked
    ) return;
    const snapshot = previousClipEditSnapshot;
    previousClipEditSnapshot = null;
    notifyHistoryCheckpoint();
    haltPlayback();
    clip.effects = normalizeEffects(snapshot.effects);
    if (
        clip.object_instance_id === BACKGROUND_AUDIO_INSTANCE_ID
        && Number.isFinite(Number(snapshot.volume))
    ) {
        clip.volume = Math.min(2, Math.max(0, Number(snapshot.volume)));
    }
    renderAudio();
    notifyAudioChanged();
});
effectResetButton?.addEventListener("click", () => {
    const clip = getSelectedEditableClip();
    if (!clip || isAIPreviewLocked) return;
    const hasEnabledEffect = Object.values(clip.effects).some((effect) => effect.enabled);
    const shouldResetBackgroundVolume =
        clip.object_instance_id === BACKGROUND_AUDIO_INSTANCE_ID
        && clip.volume !== 1;
    if (!hasEnabledEffect && !shouldResetBackgroundVolume) return;
    mutateSelectedEffects((effects, selectedClip) => {
        Object.values(effects).forEach((effect) => {
            effect.enabled = false;
        });
        if (selectedClip.object_instance_id === BACKGROUND_AUDIO_INSTANCE_ID) {
            selectedClip.volume = 1;
        }
    });
});
backgroundVolumeInput?.addEventListener("input", (event) => {
    setSelectedBackgroundVolume(event.currentTarget.value);
});
backgroundVolumeInput?.addEventListener("change", commitBackgroundVolumeEdit);
backgroundVolumeInput?.addEventListener("pointercancel", commitBackgroundVolumeEdit);
backgroundVolumeOutput?.addEventListener("dblclick", (event) => {
    event.preventDefault();
    beginBackgroundVolumeNumberEdit();
});
backgroundVolumeOutput?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    event.preventDefault();
    beginBackgroundVolumeNumberEdit();
});
backgroundVolumeNumberInput?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
        event.preventDefault();
        finishBackgroundVolumeNumberEdit();
    } else if (event.key === "Escape") {
        event.preventDefault();
        finishBackgroundVolumeNumberEdit({ commit: false });
        backgroundVolumeOutput?.focus();
    }
});
backgroundVolumeNumberInput?.addEventListener("blur", () => {
    finishBackgroundVolumeNumberEdit();
});
playhead?.addEventListener("pointerdown", beginPlayheadDrag);
editor?.addEventListener("pointerdown", (event) => {
    if (
        event.target.closest(".audio-clip")
        || event.target.closest("[data-audio-playhead]")
        || (!event.target.closest("[data-audio-lane]")
            && !event.target.closest("[data-audio-ruler]"))
    ) return;
    haltPlayback();
    setPlayheadFromClientX(event.clientX);
});
window.addEventListener("keydown", (event) => {
    if (event.code !== "Space" || event.repeat) return;
    const activeElement = document.activeElement;
    const tagName = activeElement?.tagName;
    if (
        tagName === "INPUT"
        || tagName === "TEXTAREA"
        || tagName === "SELECT"
        || tagName === "BUTTON"
        || activeElement?.isContentEditable
    ) return;
    if (!getActiveAudio()?.tracks.some((track) => track.clips.length)) return;
    event.preventDefault();
    if (isPlaying) {
        pausePlayback();
    } else if (isPreparing) {
        haltPlayback();
        renderAudio();
    } else {
        playTimeline();
    }
});
window.addEventListener("resize", movePlayheadElement);
window.addEventListener("puzzle-audiobook:canvas-object-transform", (event) => {
    scheduleObjectTransform(event.detail);
});
window.addEventListener("puzzle-audiobook:canvas-object-added", (event) => {
    handleCanvasObjectAdded(event.detail);
});
window.addEventListener("puzzle-audiobook:canvas-object-selected", (event) => {
    objectAudioChoiceRevision += 1;
    isChangingObjectAudio = false;
    setObjectAudioError();
    if (
        !event.detail?.object
        || !activeContext
        || event.detail?.context?.stepId !== activeContext.stepId
    ) {
        selectedCanvasObject = null;
    } else {
        selectedCanvasObject = {
            ...event.detail.object,
            selectionStepId: event.detail.context.stepId,
        };
    }
    renderObjectAudioPicker();
    setAssistantTool(
        selectedCanvasObject && getAudioOptionsForObject(selectedCanvasObject).length > 0
            ? "audio"
            : "ai",
    );
});
window.addEventListener("puzzle-audiobook:canvas-object-deleted", (event) => {
    handleCanvasObjectDeleted(event.detail);
});
window.addEventListener("puzzle-audiobook:canvas-background-changed", (event) => {
    handleCanvasBackgroundChanged(event.detail);
});
window.addEventListener("puzzle-audiobook:canvas-objects-replaced", (event) => {
    handleCanvasObjectsReplaced(event.detail);
});
window.addEventListener("puzzle-audiobook:reset", clearAudioCache);
window.addEventListener("puzzle-audiobook:localized-story", (event) => {
    if (!activeContext || event.detail?.stepId !== activeContext.stepId) return;
    activeContext = { ...activeContext, ...event.detail };
    const audio = getActiveAudio();
    if (!audio) return;
    syncNarrationToStep(audio, activeContext);
    renderAudio();
});
window.addEventListener("puzzle-audiobook:language-change", () => {
    renderAudio();
    renderObjectAudioPicker();
});
window.addEventListener("puzzle-audiobook:localized-assets", (event) => {
    const assets = Array.isArray(event.detail?.assets) ? event.detail.assets : [];
    localizedAssetsByKey.clear();
    assets.forEach((asset) => localizedAssetsByKey.set(asset.asset_key, { ...asset }));
    renderAudio();
    renderObjectAudioPicker();
});

setAssistantTool("ai");
renderAudio();
