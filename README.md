# Field Quick Calc

Overseas DIY-focused prototype derived from the Japanese GENBA TOOLBOX / 現場電卓 concept.

This version is designed around Imperial units only:

- feet
- inches
- cubic feet
- square feet

Metric input is intentionally not included in this prototype.

## Tools

- Tapered Volume: side-slope based section widths and volume
- Radius / Circle: arc length, estimated radius, circle circumference
- Slope: rise, run, angle, slope length
- Stairs: rise per step, total run, stringer length
- Material Weight Table: quick reference values
- Notes: localStorage memo

## Run Locally

Open `index.html` directly, or run:

```bash
npm run build
python3 -m http.server 3004 -d dist
```

Then open:

```text
http://localhost:3004
```

## Capacitor Prep

When ready to add native platforms:

```bash
npm install @capacitor/core @capacitor/cli @capacitor/ios @capacitor/android
npm run build
npx cap init "Field Quick Calc" "com.genbatoolbox.fieldquickcalc" --web-dir dist
npx cap add ios
npx cap add android
npx cap sync
```

## Disclaimer

Results are estimates only.
Always follow local codes, drawings, site conditions, and professional judgment.
