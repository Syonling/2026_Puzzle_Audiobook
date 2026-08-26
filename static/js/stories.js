import { request } from "./api.js?v=20260826-2";
import { t } from "./i18n.js?v=20260826-2";

const DEFAULT_STORY_ID = 1;
const DEFAULT_STORY_STATE = Object.freeze({
    stories: [],
    selectedStory: null,
    steps: [],
    currentStepOrder: null,
});

let storyState = createDefaultState();
let stepRequestId = 0;

function createDefaultState() {
    return {
        ...DEFAULT_STORY_STATE,
        stories: [],
        steps: [],
    };
}

function setImage(container, story) {
    container.replaceChildren();

    if (!story?.thumbnail_url) {
        const fallback = document.createElement("span");
        fallback.className = "book-cover-fallback";
        fallback.textContent = story?.title?.slice(0, 2) || t("story.fallback");
        container.append(fallback);
        return;
    }

    const image = document.createElement("img");
    image.src = story.thumbnail_url;
    image.alt = t("story.cover", { title: story.title });
    image.addEventListener("error", () => {
        const fallback = document.createElement("span");
        fallback.className = "book-cover-fallback";
        fallback.textContent = story.title.slice(0, 2);
        container.replaceChildren(fallback);
    }, { once: true });
    container.append(image);
}

function showStoryError(message) {
    const error = document.querySelector("[data-story-error]");
    if (!error) return;
    error.textContent = message;
    error.hidden = !message;
}

function renderCurrentStory() {
    const story = storyState.selectedStory;
    const book = document.querySelector("[data-current-book]");
    if (!book) return;

    book.disabled = storyState.stories.length === 0;
    document.querySelector("[data-current-story-title]").textContent =
        story?.title || t("story.none");
    document.querySelector("[data-current-story-description]").textContent =
        story?.description || t("story.noneDescription");
    setImage(document.querySelector("[data-current-book-cover]"), story);
}

function selectStep(stepOrder) {
    const step = storyState.steps.find((item) => item.step_order === stepOrder);
    if (!step) return;

    storyState.currentStepOrder = step.step_order;
    document.querySelector("[data-step-label]").textContent = t("story.step", { order: step.step_order });
    document.querySelector("[data-step-text]").textContent = step.sentence;

    document.querySelectorAll("[data-step-order]").forEach((button) => {
        const isCurrent = Number(button.dataset.stepOrder) === step.step_order;
        button.classList.toggle("is-current", isCurrent);
        button.setAttribute("aria-current", isCurrent ? "step" : "false");
    });

    window.dispatchEvent(new CustomEvent("puzzle-audiobook:step-change", {
        detail: {
            storyId: storyState.selectedStory.id,
            storyTitle: storyState.selectedStory.title,
            stepId: step.id,
            stepOrder: step.step_order,
            sentence: step.sentence,
            audioUrl: step.audio_url ?? null,
            totalSteps: storyState.steps.length,
        },
    }));
}

function renderSelectedStep(stepOrder = storyState.currentStepOrder) {
    const step = storyState.steps.find((item) => item.step_order === stepOrder)
        || storyState.steps[0];
    if (!step) return null;

    storyState.currentStepOrder = step.step_order;
    document.querySelector("[data-step-label]").textContent =
        t("story.step", { order: step.step_order });
    document.querySelector("[data-step-text]").textContent = step.sentence;
    document.querySelectorAll("[data-step-order]").forEach((button) => {
        const isCurrent = Number(button.dataset.stepOrder) === step.step_order;
        button.classList.toggle("is-current", isCurrent);
        button.setAttribute("aria-current", isCurrent ? "step" : "false");
    });
    return step;
}

function renderSteps() {
    const buttons = document.querySelector("[data-step-buttons]");
    if (!buttons) return;
    const keepDisabled = [...buttons.querySelectorAll("[data-step-order]")]
        .some((button) => button.disabled);

    buttons.replaceChildren();
    storyState.steps.forEach((step) => {
        const button = document.createElement("button");
        button.type = "button";
        button.dataset.stepOrder = String(step.step_order);
        button.disabled = keepDisabled;
        button.textContent = String(step.step_order);
        button.setAttribute("aria-label", t("story.stepView", { order: step.step_order }));
        button.addEventListener("click", () => {
            window.dispatchEvent(new CustomEvent("puzzle-audiobook:step-change-request", {
                detail: {
                    storyId: storyState.selectedStory.id,
                    stepOrder: step.step_order,
                },
            }));
        });
        buttons.append(button);
    });

    if (storyState.steps.length === 0) {
        storyState.currentStepOrder = null;
        document.querySelector("[data-step-label]").textContent = t("story.steps");
        document.querySelector("[data-step-text]").textContent = t("story.noSteps");
    }
}

async function selectStory(story) {
    const currentRequestId = ++stepRequestId;
    storyState.selectedStory = story;
    storyState.steps = [];
    storyState.currentStepOrder = null;
    renderCurrentStory();
    showStoryError("");
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:story-loading", {
        detail: {
            storyId: story.id,
            storyTitle: story.title,
        },
    }));

    document.querySelector("[data-step-label]").textContent = t("story.steps");
    document.querySelector("[data-step-text]").textContent = t("story.stepLoading");
    document.querySelector("[data-step-buttons]").replaceChildren();

    try {
        const steps = await request(`/stories/${story.id}/steps`);
        if (currentRequestId !== stepRequestId) return;
        storyState.steps = steps;
        renderSteps();
        renderBookshelf();
        window.dispatchEvent(new CustomEvent("puzzle-audiobook:story-ready", {
            detail: {
                storyId: story.id,
                storyTitle: story.title,
                steps: steps.map((step) => ({ ...step })),
            },
        }));
    } catch (error) {
        if (currentRequestId !== stepRequestId) return;
        document.querySelector("[data-step-text]").textContent = t("story.readFailed");
        showStoryError(error.message || t("story.contentLoadFailed"));
    }
}

function createBookshelfItem(story) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "bookshelf-book";
    button.classList.toggle("is-selected", story.id === storyState.selectedStory?.id);
    button.setAttribute("aria-label", t("story.choose", { title: story.title }));

    const cover = document.createElement("span");
    cover.className = "bookshelf-cover";
    setImage(cover, story);

    const title = document.createElement("strong");
    title.textContent = story.title;

    const description = document.createElement("span");
    description.textContent = story.description || t("story.open");

    button.append(cover, title, description);
    button.addEventListener("click", () => {
        document.querySelector("[data-bookshelf-dialog]").close();
        if (story.id !== storyState.selectedStory?.id) {
            // 切换故事前先让 projects.js 检查未保存更改，确认后再收到 select-story。
            window.dispatchEvent(new CustomEvent("puzzle-audiobook:story-change-request", {
                detail: { storyId: story.id },
            }));
        }
    });
    return button;
}

function renderBookshelf() {
    const grid = document.querySelector("[data-bookshelf-grid]");
    if (!grid) return;
    grid.replaceChildren(...storyState.stories.map(createBookshelfItem));
}

async function loadStories() {
    const book = document.querySelector("[data-current-book]");
    if (!book) return;

    try {
        storyState.stories = await request("/stories");
        renderBookshelf();

        const initialStory = storyState.stories.find((story) => story.id === DEFAULT_STORY_ID)
            || storyState.stories[0];

        if (initialStory) {
            await selectStory(initialStory);
        } else {
            renderCurrentStory();
            renderSteps();
        }
    } catch (error) {
        renderCurrentStory();
        document.querySelector("[data-step-text]").textContent = t("story.listReadFailed");
        showStoryError(error.message || t("story.listLoadFailed"));
    }
}

async function reloadLocalizedStories() {
    const selectedStoryId = storyState.selectedStory?.id;
    const selectedStepOrder = storyState.currentStepOrder;
    if (!selectedStoryId) {
        await loadStories();
        return;
    }

    const currentRequestId = ++stepRequestId;
    try {
        const stories = await request("/stories");
        if (currentRequestId !== stepRequestId) return;
        const selectedStory = stories.find((story) => story.id === selectedStoryId);
        if (!selectedStory) return;
        const steps = await request(`/stories/${selectedStoryId}/steps`);
        if (currentRequestId !== stepRequestId) return;

        storyState.stories = stories;
        storyState.selectedStory = selectedStory;
        storyState.steps = steps;
        storyState.currentStepOrder = selectedStepOrder;
        renderCurrentStory();
        renderBookshelf();
        renderSteps();

        const selectedStep = renderSelectedStep(selectedStepOrder);
        if (selectedStep) {
            window.dispatchEvent(new CustomEvent("puzzle-audiobook:localized-story", {
                detail: {
                    storyId: selectedStory.id,
                    storyTitle: selectedStory.title,
                    stepId: selectedStep.id,
                    stepOrder: selectedStep.step_order,
                    sentence: selectedStep.sentence,
                    audioUrl: selectedStep.audio_url ?? null,
                },
            }));
        }
        showStoryError("");
    } catch (error) {
        if (currentRequestId !== stepRequestId) return;
        renderCurrentStory();
        renderBookshelf();
        renderSteps();
        renderSelectedStep(selectedStepOrder);
        showStoryError(error.message || t("story.listLoadFailed"));
    }
}

export function resetStories() {
    stepRequestId += 1;
    storyState = createDefaultState();
    renderCurrentStory();
    renderSteps();
}

const bookshelfDialog = document.querySelector("[data-bookshelf-dialog]");

document.querySelector("[data-current-book]")?.addEventListener("click", () => {
    renderBookshelf();
    bookshelfDialog.showModal();
});
document.querySelector("[data-bookshelf-close]")?.addEventListener("click", () => {
    bookshelfDialog.close();
});
bookshelfDialog?.addEventListener("click", (event) => {
    if (event.target === bookshelfDialog) bookshelfDialog.close();
});

window.addEventListener("puzzle-audiobook:reset", resetStories);
window.addEventListener("puzzle-audiobook:language-change", reloadLocalizedStories);
window.addEventListener("puzzle-audiobook:select-step", (event) => {
    if (event.detail.storyId !== storyState.selectedStory?.id) return;
    selectStep(event.detail.stepOrder);
});
window.addEventListener("puzzle-audiobook:select-story", (event) => {
    const story = storyState.stories.find((item) => item.id === event.detail.storyId);
    if (!story || story.id === storyState.selectedStory?.id) return;
    window.dispatchEvent(new CustomEvent("puzzle-audiobook:new-story", {
        detail: {
            storyId: story.id,
            storyTitle: story.title,
        },
    }));
    selectStory(story);
});
loadStories();
