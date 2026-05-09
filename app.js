const workTypes = [
  { id: "concrete", label: "土間" },
  { id: "turf", label: "人工芝" },
  { id: "fence", label: "フェンス" },
  { id: "carport", label: "カーポート" },
  { id: "deck", label: "ウッドデッキ" },
  { id: "plants", label: "植栽" },
];

const optionLabels = {
  color: {
    natural: "ナチュラル",
    gray: "グレー系",
    dark: "ダーク系",
    green: "グリーン系",
    white: "ホワイト系",
  },
  size: {
    compact: "コンパクト",
    standard: "標準",
    wide: "広め",
  },
  height: {
    low: "低め",
    middle: "標準",
    high: "高め",
  },
  mood: {
    modern: "モダン",
    warm: "あたたかい",
    simple: "シンプル",
    luxury: "上質",
    japanese: "和風",
  },
};

const palette = {
  natural: {
    concrete: "#d8d2c4",
    turf: "#5e9362",
    fence: "#8a6a4b",
    carport: "#c8d0d2",
    deck: "#9a6844",
    plants: "#477747",
  },
  gray: {
    concrete: "#c4c8c7",
    turf: "#69826a",
    fence: "#6d7373",
    carport: "#b9c0c1",
    deck: "#8a8d88",
    plants: "#577b55",
  },
  dark: {
    concrete: "#777b78",
    turf: "#466b46",
    fence: "#2c3431",
    carport: "#3b4445",
    deck: "#4a3429",
    plants: "#3d643f",
  },
  green: {
    concrete: "#c8d2c5",
    turf: "#3d9951",
    fence: "#5d765c",
    carport: "#aebcb7",
    deck: "#80664d",
    plants: "#2f7f42",
  },
  white: {
    concrete: "#ecebe5",
    turf: "#77a772",
    fence: "#f4f0e8",
    carport: "#eef2f1",
    deck: "#c79a70",
    plants: "#5a8752",
  },
};

const layerDefaults = {
  concrete: { x: 0.5, y: 0.78, w: 0.72, h: 0.26, scale: 1, rotation: 0, depth: 1 },
  turf: { x: 0.32, y: 0.78, w: 0.55, h: 0.2, scale: 1, rotation: 0, depth: 1 },
  fence: { x: 0.5, y: 0.47, w: 0.88, h: 0.18, scale: 1, rotation: 0, depth: 1 },
  carport: { x: 0.64, y: 0.45, w: 0.5, h: 0.25, scale: 1, rotation: 0, depth: 1 },
  deck: { x: 0.68, y: 0.78, w: 0.43, h: 0.16, scale: 1, rotation: 0, depth: 1 },
  plants: { x: 0.28, y: 0.72, w: 0.42, h: 0.22, scale: 1, rotation: 0, depth: 1 },
};

const state = {
  photoFile: null,
  photoUrl: "",
  baseImage: null,
  selectedWork: new Set(),
  options: {
    color: "natural",
    size: "standard",
    height: "middle",
    mood: "warm",
  },
  layers: [],
  selectedLayerId: "",
  removalMode: false,
  removalMaskPaths: [],
  activeMaskPath: null,
  removalCanvas: null,
  brushSize: 46,
  editorReady: false,
  isGenerating: false,
};

const gesture = {
  pointers: new Map(),
  mode: "",
  start: null,
};

const elements = {
  form: document.querySelector("#image-form"),
  photoInput: document.querySelector("#photo-input"),
  uploadTitle: document.querySelector("#upload-title"),
  uploadHelper: document.querySelector("#upload-helper"),
  workItems: document.querySelector("#work-items"),
  colorSelect: document.querySelector("#color-select"),
  sizeSelect: document.querySelector("#size-select"),
  heightSelect: document.querySelector("#height-select"),
  moodSelect: document.querySelector("#mood-select"),
  generateButton: document.querySelector("#generate-button"),
  beforeFrame: document.querySelector("#before-frame"),
  afterFrame: document.querySelector("#after-frame"),
  beforeImage: document.querySelector("#before-image"),
  editorCanvas: document.querySelector("#editor-canvas"),
  resultSummary: document.querySelector("#result-summary"),
  editPanel: document.querySelector("#edit-panel"),
  layerList: document.querySelector("#layer-list"),
  layerBackButton: document.querySelector("#layer-back-button"),
  layerFrontButton: document.querySelector("#layer-front-button"),
  deleteLayerButton: document.querySelector("#delete-layer-button"),
  scaleRange: document.querySelector("#scale-range"),
  rotationRange: document.querySelector("#rotation-range"),
  depthRange: document.querySelector("#depth-range"),
  maskModeButton: document.querySelector("#mask-mode-button"),
  removePreviewButton: document.querySelector("#remove-preview-button"),
  clearMaskButton: document.querySelector("#clear-mask-button"),
  brushRange: document.querySelector("#brush-range"),
};

const imageGenerator = {
  apiEndpoint: "/api/generate-image",
  async generate(input) {
    return createEditableMockLayers(input);
  },
  async generateWithApi(payload) {
    const response = await fetch(this.apiEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "AI画像生成に失敗しました。");
    }

    return data.imageUrl;
  },
};

const removalGenerator = {
  apiEndpoint: "/api/inpaint-removal",
  instruction: "選択範囲の既存外構物を自然に撤去し、背景を周囲になじませる",
  async generate(input) {
    return generateMockRemoval(input);
  },
  async generateWithApi(input) {
    const response = await fetch(this.apiEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "撤去イメージ生成に失敗しました。");
    }

    return data.imageUrl;
  },
};

function renderWorkOptions() {
  elements.workItems.innerHTML = workTypes
    .map((item) => `
      <label class="work-option">
        <input type="checkbox" name="workType" value="${item.id}">
        <span>${item.label}</span>
      </label>
    `)
    .join("");
}

function getWorkLabel(type) {
  return workTypes.find((item) => item.id === type)?.label || type;
}

function getSelectedLayer() {
  return state.layers.find((layer) => layer.id === state.selectedLayerId) || null;
}

function getSelectedWorkLabels() {
  return workTypes
    .filter((item) => state.selectedWork.has(item.id))
    .map((item) => item.label);
}

function syncControls() {
  elements.generateButton.disabled =
    !state.photoUrl || state.isGenerating;

  if (state.photoUrl) {
    elements.beforeFrame.classList.remove("empty");
    elements.beforeImage.src = state.photoUrl;
  } else {
    elements.beforeFrame.classList.add("empty");
    elements.beforeImage.removeAttribute("src");
  }

  if (state.editorReady) {
    elements.afterFrame.classList.remove("empty");
    elements.editPanel.classList.remove("hidden");
  } else {
    elements.afterFrame.classList.add("empty");
    elements.editPanel.classList.add("hidden");
  }

  const labels = getSelectedWorkLabels();
  const hasSelection = labels.length > 0;
  const optionText = [
    optionLabels.color[state.options.color],
    optionLabels.size[state.options.size],
    optionLabels.height[state.options.height],
    optionLabels.mood[state.options.mood],
  ].join(" / ");

  if (state.isGenerating) {
    elements.generateButton.textContent = state.removalMode ? "撤去イメージ作成中..." : "編集モードを作成中...";
    elements.resultSummary.textContent = state.removalMode
      ? "選択範囲を周囲になじませるモック処理をしています。"
      : "写真上に編集できる外構要素を配置しています。";
  } else {
    elements.generateButton.textContent = state.editorReady
      ? "選択内容で編集を作り直す"
      : "配置調整・撤去モードを開始";
    elements.resultSummary.textContent = state.editorReady
      ? getEditorSummary()
      : hasSelection
        ? `${labels.join("、")} / ${optionText}`
        : "写真を選択すると、撤去範囲の作成や配置調整を開始できます。";
  }

  renderLayerList();
  syncRangeControls();
  syncRemovalControls();
}

function getEditorSummary() {
  if (state.removalMode) {
    return "撤去範囲を指でなぞって指定中です。赤い範囲が撤去対象です。";
  }

  if (state.layers.length > 0) {
    return `配置中: ${state.layers.map((layer) => layer.label).join("、")}`;
  }

  return "撤去範囲を描くと、既存物の撤去イメージを確認できます。";
}

function syncRangeControls() {
  const layer = getSelectedLayer();
  const disabled = !layer;

  elements.scaleRange.disabled = disabled;
  elements.rotationRange.disabled = disabled;
  elements.depthRange.disabled = disabled;
  elements.layerBackButton.disabled = disabled;
  elements.layerFrontButton.disabled = disabled;
  elements.deleteLayerButton.disabled = disabled;

  if (!layer) {
    elements.scaleRange.value = 100;
    elements.rotationRange.value = 0;
    elements.depthRange.value = 100;
    return;
  }

  elements.scaleRange.value = Math.round(layer.scale * 100);
  elements.rotationRange.value = Math.round((layer.rotation * 180) / Math.PI);
  elements.depthRange.value = Math.round(layer.depth * 100);
}

function syncRemovalControls() {
  const hasMask = state.removalMaskPaths.length > 0 || Boolean(state.activeMaskPath);

  elements.maskModeButton.disabled = !state.editorReady || state.isGenerating;
  elements.removePreviewButton.disabled = !state.editorReady || !hasMask || state.isGenerating;
  elements.clearMaskButton.disabled = !state.editorReady || (!hasMask && !state.removalCanvas) || state.isGenerating;
  elements.brushRange.disabled = !state.editorReady || state.isGenerating;
  elements.brushRange.value = state.brushSize;
  elements.maskModeButton.classList.toggle("active", state.removalMode);
}

function renderLayerList() {
  if (!state.editorReady) {
    elements.layerList.innerHTML = "";
    return;
  }

  elements.layerList.innerHTML = state.layers
    .slice()
    .sort((a, b) => b.z - a.z)
    .map((layer) => `
      <button
        type="button"
        class="layer-chip ${layer.id === state.selectedLayerId ? "active" : ""}"
        data-layer-id="${layer.id}"
      >
        ${getWorkLabel(layer.type)}
      </button>
    `)
    .join("");
}

function setPhoto(file) {
  if (state.photoUrl) {
    URL.revokeObjectURL(state.photoUrl);
  }

  state.photoFile = file;
  state.photoUrl = file ? URL.createObjectURL(file) : "";
  state.baseImage = null;
  state.layers = [];
  state.selectedLayerId = "";
  state.removalMode = false;
  state.removalMaskPaths = [];
  state.activeMaskPath = null;
  state.removalCanvas = null;
  state.editorReady = false;

  elements.uploadTitle.textContent = file ? "写真を選択済み" : "現場写真を選択";
  elements.uploadHelper.textContent = file?.name || "スマホのカメラロールから選択できます";
  syncControls();
  renderEditor();
}

function updateOption(name, value) {
  state.options[name] = value;

  if (state.editorReady) {
    state.layers.forEach((layer) => {
      layer.color = getLayerColor(layer.type);
    });
    renderEditor();
  }

  syncControls();
}

function updateWorkSelection(input) {
  if (input.checked) {
    state.selectedWork.add(input.value);
  } else {
    state.selectedWork.delete(input.value);
  }

  syncControls();
}

function clearRemovalMask() {
  state.removalMaskPaths = [];
  state.activeMaskPath = null;
  state.removalCanvas = null;
  state.removalMode = false;
  renderEditor();
  syncControls();
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("写真を読み込めませんでした。"));
    image.src = src;
  });
}

function getScale(size) {
  return { compact: 0.82, standard: 1, wide: 1.16 }[size] || 1;
}

function getHeightScale(height) {
  return { low: 0.78, middle: 1, high: 1.22 }[height] || 1;
}

function getLayerColor(type) {
  return (palette[state.options.color] || palette.natural)[type];
}

function createEditableMockLayers(input) {
  const sizeScale = getScale(input.options.size);
  const heightScale = getHeightScale(input.options.height);

  return Array.from(input.selectedWork).map((type, index) => {
    const defaults = layerDefaults[type];
    const scale = type === "fence" || type === "carport"
      ? sizeScale * heightScale
      : sizeScale;

    return {
      id: `${type}-${Date.now()}-${index}`,
      type,
      label: getWorkLabel(type),
      x: defaults.x,
      y: defaults.y,
      w: defaults.w,
      h: defaults.h,
      scale: defaults.scale * scale,
      rotation: defaults.rotation,
      depth: defaults.depth,
      color: getLayerColor(type),
      z: index + 1,
    };
  });
}

async function startEditorMode() {
  state.isGenerating = true;
  syncControls();

  try {
    state.baseImage = await loadImage(state.photoUrl);
    state.layers = await imageGenerator.generate({
      photoFile: state.photoFile,
      photoUrl: state.photoUrl,
      selectedWork: new Set(state.selectedWork),
      options: { ...state.options },
    });
    state.selectedLayerId = state.layers[state.layers.length - 1]?.id || "";
    state.removalMode = state.layers.length === 0;
    state.removalMaskPaths = [];
    state.activeMaskPath = null;
    state.removalCanvas = null;
    state.editorReady = true;
    setupCanvasSize();
    renderEditor();
  } catch (error) {
    elements.resultSummary.textContent = error.message;
  } finally {
    state.isGenerating = false;
    syncControls();
  }
}

function setupCanvasSize() {
  if (!state.baseImage) return;

  const canvas = elements.editorCanvas;
  const maxSide = 1280;
  const ratio = Math.min(1, maxSide / Math.max(state.baseImage.naturalWidth, state.baseImage.naturalHeight));
  canvas.width = Math.round(state.baseImage.naturalWidth * ratio);
  canvas.height = Math.round(state.baseImage.naturalHeight * ratio);
}

function renderEditor() {
  const canvas = elements.editorCanvas;
  const ctx = canvas.getContext("2d");

  if (!state.editorReady || !state.baseImage) {
    ctx.clearRect(0, 0, canvas.width || 1, canvas.height || 1);
    return;
  }

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.drawImage(state.removalCanvas || state.baseImage, 0, 0, canvas.width, canvas.height);
  applyMoodTint(ctx, canvas, state.options.mood);

  state.layers
    .slice()
    .sort((a, b) => a.z - b.z)
    .forEach((layer) => {
      drawLayer(ctx, canvas, layer);
    });

  drawRemovalMask(ctx, canvas);
  drawEditorBadge(ctx, canvas);
}

function applyMoodTint(ctx, canvas, mood) {
  const tintMap = {
    modern: "rgba(210, 226, 232, 0.14)",
    warm: "rgba(235, 210, 176, 0.16)",
    simple: "rgba(245, 245, 238, 0.12)",
    luxury: "rgba(30, 30, 28, 0.10)",
    japanese: "rgba(205, 221, 196, 0.16)",
  };

  ctx.fillStyle = tintMap[mood] || tintMap.warm;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
}

function drawLayer(ctx, canvas, layer) {
  const w = canvas.width * layer.w;
  const h = canvas.height * layer.h;
  const x = canvas.width * layer.x;
  const y = canvas.height * layer.y;
  const selected = layer.id === state.selectedLayerId;

  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(layer.rotation);
  ctx.scale(layer.scale * layer.depth, layer.scale * layer.depth);

  if (layer.type === "concrete") drawConcrete(ctx, w, h, layer.color);
  if (layer.type === "turf") drawTurf(ctx, w, h, layer.color);
  if (layer.type === "fence") drawFence(ctx, w, h, layer.color);
  if (layer.type === "carport") drawCarport(ctx, w, h, layer.color);
  if (layer.type === "deck") drawDeck(ctx, w, h, layer.color);
  if (layer.type === "plants") drawPlants(ctx, w, h, layer.color);

  if (selected) {
    ctx.strokeStyle = "rgba(255, 255, 255, 0.95)";
    ctx.lineWidth = 3 / Math.max(0.4, layer.scale * layer.depth);
    ctx.setLineDash([8, 5]);
    ctx.strokeRect(-w / 2, -h / 2, w, h);
  }

  ctx.restore();
}

function withAlpha(hex, alpha) {
  const clean = hex.replace("#", "");
  const r = Number.parseInt(clean.slice(0, 2), 16);
  const g = Number.parseInt(clean.slice(2, 4), 16);
  const b = Number.parseInt(clean.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function roundRect(ctx, x, y, w, h, radius) {
  const r = Math.min(radius, Math.abs(w) / 2, Math.abs(h) / 2);
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function drawConcrete(ctx, w, h, color) {
  ctx.fillStyle = withAlpha(color, 0.78);
  ctx.beginPath();
  ctx.moveTo(-w * 0.42, -h * 0.5);
  ctx.lineTo(w * 0.42, -h * 0.5);
  ctx.lineTo(w * 0.5, h * 0.5);
  ctx.lineTo(-w * 0.5, h * 0.5);
  ctx.closePath();
  ctx.fill();

  ctx.strokeStyle = "rgba(255,255,255,0.38)";
  ctx.lineWidth = Math.max(1.5, w * 0.004);
  for (let i = -1; i <= 1; i += 1) {
    ctx.beginPath();
    ctx.moveTo(w * i * 0.14, -h * 0.42);
    ctx.lineTo(w * (i * 0.14 + 0.04), h * 0.42);
    ctx.stroke();
  }
}

function drawTurf(ctx, w, h, color) {
  ctx.fillStyle = withAlpha(color, 0.78);
  roundRect(ctx, -w / 2, -h / 2, w, h, 18);
  ctx.fill();

  ctx.strokeStyle = "rgba(255,255,255,0.18)";
  ctx.lineWidth = 2;
  for (let i = 0; i < 14; i += 1) {
    const gx = -w * 0.45 + (w * i) / 13;
    ctx.beginPath();
    ctx.moveTo(gx, h * 0.48);
    ctx.lineTo(gx + w * 0.025, -h * (0.2 + (i % 3) * 0.08));
    ctx.stroke();
  }
}

function drawFence(ctx, w, h, color) {
  ctx.fillStyle = withAlpha(color, 0.86);
  ctx.fillRect(-w / 2, -h / 2, w, h);

  ctx.fillStyle = "rgba(255,255,255,0.22)";
  const postW = Math.max(4, w * 0.018);
  for (let i = 0; i < 9; i += 1) {
    const x = -w * 0.45 + i * w * 0.112;
    ctx.fillRect(x, -h / 2, postW, h);
  }
}

function drawCarport(ctx, w, h, color) {
  ctx.strokeStyle = withAlpha(color, 0.88);
  ctx.lineWidth = Math.max(5, w * 0.025);
  ctx.beginPath();
  ctx.moveTo(-w * 0.38, h * 0.5);
  ctx.lineTo(-w * 0.38, -h * 0.18);
  ctx.lineTo(w * 0.42, -h * 0.42);
  ctx.lineTo(w * 0.42, h * 0.5);
  ctx.stroke();

  ctx.fillStyle = "rgba(240, 247, 248, 0.62)";
  ctx.beginPath();
  ctx.moveTo(-w * 0.5, -h * 0.18);
  ctx.lineTo(w * 0.48, -h * 0.5);
  ctx.lineTo(w * 0.5, -h * 0.22);
  ctx.lineTo(-w * 0.45, h * 0.02);
  ctx.closePath();
  ctx.fill();
}

function drawDeck(ctx, w, h, color) {
  ctx.fillStyle = withAlpha(color, 0.82);
  ctx.beginPath();
  ctx.moveTo(-w * 0.5, -h * 0.35);
  ctx.lineTo(w * 0.5, -h * 0.25);
  ctx.lineTo(w * 0.42, h * 0.5);
  ctx.lineTo(-w * 0.48, h * 0.36);
  ctx.closePath();
  ctx.fill();

  ctx.strokeStyle = "rgba(255,255,255,0.22)";
  ctx.lineWidth = 2;
  for (let i = 1; i < 5; i += 1) {
    const y = -h * 0.28 + (h * i) / 5;
    ctx.beginPath();
    ctx.moveTo(-w * 0.48, y);
    ctx.lineTo(w * 0.44, y + h * 0.04);
    ctx.stroke();
  }
}

function drawPlants(ctx, w, h, color) {
  const radius = Math.min(w, h) * 0.14;
  const xs = [-0.35, -0.12, 0.12, 0.34];

  xs.forEach((offset, index) => {
    const x = w * offset;
    const y = h * (0.08 - (index % 2) * 0.18);
    ctx.fillStyle = withAlpha(color, 0.84);
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = "rgba(92, 70, 48, 0.72)";
    ctx.fillRect(x - radius * 0.1, y + radius * 0.7, radius * 0.2, radius * 1.6);
  });
}

function drawEditorBadge(ctx, canvas) {
  const text = state.removalMode ? "撤去範囲指定" : "配置調整モード";
  ctx.font = `700 ${Math.max(14, canvas.width * 0.022)}px system-ui, sans-serif`;
  const metrics = ctx.measureText(text);
  const padX = 14;
  const boxW = Math.min(canvas.width - 24, metrics.width + padX * 2);
  const boxH = Math.max(34, canvas.height * 0.044);
  const x = 12;
  const y = canvas.height - boxH - 12;

  ctx.fillStyle = "rgba(20, 31, 26, 0.76)";
  roundRect(ctx, x, y, boxW, boxH, 999);
  ctx.fill();
  ctx.fillStyle = "#ffffff";
  ctx.fillText(text, x + padX, y + boxH * 0.66, boxW - padX * 2);
}

function drawRemovalMask(ctx, canvas) {
  const paths = [...state.removalMaskPaths];
  if (state.activeMaskPath) {
    paths.push(state.activeMaskPath);
  }

  if (!paths.length) return;

  ctx.save();
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  paths.forEach((path) => {
    if (path.points.length < 1) return;

    ctx.strokeStyle = "rgba(218, 62, 48, 0.48)";
    ctx.fillStyle = "rgba(218, 62, 48, 0.18)";
    ctx.lineWidth = path.brush;
    ctx.beginPath();
    path.points.forEach((point, index) => {
      const x = point.x * canvas.width;
      const y = point.y * canvas.height;
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();

    if (path.points.length > 4 && getPathClosure(path) < path.brush * 1.7) {
      ctx.closePath();
      ctx.fill();
    }
  });
  ctx.restore();
}

function getPathClosure(path) {
  const first = path.points[0];
  const last = path.points[path.points.length - 1];
  return Math.hypot(
    (last.x - first.x) * elements.editorCanvas.width,
    (last.y - first.y) * elements.editorCanvas.height,
  );
}

function createMaskCanvas() {
  const sourceCanvas = elements.editorCanvas;
  const maskCanvas = document.createElement("canvas");
  maskCanvas.width = sourceCanvas.width;
  maskCanvas.height = sourceCanvas.height;
  const ctx = maskCanvas.getContext("2d");

  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, maskCanvas.width, maskCanvas.height);
  ctx.strokeStyle = "#fff";
  ctx.fillStyle = "#fff";
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  state.removalMaskPaths.forEach((path) => {
    if (!path.points.length) return;

    ctx.lineWidth = path.brush;
    ctx.beginPath();
    path.points.forEach((point, index) => {
      const x = point.x * maskCanvas.width;
      const y = point.y * maskCanvas.height;
      if (index === 0) {
        ctx.moveTo(x, y);
      } else {
        ctx.lineTo(x, y);
      }
    });
    ctx.stroke();

    if (path.points.length > 4 && getPathClosure(path) < path.brush * 1.7) {
      ctx.closePath();
      ctx.fill();
    }
  });

  return maskCanvas;
}

function createOriginalImageDataUrl() {
  const canvas = document.createElement("canvas");
  canvas.width = elements.editorCanvas.width;
  canvas.height = elements.editorCanvas.height;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(state.baseImage, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.9);
}

function buildRemovalApiPayload() {
  const maskCanvas = createMaskCanvas();

  return {
    image: createOriginalImageDataUrl(),
    mask: maskCanvas.toDataURL("image/png"),
    instruction: removalGenerator.instruction,
  };
}

async function generateRemovalPreview() {
  if (!state.editorReady || state.removalMaskPaths.length === 0) return;

  state.isGenerating = true;
  syncControls();

  try {
    const payload = buildRemovalApiPayload();
    state.removalCanvas = await removalGenerator.generate({
      originalImageDataUrl: payload.image,
      maskImageDataUrl: payload.mask,
      instruction: payload.instruction,
      baseImage: state.baseImage,
      maskCanvas: createMaskCanvas(),
      width: elements.editorCanvas.width,
      height: elements.editorCanvas.height,
    });
    state.removalMode = false;
    renderEditor();
  } catch (error) {
    elements.resultSummary.textContent = error.message;
  } finally {
    state.isGenerating = false;
    syncControls();
  }
}

async function generateMockRemoval(input) {
  const canvas = document.createElement("canvas");
  canvas.width = input.width;
  canvas.height = input.height;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(input.baseImage, 0, 0, canvas.width, canvas.height);

  const maskCtx = input.maskCanvas.getContext("2d");
  const mask = maskCtx.getImageData(0, 0, canvas.width, canvas.height).data;
  const image = ctx.getImageData(0, 0, canvas.width, canvas.height);
  const data = image.data;
  const snapshot = new Uint8ClampedArray(data);
  const radius = 18;

  for (let y = 0; y < canvas.height; y += 1) {
    for (let x = 0; x < canvas.width; x += 1) {
      const index = (y * canvas.width + x) * 4;
      if (mask[index] < 128) continue;

      let r = 0;
      let g = 0;
      let b = 0;
      let count = 0;
      const samples = [
        [x - radius, y],
        [x + radius, y],
        [x, y - radius],
        [x, y + radius],
        [x - radius, y - radius],
        [x + radius, y + radius],
      ];

      samples.forEach(([sx, sy]) => {
        const cx = Math.max(0, Math.min(canvas.width - 1, sx));
        const cy = Math.max(0, Math.min(canvas.height - 1, sy));
        const sampleIndex = (cy * canvas.width + cx) * 4;
        if (mask[sampleIndex] > 128) return;
        r += snapshot[sampleIndex];
        g += snapshot[sampleIndex + 1];
        b += snapshot[sampleIndex + 2];
        count += 1;
      });

      if (count === 0) {
        r = snapshot[index];
        g = snapshot[index + 1];
        b = snapshot[index + 2];
        count = 1;
      }

      data[index] = r / count;
      data[index + 1] = g / count;
      data[index + 2] = b / count;
    }
  }

  ctx.putImageData(image, 0, 0);
  await new Promise((resolve) => setTimeout(resolve, 360));
  return canvas;
}

function getCanvasPoint(event) {
  const rect = elements.editorCanvas.getBoundingClientRect();
  return {
    x: ((event.clientX - rect.left) / rect.width) * elements.editorCanvas.width,
    y: ((event.clientY - rect.top) / rect.height) * elements.editorCanvas.height,
  };
}

function getNormalizedPoint(point) {
  return {
    x: Math.max(0, Math.min(1, point.x / elements.editorCanvas.width)),
    y: Math.max(0, Math.min(1, point.y / elements.editorCanvas.height)),
  };
}

function hitTest(point) {
  return state.layers
    .slice()
    .sort((a, b) => b.z - a.z)
    .find((layer) => isPointInLayer(point, layer));
}

function isPointInLayer(point, layer) {
  const canvas = elements.editorCanvas;
  const cx = canvas.width * layer.x;
  const cy = canvas.height * layer.y;
  const totalScale = layer.scale * layer.depth;
  const cos = Math.cos(-layer.rotation);
  const sin = Math.sin(-layer.rotation);
  const dx = point.x - cx;
  const dy = point.y - cy;
  const localX = (dx * cos - dy * sin) / totalScale;
  const localY = (dx * sin + dy * cos) / totalScale;
  const w = canvas.width * layer.w;
  const h = canvas.height * layer.h;

  return Math.abs(localX) <= w / 2 && Math.abs(localY) <= h / 2;
}

function selectLayer(id) {
  state.selectedLayerId = id;
  state.removalMode = false;
  state.activeMaskPath = null;
  renderEditor();
  syncControls();
}

function moveSelectedLayerToFront() {
  const layer = getSelectedLayer();
  if (!layer) return;

  layer.z = Math.max(...state.layers.map((item) => item.z)) + 1;
  normalizeZ();
  renderEditor();
  syncControls();
}

function moveSelectedLayerToBack() {
  const layer = getSelectedLayer();
  if (!layer) return;

  layer.z = Math.min(...state.layers.map((item) => item.z)) - 1;
  normalizeZ();
  renderEditor();
  syncControls();
}

function normalizeZ() {
  state.layers
    .slice()
    .sort((a, b) => a.z - b.z)
    .forEach((layer, index) => {
      layer.z = index + 1;
    });
}

function deleteSelectedLayer() {
  const layer = getSelectedLayer();
  if (!layer) return;

  state.layers = state.layers.filter((item) => item.id !== layer.id);
  state.selectedLayerId = state.layers[state.layers.length - 1]?.id || "";
  if (state.layers.length === 0) {
    state.editorReady = false;
  }
  renderEditor();
  syncControls();
}

function setLayerRange(name, rawValue) {
  const layer = getSelectedLayer();
  if (!layer) return;

  const value = Number(rawValue);
  if (name === "scale") layer.scale = value / 100;
  if (name === "rotation") layer.rotation = (value * Math.PI) / 180;
  if (name === "depth") layer.depth = value / 100;

  renderEditor();
  syncControls();
}

function getPointerDistance(a, b) {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

function getPointerAngle(a, b) {
  return Math.atan2(b.y - a.y, b.x - a.x);
}

function beginSinglePointer(point) {
  const layer = hitTest(point);
  if (!layer) {
    return;
  }

  selectLayer(layer.id);
  gesture.mode = "drag";
  gesture.start = {
    point,
    layerX: layer.x,
    layerY: layer.y,
  };
}

function beginPinch() {
  const layer = getSelectedLayer();
  const points = Array.from(gesture.pointers.values());
  if (!layer || points.length < 2) return;

  gesture.mode = "pinch";
  gesture.start = {
    distance: getPointerDistance(points[0], points[1]),
    angle: getPointerAngle(points[0], points[1]),
    scale: layer.scale,
    rotation: layer.rotation,
  };
}

function handleCanvasPointerDown(event) {
  if (!state.editorReady) return;

  elements.editorCanvas.setPointerCapture(event.pointerId);
  const point = getCanvasPoint(event);
  gesture.pointers.set(event.pointerId, point);

  if (state.removalMode) {
    state.activeMaskPath = {
      brush: state.brushSize,
      points: [getNormalizedPoint(point)],
    };
    gesture.mode = "mask";
    renderEditor();
    syncControls();
    return;
  }

  if (gesture.pointers.size === 1) {
    beginSinglePointer(point);
  }

  if (gesture.pointers.size === 2) {
    beginPinch();
  }
}

function handleCanvasPointerMove(event) {
  if (!state.editorReady || !gesture.pointers.has(event.pointerId)) return;

  const point = getCanvasPoint(event);
  gesture.pointers.set(event.pointerId, point);

  if (gesture.mode === "mask" && state.activeMaskPath) {
    state.activeMaskPath.points.push(getNormalizedPoint(point));
    renderEditor();
    syncRemovalControls();
    return;
  }

  const layer = getSelectedLayer();
  if (!layer || !gesture.start) return;

  if (gesture.mode === "drag" && gesture.pointers.size === 1) {
    const dx = (point.x - gesture.start.point.x) / elements.editorCanvas.width;
    const dy = (point.y - gesture.start.point.y) / elements.editorCanvas.height;
    layer.x = Math.max(0.02, Math.min(0.98, gesture.start.layerX + dx));
    layer.y = Math.max(0.02, Math.min(0.98, gesture.start.layerY + dy));
  }

  if (gesture.mode === "pinch" && gesture.pointers.size >= 2) {
    const points = Array.from(gesture.pointers.values());
    const distance = getPointerDistance(points[0], points[1]);
    const angle = getPointerAngle(points[0], points[1]);
    const scaleRatio = distance / Math.max(1, gesture.start.distance);
    layer.scale = Math.max(0.45, Math.min(1.8, gesture.start.scale * scaleRatio));
    layer.rotation = Math.max(
      -Math.PI / 4,
      Math.min(Math.PI / 4, gesture.start.rotation + angle - gesture.start.angle),
    );
  }

  renderEditor();
  syncRangeControls();
}

function handleCanvasPointerUp(event) {
  if (gesture.mode === "mask" && state.activeMaskPath) {
    state.removalMaskPaths.push(state.activeMaskPath);
    state.activeMaskPath = null;
    gesture.pointers.delete(event.pointerId);
    if (gesture.pointers.size === 0) {
      gesture.mode = "";
      gesture.start = null;
    }
    renderEditor();
    syncControls();
    return;
  }

  gesture.pointers.delete(event.pointerId);

  if (gesture.pointers.size === 1) {
    const point = Array.from(gesture.pointers.values())[0];
    beginSinglePointer(point);
    return;
  }

  if (gesture.pointers.size === 0) {
    gesture.mode = "";
    gesture.start = null;
  }
}

elements.photoInput.addEventListener("change", (event) => {
  setPhoto(event.target.files?.[0] || null);
});

elements.workItems.addEventListener("change", (event) => {
  if (event.target.matches('input[name="workType"]')) {
    updateWorkSelection(event.target);
  }
});

elements.colorSelect.addEventListener("change", (event) => updateOption("color", event.target.value));
elements.sizeSelect.addEventListener("change", (event) => updateOption("size", event.target.value));
elements.heightSelect.addEventListener("change", (event) => updateOption("height", event.target.value));
elements.moodSelect.addEventListener("change", (event) => updateOption("mood", event.target.value));

elements.layerList.addEventListener("click", (event) => {
  const button = event.target.closest("[data-layer-id]");
  if (button) {
    selectLayer(button.dataset.layerId);
  }
});

elements.layerFrontButton.addEventListener("click", moveSelectedLayerToFront);
elements.layerBackButton.addEventListener("click", moveSelectedLayerToBack);
elements.deleteLayerButton.addEventListener("click", deleteSelectedLayer);
elements.scaleRange.addEventListener("input", (event) => setLayerRange("scale", event.target.value));
elements.rotationRange.addEventListener("input", (event) => setLayerRange("rotation", event.target.value));
elements.depthRange.addEventListener("input", (event) => setLayerRange("depth", event.target.value));
elements.maskModeButton.addEventListener("click", () => {
  if (!state.editorReady) return;
  state.removalMode = !state.removalMode;
  state.activeMaskPath = null;
  gesture.pointers.clear();
  gesture.mode = "";
  gesture.start = null;
  renderEditor();
  syncControls();
});
elements.removePreviewButton.addEventListener("click", generateRemovalPreview);
elements.clearMaskButton.addEventListener("click", clearRemovalMask);
elements.brushRange.addEventListener("input", (event) => {
  state.brushSize = Number(event.target.value);
  syncRemovalControls();
});

elements.editorCanvas.addEventListener("pointerdown", handleCanvasPointerDown);
elements.editorCanvas.addEventListener("pointermove", handleCanvasPointerMove);
elements.editorCanvas.addEventListener("pointerup", handleCanvasPointerUp);
elements.editorCanvas.addEventListener("pointercancel", handleCanvasPointerUp);

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (!state.photoUrl || state.isGenerating) {
    return;
  }

  await startEditorMode();
});

window.addEventListener("resize", () => {
  renderEditor();
});

renderWorkOptions();
syncControls();
