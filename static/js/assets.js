import { request } from "./api.js?v=20260825-5";
import { t } from "./i18n.js?v=20260825-5";

const searchInput = document.querySelector("[data-asset-search]");
const categoryList = document.querySelector("[data-asset-categories]");
const assetGrid = document.querySelector("[data-asset-grid]");
const suggestionPanel = document.querySelector("[data-asset-suggestion-panel]");
const suggestionList = document.querySelector("[data-asset-suggestion-list]");
const pagination = document.querySelector("[data-asset-pagination]");

const ASSETS_PER_PAGE = 8;

let assets = [];
let selectedCategory = "";
let keyword = "";
let suggestedAssetKeys = new Set();
let assetRequestRevision = 0;
let currentPage = 1;

function createCategoryButton(category, label = category) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.assetCategory = category;
    button.textContent = category ? label : t("library.all");
    button.addEventListener("click", () => {
        selectedCategory = category;
        currentPage = 1;
        renderCategories();
        renderAssets();
    });
    return button;
}

function renderCategories() {
    const categories = new Map();
    assets.forEach((asset) => {
        if (!asset.category || categories.has(asset.category)) return;
        categories.set(
            asset.category,
            asset.category_translation || asset.category,
        );
    });
    const buttons = [
        createCategoryButton(""),
        ...[...categories].map(([category, label]) => (
            createCategoryButton(category, label)
        )),
    ];

    buttons.forEach((button) => {
        const isActive = button.dataset.assetCategory === selectedCategory;
        button.classList.toggle("is-active", isActive);
        button.setAttribute("aria-pressed", String(isActive));
    });
    categoryList.replaceChildren(...buttons);
}

function createAssetItem(asset, isSuggestion = false) {
    const item = document.createElement("article");
    item.className = "asset-item";
    item.dataset.assetId = String(asset.id);
    item.dataset.assetKey = asset.asset_key;
    item.classList.toggle("is-ai-suggested", isSuggestion);
    item.draggable = true;
    item.title = t("library.drag", { name: asset.name });
    if (asset.category === "background") {
        item.tabIndex = 0;
        item.setAttribute("role", "button");
        const activateBackground = () => {
            window.dispatchEvent(new CustomEvent("puzzle-audiobook:asset-activate", {
                detail: { asset: { ...asset } },
            }));
        };
        item.addEventListener("click", activateBackground);
        item.addEventListener("keydown", (event) => {
            if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                activateBackground();
            }
        });
    }
    item.addEventListener("dragstart", (event) => {
        const payload = JSON.stringify(asset);
        event.dataTransfer.effectAllowed = "copy";
        event.dataTransfer.setData(
            "application/x-puzzle-audiobook-asset",
            payload,
        );
        event.dataTransfer.setData("text/plain", payload);
        item.classList.add("is-dragging");
    });
    item.addEventListener("dragend", () => {
        item.classList.remove("is-dragging");
    });

    const icon = document.createElement("span");
    icon.className = "asset-icon";

    const image = document.createElement("img");
    image.src = asset.image_url;
    image.alt = "";
    image.draggable = false;
    image.addEventListener("error", () => {
        const fallback = document.createElement("span");
        fallback.className = "asset-icon-fallback";
        fallback.textContent = asset.name.slice(0, 1);
        icon.replaceChildren(fallback);
    }, { once: true });
    icon.append(image);

    const name = document.createElement("span");
    name.className = "asset-name";
    name.textContent = asset.name;

    item.append(icon, name);
    return item;
}

function getVisiblePageNumbers(pageCount) {
    if (pageCount <= 7) {
        return Array.from({ length: pageCount }, (_, index) => index + 1);
    }
    const pages = new Set([1, pageCount]);
    for (let page = currentPage - 2; page <= currentPage + 2; page += 1) {
        if (page > 1 && page < pageCount) pages.add(page);
    }
    const sortedPages = [...pages].sort((left, right) => left - right);
    const result = [];
    sortedPages.forEach((page, index) => {
        if (index > 0 && page - sortedPages[index - 1] > 1) result.push(null);
        result.push(page);
    });
    return result;
}

function renderPagination(pageCount) {
    if (!pagination || pageCount <= 1) {
        if (pagination) {
            pagination.hidden = true;
            pagination.replaceChildren();
        }
        return;
    }

    const controls = getVisiblePageNumbers(pageCount).map((page) => {
        if (page === null) {
            const ellipsis = document.createElement("span");
            ellipsis.className = "asset-page-ellipsis";
            ellipsis.textContent = "…";
            ellipsis.setAttribute("aria-hidden", "true");
            return ellipsis;
        }
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = String(page);
        button.classList.toggle("is-active", page === currentPage);
        button.setAttribute("aria-current", page === currentPage ? "page" : "false");
        button.setAttribute("aria-label", t("library.page", { page }));
        button.addEventListener("click", () => {
            if (page === currentPage) return;
            currentPage = page;
            renderAssets();
            assetGrid.scrollTop = 0;
        });
        return button;
    });
    pagination.replaceChildren(...controls);
    pagination.hidden = false;
}

function renderAssets() {
    const normalizedKeyword = keyword.trim().toLocaleLowerCase();
    const filteredAssets = assets.filter((asset) => {
        const matchesCategory =
            !selectedCategory || asset.category === selectedCategory;
        const matchesKeyword =
            !normalizedKeyword
            || asset.name.toLocaleLowerCase().includes(normalizedKeyword)
            || asset.asset_key.toLocaleLowerCase().includes(normalizedKeyword);
        return matchesCategory && matchesKeyword;
    });

    if (filteredAssets.length === 0) {
        const empty = document.createElement("p");
        empty.className = "asset-library-status";
        empty.textContent = assets.length === 0 ? t("library.empty") : t("library.noMatch");
        assetGrid.replaceChildren(empty);
        renderPagination(0);
        return;
    }

    const pageCount = Math.ceil(filteredAssets.length / ASSETS_PER_PAGE);
    currentPage = Math.min(Math.max(1, currentPage), pageCount);
    const pageStart = (currentPage - 1) * ASSETS_PER_PAGE;
    const pageAssets = filteredAssets.slice(pageStart, pageStart + ASSETS_PER_PAGE);
    assetGrid.replaceChildren(
        ...pageAssets.map((asset) => createAssetItem(asset)),
    );
    renderPagination(pageCount);
}

function renderSuggestedAssets() {
    if (suggestedAssetKeys.size === 0) {
        suggestionPanel.hidden = true;
        suggestionList.replaceChildren();
        return;
    }

    const assetsByKey = new Map(
        assets.map((asset) => [asset.asset_key, asset]),
    );
    const suggestedAssets = [...suggestedAssetKeys]
        .map((assetKey) => assetsByKey.get(assetKey))
        .filter(Boolean);

    if (suggestedAssets.length === 0) {
        suggestionPanel.hidden = true;
        suggestionList.replaceChildren();
        return;
    }

    suggestionList.replaceChildren(
        ...suggestedAssets.map((asset) => createAssetItem(asset, true)),
    );
    suggestionPanel.hidden = false;
}

async function loadAssets() {
    const revision = ++assetRequestRevision;
    try {
        const result = await request("/assets");
        if (revision !== assetRequestRevision) return;
        if (!Array.isArray(result)) throw new Error(t("library.invalid"));

        assets = result;
        currentPage = 1;
        window.dispatchEvent(new CustomEvent("puzzle-audiobook:localized-assets", {
            detail: { assets: assets.map((asset) => ({ ...asset })) },
        }));
        renderCategories();
        renderAssets();
        renderSuggestedAssets();
    } catch (error) {
        if (revision !== assetRequestRevision) return;
        const failed = document.createElement("p");
        failed.className = "asset-library-status is-error";
        failed.textContent = error.message || t("library.failed");
        assetGrid.replaceChildren(failed);
        renderPagination(0);
    }
}

searchInput?.addEventListener("input", (event) => {
    keyword = event.currentTarget.value;
    currentPage = 1;
    renderAssets();
});

window.addEventListener("puzzle-audiobook:asset-suggestions", (event) => {
    const assetKeys = Array.isArray(event.detail?.assetKeys)
        ? event.detail.assetKeys.filter((assetKey) => typeof assetKey === "string")
        : [];
    suggestedAssetKeys = new Set(assetKeys);
    renderSuggestedAssets();
});

document.querySelector("[data-asset-suggestion-close]")?.addEventListener("click", () => {
    suggestionPanel.hidden = true;
});

window.addEventListener("puzzle-audiobook:reset", () => {
    selectedCategory = "";
    keyword = "";
    currentPage = 1;
    suggestedAssetKeys.clear();
    if (searchInput) searchInput.value = "";
    renderCategories();
    renderAssets();
    renderSuggestedAssets();
});
window.addEventListener("puzzle-audiobook:language-change", loadAssets);

loadAssets();
