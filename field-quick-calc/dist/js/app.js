const $ = (id) => document.getElementById(id);
const screens = [...document.querySelectorAll(".screen")];
const notesKey = "fieldQuickCalc_notes_v1";
let radiusMode = "arc";
let taperSide = "left";

function n(id) {
  const value = parseFloat($(id)?.value);
  return Number.isFinite(value) ? value : 0;
}

function fmt(value, digits = 1) {
  if (!Number.isFinite(value)) return "--";
  return value.toLocaleString("en-US", {
    maximumFractionDigits: digits,
    minimumFractionDigits: digits
  });
}

function whole(value) {
  if (!Number.isFinite(value)) return "--";
  return Math.ceil(value).toLocaleString("en-US");
}

function show(id) {
  screens.forEach((screen) => screen.classList.toggle("active", screen.id === id));
  window.scrollTo(0, 0);
}

function calcConcrete() {
  const totalHeight = n("conTotalHeightFt");
  const topWidth = n("conTopWidthFt");
  const slopeRatio = n("conSlopeRatio");
  const length = n("conLenFt");
  const checkHeights = [n("conCheckH1Ft"), n("conCheckH2Ft"), n("conCheckH3Ft")];
  const sideFactor = taperSide === "both" ? 2 : 1;
  const bottomWidth = topWidth + sideFactor * slopeRatio * totalHeight;
  const avgWidth = (topWidth + bottomWidth) / 2;
  const area = avgWidth * totalHeight;
  const volume = area * length;
  const widths = checkHeights.map((height) => widthAtHeight(height, totalHeight, topWidth, slopeRatio, taperSide));

  $("conVolume").textContent = volume > 0 ? fmt(volume, 1) : "--";
  $("conYards").textContent = volume > 0 ? fmt(volume / 27, 2) : "--";
  $("conBottomWidth").textContent = bottomWidth > 0 ? fmt(bottomWidth, 2) : "--";
  $("conWidthH1").textContent = widths[0] > 0 ? fmt(widths[0], 2) : "--";
  $("conWidthH2").textContent = widths[1] > 0 ? fmt(widths[1], 2) : "--";
  $("conWidthH3").textContent = widths[2] > 0 ? fmt(widths[2], 2) : "--";
  $("conArea").textContent = area > 0 ? fmt(area, 2) : "--";
  drawTaperedSection({ totalHeight, topWidth, slopeRatio, checkHeights, widths, bottomWidth, taperSide });
}

function widthAtHeight(checkHeight, totalHeight, topWidth, slopeRatio, side = taperSide) {
  if (checkHeight <= 0 || totalHeight <= 0 || topWidth <= 0) return 0;
  const clampedHeight = Math.min(checkHeight, totalHeight);
  const sideFactor = side === "both" ? 2 : 1;
  return topWidth + sideFactor * slopeRatio * clampedHeight;
}

function drawTaperedSection(data) {
  const totalHeight = data.totalHeight > 0 ? data.totalHeight : 5;
  const topWidth = data.topWidth > 0 ? data.topWidth : 2;
  const hasSectionInput = data.totalHeight > 0 || data.topWidth > 0 || $("conSlopeRatio").value.trim() !== "";
  const slopeRatio = hasSectionInput ? Math.max(data.slopeRatio, 0) : 1.5;
  const side = data.taperSide || "left";
  const checkHeights = data.checkHeights.map((height, index) => (
    height > 0 ? height : [1, 2, 4][index]
  ));
  const bottomWidth = widthAtHeight(totalHeight, totalHeight, topWidth, slopeRatio, side);
  const widths = checkHeights.map((height) => widthAtHeight(height, totalHeight, topWidth, slopeRatio, side));

  const topY = 38;
  const bottomY = 232;
  const centerX = 160;
  const maxDrawWidth = 232;
  const scale = maxDrawWidth / Math.max(bottomWidth, topWidth, 1);
  const topDraw = topWidth * scale;
  const bottomDraw = bottomWidth * scale;
  const anchorX = side === "right" ? 82 : side === "left" ? 238 : centerX;
  const topLeft = side === "left" ? anchorX - topDraw : side === "right" ? anchorX : centerX - topDraw / 2;
  const topRight = topLeft + topDraw;
  const bottomLeft = side === "left" ? anchorX - bottomDraw : side === "right" ? anchorX : centerX - bottomDraw / 2;
  const bottomRight = bottomLeft + bottomDraw;
  const heightLineX = Math.max(24, bottomLeft - 22);

  $("taperShape").setAttribute(
    "points",
    `${fmtSvg(topLeft)},${topY} ${fmtSvg(topRight)},${topY} ${fmtSvg(bottomRight)},${bottomY} ${fmtSvg(bottomLeft)},${bottomY}`
  );
  setLine("taperTopLine", topLeft, topY - 13, topRight, topY - 13);
  setLine("taperBottomLine", bottomLeft, bottomY + 13, bottomRight, bottomY + 13);
  setLine("taperHeightLine", heightLineX, topY, heightLineX, bottomY);
  setText("taperTopLabel", centerX - 36, topY - 20, `Top ${fmt(topWidth, 1)} ft`);
  setText("taperBottomLabel", centerX - 50, bottomY + 33, `Bottom ${fmt(bottomWidth, 1)} ft`);
  setText("taperHeightLabel", Math.max(8, heightLineX - 16), (topY + bottomY) / 2, `H ${fmt(totalHeight, 1)} ft`);

  checkHeights.forEach((height, index) => {
    const clampedHeight = Math.min(Math.max(height, 0), totalHeight);
    const y = topY + (clampedHeight / totalHeight) * (bottomY - topY);
    const width = widths[index];
    const drawWidth = width * scale;
    const left = side === "left" ? anchorX - drawWidth : side === "right" ? anchorX : centerX - drawWidth / 2;
    const right = left + drawWidth;
    setLine(`checkLine${index + 1}`, left, y, right, y);
    setText(`checkLabel${index + 1}`, right + 10, y + 5, `h${index + 1}: ${fmt(width, 1)} ft`);
  });
}

function setLine(id, x1, y1, x2, y2) {
  const line = $(id);
  line.setAttribute("x1", fmtSvg(x1));
  line.setAttribute("y1", fmtSvg(y1));
  line.setAttribute("x2", fmtSvg(x2));
  line.setAttribute("y2", fmtSvg(y2));
}

function setText(id, x, y, text) {
  const el = $(id);
  el.setAttribute("x", fmtSvg(x));
  el.setAttribute("y", fmtSvg(y));
  el.textContent = text;
}

function calcArc() {
  const chord = n("arcChordFt");
  const height = n("arcHeightIn") / 12;
  if (chord <= 0 || height <= 0) {
    $("arcLength").textContent = "--";
    $("arcRadius").textContent = "--";
    $("arcExtra").textContent = "--";
    return;
  }
  const radius = (chord * chord) / (8 * height) + height / 2;
  const theta = 2 * Math.asin(chord / (2 * radius));
  const arcLength = radius * theta;
  $("arcLength").textContent = fmt(arcLength, 2);
  $("arcRadius").textContent = fmt(radius, 2);
  $("arcExtra").textContent = fmt((arcLength - chord) * 12, 1);
}

function calcCircle() {
  const diameter = n("circleDiameterFt");
  const radius = diameter / 2;
  $("circleCirc").textContent = diameter > 0 ? fmt(Math.PI * diameter, 2) : "--";
  $("circleRadius").textContent = diameter > 0 ? fmt(radius, 2) : "--";
  $("circleArea").textContent = diameter > 0 ? fmt(Math.PI * radius * radius, 2) : "--";
}

function calcSlope() {
  const riseFt = n("slopeRiseIn") / 12;
  const runFt = n("slopeRunFt");
  const length = Math.hypot(runFt, riseFt);
  const angle = Math.atan2(riseFt, runFt) * 180 / Math.PI;
  const pitch = runFt > 0 ? n("slopeRiseIn") / runFt : 0;
  $("slopeLength").textContent = length > 0 ? fmt(length, 2) : "--";
  $("slopeAngle").textContent = runFt > 0 && riseFt > 0 ? fmt(angle, 1) : "--";
  $("slopePitch").textContent = pitch > 0 ? fmt(pitch, 1) : "--";
}

function calcStairs() {
  const totalRise = n("stairTotalRise");
  const steps = Math.max(0, Math.round(n("stairSteps")));
  const tread = n("stairTread");
  const riseEach = steps > 0 ? totalRise / steps : 0;
  const totalRunIn = steps > 0 ? tread * steps : 0;
  const stringerFt = Math.hypot(totalRise, totalRunIn) / 12;
  $("stairRiseEach").textContent = riseEach > 0 ? fmt(riseEach, 2) : "--";
  $("stairRun").textContent = totalRunIn > 0 ? fmt(totalRunIn / 12, 2) : "--";
  $("stairStringer").textContent = stringerFt > 0 ? fmt(stringerFt, 2) : "--";
  drawStairs({ steps, riseEach, tread, totalRise, totalRunIn });
  updateStairNotice(riseEach, tread, steps);
}

function drawStairs(data) {
  const inputSteps = data.steps || 6;
  const visibleSteps = Math.min(Math.max(inputSteps, 1), 14);
  const left = 54;
  const right = 292;
  const bottom = 154;
  const top = 48;
  const stepW = (right - left) / visibleSteps;
  const stepH = (bottom - top) / visibleSteps;
  const points = [[left, bottom]];

  for (let i = 1; i <= visibleSteps; i += 1) {
    const x = left + stepW * i;
    const y = bottom - stepH * (i - 1);
    points.push([x, y]);
    points.push([x, bottom - stepH * i]);
  }

  $("stairShape").setAttribute("points", points.map(([x, y]) => `${fmtSvg(x)},${fmtSvg(y)}`).join(" "));
  setLine("stairStringerLine", left, bottom, right, top);
  setLine("stairTreadLine", left, bottom + 18, left + stepW, bottom + 18);
  setLine("stairStepRiseLine", left + stepW, bottom, left + stepW, bottom - stepH);
  $("stairRunLine").setAttribute("x2", fmtSvg(right));
  $("stairRiseLine").setAttribute("x1", fmtSvg(right));
  $("stairRiseLine").setAttribute("x2", fmtSvg(right));
  $("stairRiseLine").setAttribute("y2", fmtSvg(top));
  setText("stairRunLabel", left + (right - left) / 2 - 36, bottom + 42, "Total run");
  setText("stairRiseLabel", right + 8, top + (bottom - top) / 2, "Total rise");
  setText("stairTreadLabel", left + stepW / 2 - 14, bottom + 35, data.tread > 0 ? `${fmt(data.tread, 1)} in tread` : "Tread");
  setText("stairStepRiseLabel", left + stepW + 9, bottom - stepH / 2 + 4, data.riseEach > 0 ? `${fmt(data.riseEach, 1)} in rise` : "Rise");
  $("stairCountLabel").textContent = inputSteps > visibleSteps ? `${visibleSteps} of ${inputSteps} steps shown` : `${visibleSteps} steps shown`;
}

function updateStairNotice(riseEach, tread, steps) {
  const notice = $("stairNotice");
  const messages = [];
  if (steps > 14) messages.push("Showing a simplified stair sketch so the steps stay readable.");
  if (riseEach > 0 && (riseEach < 4.5 || riseEach > 8.5)) messages.push("Rise per step looks unusual. Double-check your layout and local requirements.");
  if (tread > 0 && tread < 8) messages.push("Tread depth looks tight for a typical DIY stair.");
  notice.hidden = messages.length === 0;
  notice.textContent = messages.join(" ");
}

function fmtSvg(value) {
  return Number(value.toFixed(2)).toString();
}

function recalcAll() {
  calcConcrete();
  calcArc();
  calcCircle();
  calcSlope();
  calcStairs();
}

function setupNavigation() {
  document.querySelectorAll("[data-open]").forEach((button) => {
    button.addEventListener("click", () => show(button.dataset.open));
  });
}

function setupRadiusMode() {
  document.querySelectorAll("[data-radius-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      radiusMode = button.dataset.radiusMode;
      document.querySelectorAll("[data-radius-mode]").forEach((item) => {
        item.classList.toggle("active", item.dataset.radiusMode === radiusMode);
      });
      $("arcMode").hidden = radiusMode !== "arc";
      $("circleMode").hidden = radiusMode !== "circle";
    });
  });
}

function setupTaperSide() {
  document.querySelectorAll("[data-taper-side]").forEach((button) => {
    button.addEventListener("click", () => {
      taperSide = button.dataset.taperSide;
      document.querySelectorAll("[data-taper-side]").forEach((item) => {
        item.classList.toggle("active", item.dataset.taperSide === taperSide);
      });
      calcConcrete();
    });
  });
}

function setupNotes() {
  const notes = $("notesText");
  notes.value = localStorage.getItem(notesKey) || "";
  notes.addEventListener("input", () => localStorage.setItem(notesKey, notes.value));
  $("clearNotes").addEventListener("click", () => {
    if (!confirm("Clear saved notes?")) return;
    notes.value = "";
    localStorage.removeItem(notesKey);
  });
}

function setupInputs() {
  document.querySelectorAll("input").forEach((input) => input.addEventListener("input", recalcAll));
}

setupNavigation();
setupRadiusMode();
setupTaperSide();
setupNotes();
setupInputs();
recalcAll();
