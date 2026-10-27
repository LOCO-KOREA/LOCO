// LOCO 발표 PPT 생성기 (pptxgenjs).
//
//   cd docs/presentation/deck-src && npm install && node build-deck.mjs
//   node build-deck.mjs --assets <캡처 폴더> --out <LOCO-발표.pptx> --work <임시 폴더>   (경로를 바꿀 때)
//
// 기본 경로: 캡처 = ../assets, 결과 = ../LOCO-발표.pptx, 임시 = ./.work
// 환경변수 QA_FLAT=1 이면 제목·마무리 슬라이드에 배경 그림을 슬라이드 위에 한 번 더 깐다
// (레이아웃 배경을 못 그리는 미리보기 도구로 눈 확인할 때만 쓰고, 배포 파일은 이 값 없이 만든다).
//
// 필요한 패키지: pptxgenjs, sharp, react, react-dom, react-icons, jszip (package.json 참고).
// 글자·숫자·한계 문구는 docs/presentation/TEST_FACTS.md 와 저장소 문서에서 가져온 것이다.
// 여기에 없는 수치는 만들어 쓰지 않는다. 숫자를 바꿀 때는 아래 FACTS 와 각 슬라이드 문구·노트를 함께 고친다.
import pptxgen from 'pptxgenjs';
import sharp from 'sharp';
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import * as Fi from 'react-icons/fi';
import JSZip from 'jszip';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// ───────────────────────────── 인자 ─────────────────────────────
const args = Object.fromEntries(process.argv.slice(2).reduce((acc, cur, i, all) => {
  if (cur.startsWith('--')) acc.push([cur.slice(2), all[i + 1]]);
  return acc;
}, []));
const HERE = path.dirname(fileURLToPath(import.meta.url));
const ASSETS = path.resolve(args.assets || path.join(HERE, '..', 'assets'));
const OUT = path.resolve(args.out || path.join(HERE, '..', 'LOCO-발표.pptx'));
const WORK = path.resolve(args.work || path.join(HERE, '.work'));
fs.mkdirSync(WORK, { recursive: true });
fs.mkdirSync(path.dirname(OUT), { recursive: true });

// ───────────────────────────── 디자인 기준 ─────────────────────────────
const FONT = 'Malgun Gothic';            // 맑은 고딕 (Windows 기본 한글 글꼴)
const W = 13.333, H = 7.5, MX = 0.6, CW = W - 2 * MX;
const INK = '1B1E3C', INDIGO = '262A6B', VIOLET = '5C61DB', LAV = '8D91EA', SURFACE = 'F3F4FD';
const AMBER = 'F2A33A', AMBER_BG = 'FFF4E0', AMBER_INK = '6F4300', GREEN = '2E9E6B', RED = 'D9534F';
const SUB = '4A4F6D', MUTED = '6B7090', LINE = 'DADCF0', WHITE = 'FFFFFF';
// 앱 결과 화면(demo-05)의 REBA 위험 단계 색상바에서 픽셀 값을 읽어 옮긴 색
const REBA = { r1: '307946', r23: '9ECE74', r47: 'F0D05B', r810: 'E89743', r1115: 'C04946' };
const THEME = {
  name: 'LOCO',
  colors: { dk1: INK, lt1: WHITE, dk2: INDIGO, lt2: SURFACE, accent1: VIOLET, accent2: LAV, accent3: AMBER,
    accent4: GREEN, accent5: RED, accent6: MUTED, hlink: VIOLET, folHlink: LAV },
};

// 발표에 쓰는 사실. 출처: TEST_FACTS.md(2026-10-26 실측, "한 페이지 입력 반영본").
// 바꾸면 슬라이드 문구·발표자 노트·README 도 함께 확인한다. 여기에 없는 수치는 만들어 쓰지 않는다.
const FACTS = {
  asOf: '2026-10-26',
  pythonTests: 529, frontendFiles: 37, defects: 12,   // TEST_FACTS.md "시험 규모"(커밋 457b5f5 기준)
  waitXhigh: [170, 121, 113], waitHigh: [55, 73, 73, 256], firstScoreSec: [3.6, 4.1, 6.1],
  interactions: 17, interactionsBefore: 19,
};
const firstScoreText = `${FACTS.firstScoreSec.join('초·')}초`;
const demoFirstScore = '4~10초';   // docs/presentation/demo/시연-시나리오.md: 단독 실행 3.6~6.1초, 리허설(두 개 동시 실행) 7.4초·9.9초
// 커밋 4fb3dc3(AI 요청 재전송). 실제 AI 로 120초 초과를 만들어 시험하지는 못했다는 한계를 항상 같이 쓴다.
const resendNote = 'AI 요청 한 번은 120초까지만 기다리고 답이 없으면 같은 요청을 다시 보냅니다(처음 포함 최대 3번, 시간 초과가 아닌 오류는 다시 보내지 않음). 실제 AI로 120초 초과를 만들어 시험하지는 못했고, 실제 SDK와 일부러 느리게 만든 로컬 서버(제한을 1초로 줄임)로 두 번째 요청의 답을 쓰는 것을 확인했습니다(커밋 4fb3dc3).';

// ───────────────────────────── 작은 도구 ─────────────────────────────
function estWidth(text, pt) {           // 글자 폭 어림(인치): 한글 1em, 숫자·영문은 더 좁게
  let em = 0;
  for (const ch of String(text)) {
    if (/[ᄀ-ᇿ㄰-㆏가-힯　-〿＀-￯①-⓿]/.test(ch)) em += 1;
    else if (/[0-9]/.test(ch)) em += 0.56;
    else if (/[A-Z]/.test(ch)) em += 0.64;
    else if (/[a-z]/.test(ch)) em += 0.54;
    else if (ch === ' ') em += 0.3;
    else em += 0.45;
  }
  return em * pt / 72;
}
const iconCache = new Map();
async function icon(name, color) {
  const key = name + color;
  if (iconCache.has(key)) return iconCache.get(key);
  const Cmp = Fi[name];
  if (!Cmp) throw new Error('없는 아이콘: ' + name);
  let svg = renderToStaticMarkup(React.createElement(Cmp, { size: 256 })).replace(/currentColor/g, '#' + color);
  if (!svg.includes('xmlns=')) svg = svg.replace('<svg', '<svg xmlns="http://www.w3.org/2000/svg"');
  const buf = await sharp(Buffer.from(svg), { density: 300 }).resize(256, 256).png().toBuffer();
  const data = 'image/png;base64,' + buf.toString('base64');
  iconCache.set(key, data);
  return data;
}
// 캡처를 잘라 모서리를 둥글게 하고 가는 테두리를 둘러 PNG 로 저장한다. 크기는 원본 픽셀 그대로.
async function framed(file, box, name, { radius = 14, border = LINE } = {}) {
  let img = sharp(path.join(ASSETS, file));
  if (box) img = img.extract({ left: box[0], top: box[1], width: box[2] - box[0], height: box[3] - box[1] });
  const buf = await img.png().toBuffer();
  const { width: w, height: h } = await sharp(buf).metadata();
  const mask = Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><rect width="${w}" height="${h}" rx="${radius}" fill="#fff"/></svg>`);
  const edge = Buffer.from(`<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}"><rect x="0.75" y="0.75" width="${w - 1.5}" height="${h - 1.5}" rx="${radius}" fill="none" stroke="#${border}" stroke-width="1.5"/></svg>`);
  const out = await sharp(buf).composite([{ input: mask, blend: 'dest-in' }]).composite([{ input: edge }]).png().toBuffer();
  const dest = path.join(WORK, name + '.png');
  fs.writeFileSync(dest, out);
  return { path: dest, w, h };
}
const fitW = (img, h) => h * img.w / img.h;     // 높이를 정하면 가로(인치)
const fitH = (img, w) => w * img.h / img.w;     // 가로를 정하면 높이(인치)

// 제목·마무리 슬라이드 배경(그라데이션 + 자세 골격 모티프)
async function backgroundPng(name, { figure }) {
  const bone = (a, b) => `<line x1="${a[0]}" y1="${a[1]}" x2="${b[0]}" y2="${b[1]}"/>`;
  const P = { N: [1405, 362], S: [1422, 398], E: [1348, 540], Wr: [1278, 642], Hp: [1512, 612], Kn: [1456, 776], An: [1512, 930], T: [1428, 946] };
  const joints = Object.values(P).map(p => `<circle cx="${p[0]}" cy="${p[1]}" r="15"/>`).join('');
  const fig = figure ? `
    <g stroke="#CFD2FF" stroke-width="9" stroke-linecap="round" stroke-opacity="0.92" fill="none">
      <circle cx="1392" cy="288" r="46" stroke-width="8"/>
      ${bone([1398, 334], P.N)}${bone(P.N, P.S)}${bone(P.S, P.E)}${bone(P.E, P.Wr)}
      ${bone(P.S, P.Hp)}${bone(P.Hp, P.Kn)}${bone(P.Kn, P.An)}${bone(P.An, P.T)}
    </g>
    <rect x="1150" y="642" width="200" height="150" rx="16" fill="#FFFFFF" fill-opacity="0.08" stroke="#FFFFFF" stroke-opacity="0.38" stroke-width="3"/>
    <path d="M1478 700 A 62 62 0 0 1 1466 716" stroke="#F2A33A" stroke-width="7" fill="none" stroke-linecap="round" transform="translate(0,0)"/>
    <path d="M 1432 700 A 80 80 0 0 0 1448 790" stroke="#F2A33A" stroke-width="7" fill="none" stroke-linecap="round" stroke-opacity="0.95"/>
    <g fill="#FFFFFF" stroke="#7A7FF0" stroke-width="5">${joints}</g>` : '';
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
    <defs>
      <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#171A4D"/><stop offset="0.55" stop-color="#262A6B"/><stop offset="1" stop-color="#3F44B5"/>
      </linearGradient>
      <radialGradient id="glow" cx="0.74" cy="0.5" r="0.5">
        <stop offset="0" stop-color="#8D91EA" stop-opacity="0.50"/><stop offset="1" stop-color="#8D91EA" stop-opacity="0"/>
      </radialGradient>
    </defs>
    <rect width="1920" height="1080" fill="url(#bg)"/>
    <rect width="1920" height="1080" fill="url(#glow)"/>
    <g fill="none" stroke="#FFFFFF" stroke-opacity="0.08" stroke-width="2">
      <circle cx="1420" cy="560" r="250"/><circle cx="1420" cy="560" r="390"/><circle cx="1420" cy="560" r="530"/><circle cx="1420" cy="560" r="680"/>
    </g>${fig}
  </svg>`;
  const dest = path.join(WORK, name + '.png');
  await sharp(Buffer.from(svg)).png().toFile(dest);
  return dest;
}

// ───────────────────────────── pptx 뼈대 ─────────────────────────────
const pres = new pptxgen();
pres.layout = 'LAYOUT_WIDE';
pres.title = 'LOCO 2.0 발표 자료';
pres.subject = '사진과 한 문장으로 시작하는 근골격계 유해요인조사 보조 도구';
pres.author = '팀 LOCO';
pres.company = 'LOCO';
pres.theme = { headFontFace: FONT, bodyFontFace: FONT };
const SHAPE = pres.ShapeType;

function txt(slide, text, o = {}) {
  slide.addText(text, { isTextBox: true, fontFace: FONT, lang: 'ko-KR', margin: 0, valign: 'top', color: INK, lineSpacingMultiple: 1.08, ...o });
}
function box(slide, x, y, w, h, { fill = SURFACE, radius = 0.16, line = null, shadow = false, name = '카드' } = {}) {
  slide.addShape(SHAPE.roundRect, {
    x, y, w, h, rectRadius: radius, objectName: name,
    fill: { color: fill }, line: line ? { color: line, width: 1 } : { type: 'none' },
    ...(shadow ? { shadow: { type: 'outer', color: '1B1E3C', opacity: 0.12, blur: 10, offset: 3, angle: 90 } } : {}),
  });
}
async function iconDot(slide, name, x, y, d, { bg = VIOLET, fg = WHITE, alt } = {}) {
  slide.addShape(SHAPE.ellipse, { x, y, w: d, h: d, fill: { color: bg }, line: { type: 'none' }, objectName: (alt || name) + ' 원' });
  const pad = d * 0.24;
  slide.addImage({ data: await icon(name, fg), x: x + pad, y: y + pad, w: d - 2 * pad, h: d - 2 * pad, altText: alt || '아이콘' });
}
function badge(slide, n, x, y, d = 0.6, { bg = VIOLET, fg = WHITE, size } = {}) {
  slide.addText(String(n), { isTextBox: true, shape: SHAPE.ellipse, x, y, w: d, h: d, fill: { color: bg }, line: { type: 'none' }, color: fg,
    bold: true, fontSize: size || Math.round(d * 34), fontFace: FONT, lang: 'ko-KR', align: 'center', valign: 'middle', margin: 0, objectName: '번호 ' + n });
}
function chip(slide, label, x, y, { fill = SURFACE, fg = INDIGO, size = 13, h = 0.32, bold = true, padX = 0.34, w, line } = {}) {
  const width = w || estWidth(label, size) + padX;
  slide.addText(label, { isTextBox: true, shape: SHAPE.roundRect, x, y, w: width, h, rectRadius: h / 2, fill: { color: fill }, line: line ? { color: line, width: 1 } : { type: 'none' },
    color: fg, bold, fontSize: size, fontFace: FONT, lang: 'ko-KR', align: 'center', valign: 'middle', margin: 0, objectName: '표시 ' + label });
  return width;
}
function arrow(slide, x1, y, x2, { color = LAV, width = 3 } = {}) {
  slide.addShape(SHAPE.line, { x: x1, y, w: x2 - x1, h: 0, line: { color, width, endArrowType: 'triangle' }, objectName: '화살표' });
}
function sectionTag(slide, label) {
  chip(slide, label, MX, 0.34, { fill: VIOLET, fg: WHITE, size: 13, h: 0.32, padX: 0.5 });
}
function amberNote(slide, text, x, y, w, h, { size = 15 } = {}) {
  box(slide, x, y, w, h, { fill: AMBER_BG, radius: 0.14, name: '주의 상자' });
  txt(slide, text, { x: x + 0.25, y, w: w - 0.5, h, fontSize: size, color: AMBER_INK, valign: 'middle', bold: false });
}
function credit(slide, text, y = 6.66) {
  txt(slide, text, { x: MX, y, w: CW, h: 0.3, fontSize: 11, color: MUTED });
}
function contentSlide(section, title, notes, tag) {
  const slide = pres.addSlide({ masterName: 'CONTENT', sectionTitle: section });
  slide.addText(title, { placeholder: 'title', lang: 'ko-KR' });
  sectionTag(slide, tag || sectionTagLabel[section]);
  slide.addNotes(notes);
  return slide;
}
const sectionTagLabel = { '발표 기획의도': '기획의도', '프로그램 개발 환경': '개발 환경', '프로그램 사용 방법': '사용 방법', '시연': '시연', '향후 계획': '향후 계획' };

// 레이아웃(슬라이드 마스터)
const bgTitle = await backgroundPng('bg-title', { figure: true });
const bgClosing = await backgroundPng('bg-closing', { figure: false });
pres.defineSlideMaster({
  title: 'TITLE', background: { path: bgTitle },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: 0.9, y: 1.95, w: 8.5, h: 2.95, fontFace: FONT, fontSize: 44, bold: true, color: WHITE, align: 'left', valign: 'top', margin: 0, lineSpacingMultiple: 1.12 }, text: '' } },
    { placeholder: { options: { name: 'sub', type: 'body', x: 0.9, y: 5.0, w: 7.4, h: 1.1, fontFace: FONT, fontSize: 22, color: 'DCDEFF', align: 'left', valign: 'top', margin: 0, lineSpacingMultiple: 1.15 }, text: '' } },
  ],
});
pres.defineSlideMaster({
  title: 'CLOSING', background: { path: bgClosing },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: 0.9, y: 0.7, w: 11.5, h: 0.95, fontFace: FONT, fontSize: 38, bold: true, color: WHITE, align: 'left', valign: 'middle', margin: 0 }, text: '' } },
  ],
});
pres.defineSlideMaster({
  title: 'CONTENT', background: { color: WHITE },
  objects: [
    { placeholder: { options: { name: 'title', type: 'title', x: MX, y: 0.74, w: CW, h: 0.82, fontFace: FONT, fontSize: 32, bold: true, color: INDIGO, align: 'left', valign: 'middle', margin: 0 }, text: '' } },
    { text: { text: 'LOCO 2.0 · 발표 자료', options: { x: MX, y: 7.06, w: 4, h: 0.28, fontFace: FONT, fontSize: 11, color: MUTED, margin: 0, valign: 'middle', lang: 'ko-KR' } } },
  ],
  slideNumber: { x: W - MX - 0.8, y: 7.06, w: 0.8, h: 0.28, fontFace: FONT, fontSize: 11, color: MUTED, align: 'right' },
});

// ───────────────────────────── 이미지 준비 ─────────────────────────────
const IMG = {
  d01: await framed('demo-01-photo-chosen.png', [0, 62, 1409, 1160], 'c-d01-photo-text'),
  op01banner: await framed('demo-onepage-01-first-score-while-ai-runs.png', [40, 178, 1384, 268], 'c-op01-banner', { radius: 12 }),
  op01photo: await framed('demo-onepage-01-first-score-while-ai-runs.png', [40, 283, 592, 993], 'c-op01-photo'),
  op01score: await framed('demo-onepage-01-first-score-while-ai-runs.png', [612, 283, 1351, 1040], 'c-op01-score'),
  dlg1: await framed('demo-dialog-1-work-features.png', null, 'c-dlg1'),
  dlg5: await framed('demo-dialog-5-conditions.png', null, 'c-dlg5'),
  dlg2: await framed('demo-dialog-2-checklist.png', null, 'c-dlg2'),
  dlg3: await framed('demo-dialog-3-checklist-confirmed.png', null, 'c-dlg3'),
  dlg4: await framed('demo-dialog-4-angles.png', null, 'c-dlg4'),
  op07score: await framed('demo-onepage-07-result-final.png', [612, 800, 1351, 1500], 'c-op07-score'),
  d06table: await framed('demo-06-final-result-lifting.png', [612, 1160, 1351, 1430], 'c-d06-table'),
  // Excel 단계: 미리보기 카드 영역(y 182~1525)까지만 쓴다.
  exA: await framed('demo-excel-00-summary.png', [30, 48, 1345, 1529], 'c-ex-a', { radius: 12 }),
  exB1: await framed('demo-excel-01-input-values.png', [30, 182, 1350, 545], 'c-ex-b1', { radius: 12 }),
  exB2: await framed('demo-excel-01-input-values.png', [30, 1158, 1350, 1430], 'c-ex-b2', { radius: 12 }),
};

// ═════════════════════════════ 슬라이드 ═════════════════════════════

// 1. 제목 ─────────────────────────────────────────────
{
  pres.addSection({ title: '제목' });
  const s = pres.addSlide({ masterName: 'TITLE', sectionTitle: '제목' });
  if (process.env.QA_FLAT) s.addImage({ path: bgTitle, x: 0, y: 0, w: W, h: H }); // 미리보기 도구용(배경 이미지를 못 그리는 도구 대비). 실제 배포 파일에는 넣지 않는다.
  txt(s, 'LOCO 2.0 · 현장 자세 분석', { x: 0.9, y: 1.35, w: 7, h: 0.45, fontSize: 18, bold: true, color: 'C9CCFF', charSpacing: 1 });
  s.addText([{ text: '사진과 한 문장으로 시작하는', options: { breakLine: true } }, { text: '근골격계 유해요인조사' }], { placeholder: 'title', lang: 'ko-KR' });
  s.addText('11개 법정 기준 초안과 REBA 점수를,\n필요한 것만 물어 Excel까지', { placeholder: 'sub', lang: 'ko-KR' });
  txt(s, '팀 LOCO  ·  Windows 데스크톱 앱 (Electron + Python)', { x: 0.9, y: 6.25, w: 8, h: 0.4, fontSize: 16, color: WHITE });
  txt(s, '점수와 해당 여부는 조사자가 검토해 정하는 보조 도구입니다.', { x: 0.9, y: 6.72, w: 8, h: 0.32, fontSize: 13, color: 'B9BDF5' });
  s.addNotes(`[여는 말 · 약 30초]
- 안녕하세요, LOCO 팀입니다. LOCO는 사진 한 장과 한 문장으로 근골격계 유해요인조사를 시작하게 해 주는 Windows 데스크톱 앱입니다.
- 오늘 순서: ① 기획의도(시작 배경·기대 효과) ② 프로그램 개발 환경 ③ 사용 방법 ④ 시연 ⑤ 향후 계획 ⑥ 질문.
- 처음에 한 가지만 먼저 말씀드립니다. 화면에 나오는 점수와 해당 여부는 '초안'이고, 최종 판단은 조사자가 합니다. 그리고 오늘 보여 드리는 시험은 공개 사진으로 한 것이며 현장 사진으로 한 시험은 아닙니다.

[발표 준비 메모 — 청중에게 말하지 않는 내용]
- 발표자 이름·발표일은 이 슬라이드에 직접 적어 넣으세요(자료에는 팀 이름만 넣었습니다).
- 전체 16장입니다. 시연(8~13번)을 뺀 10장을 장당 1~1.5분으로 말하면 약 10~15분이고, 시연은 실제 앱 시간이 따로 듭니다. 시간이 모자라면 5번(시험 체계)과 7번(사용 방법 ②)을 한두 문장으로 넘겨도 흐름이 이어집니다.
- 이 자료의 숫자와 화면 캡처는 ${FACTS.asOf} 시험 기록(docs/presentation/TEST_FACTS.md, 한 페이지 입력 반영본) 기준입니다. 코드는 원격 브랜치 fix/quickflow-score-so-far-20261026에 네 커밋으로 푸시되어 있습니다(맨 위가 457b5f5). fcfa0a5: 확정 전 점수·체크리스트·'1차 점수를 AI보다 먼저 보여 주기'·추론 강도 high / f66f103: 입력 한 페이지, 저장 뒤 다시 묻지 않음(사용 방법 7번, 시연 10·11번) / 4fb3dc3: AI 요청이 120초 안에 답이 없으면 같은 요청을 다시 보냄(14·15번) / 457b5f5: 점수에 안 쓰이는 입력 4묶음(수시조사 사유·작업장 상황·근로자 참여·증상조사)을 묻지도 보여주지도 받지도 않음.
- 시험 숫자와 화면 캡처는 f66f103 시점의 실제 앱 실행 기록입니다. 시험 개수(Python ${FACTS.pythonTests}·프런트엔드 ${FACTS.frontendFiles}개 파일)는 커밋 457b5f5(범위 정리, 2026-10-27) 기준입니다. 4fb3dc3의 120초 재전송은 실제 AI로 시험하지 못했습니다(14번 노트). 발표 직전에 코드와 docs/가 바뀌었는지는 다시 확인하세요.`);
}

// 2. 시작 배경 ─────────────────────────────────────────
{
  pres.addSection({ title: '발표 기획의도' });
  const s = contentSlide('발표 기획의도', '시작 배경: 모아야 할 근거가 많다', `[말할 내용 · 약 1분 30초]
- 근골격계 유해요인조사는 작업을 11개 부담작업 기준(고용노동부고시 제2020-12호, 프로젝트 문서 기준)에 비춰 하나하나 따져 기록하는 일입니다.
- 어려움 ① 기준이 겹칩니다. 한 작업이 여러 호에 해당할 수 있고, 작업 이름만으로는 호가 정해지지 않습니다. 그래서 LOCO는 상자 들기든 사무 작업이든 같은 '일반 작업'으로 입력받습니다.
- 어려움 ② 사진에는 나오지 않는 사실이 있습니다. 하루 몇 시간, 몇 번, 몇 kg인지는 조사자가 확인해서 적어야 합니다.
- 어려움 ③ 그런데 질문이 많으면 쓰기 힘듭니다. 우리가 직접 써 보면서 '질문이 많다', 'Excel에서도 입력을 너무 많이 요구한다'는 지적이 나왔고(2026-10-23·24 개발 기록), 이것이 이번 개발의 큰 방향이었습니다.
- 그래서 설계 원칙은 세 가지입니다. 입력은 줄이고(한 문장·사진에서 읽은 값은 다시 묻지 않기), 근거는 남기고(값마다 출처 표시), 판단은 조사자가(AI는 점수·판정을 바꾸지 않음).
- 첫 사용자는 현장 조사자와 안전보건 담당자로 잡았습니다(요구사항 문서 8장).

[주의]
- 법령 조항·조사 주기·수치는 슬라이드에 쓰지 않았습니다. 고시 번호는 저장소 문서(기능정의서 3장)가 근거로 삼은 것이며, 법령 원문과 대조하지는 않았습니다. 질문이 나오면 "법령의 최신 개정과 현장 적용 해석은 별도로 확인해야 한다"고 답하세요.
- '질문이 많다'는 지적은 팀 안에서 써 본 사용자의 의견이지 현장 조사 결과가 아닙니다.`);
  const cards = [
    ['FiLayers', '기준이 겹칩니다', '한 작업이 여러 호에 걸리고, 작업 이름만으로는 정해지지 않습니다.'],
    ['FiEye', '사진엔 없는 사실', '하루 시간·횟수·무게·힘은 조사자가 직접 확인해 적어야 합니다.'],
    ['FiEdit3', '입력이 많으면 부담', '써 보니 ‘질문이 많다’, ‘Excel 입력 요구가 많다’는 지적이 나왔습니다.'],
  ];
  const cw = 3.92, gap = (CW - 3 * cw) / 2;
  for (let i = 0; i < 3; i++) {
    const x = MX + i * (cw + gap), y = 1.8;
    box(s, x, y, cw, 3.5, { shadow: true, name: `배경 카드 ${i + 1}` });
    await iconDot(s, cards[i][0], x + 0.35, y + 0.35, 0.85, { alt: cards[i][1] });
    txt(s, cards[i][1], { x: x + 0.35, y: y + 1.4, w: cw - 0.7, h: 0.62, fontSize: 24, bold: true, color: INDIGO });
    txt(s, cards[i][2], { x: x + 0.35, y: y + 2.07, w: cw - 0.7, h: 1.3, fontSize: 17, color: SUB, lineSpacingMultiple: 1.12 });
  }
  box(s, MX, 5.55, CW, 1.3, { fill: INDIGO, radius: 0.18, name: '출발점 배너' });
  txt(s, '입력은 줄이고, 근거는 남기고, 판단은 조사자가', { x: MX + 0.5, y: 5.68, w: CW - 1, h: 0.65, fontSize: 28, bold: true, color: WHITE, valign: 'middle' });
  txt(s, '첫 사용자: 현장 조사자와 안전보건 담당자', { x: MX + 0.5, y: 6.33, w: CW - 1, h: 0.42, fontSize: 16, color: 'C9CCFF' });
}

// 3. 기대 효과 ─────────────────────────────────────────
{
  const s = contentSlide('발표 기획의도', '기대 효과: 목표이며, 입증 전입니다', `[말할 내용 · 약 1분]
- 이 슬라이드의 네 가지는 모두 '기대'입니다. 입증했다고 말하지 마세요.
- ① 기록 누락 줄이기: 11개 기준마다 입력·누락·계산 초안·조사자 결론이 이어져서 빠진 근거가 눈에 보이게 하는 것이 설계 목표입니다. 요구사항 문서도 "의미 있는 성과는 포즈 인식 시연보다 조사 기록의 누락을 줄이고 같은 입력에서 같은 계산 근거를 재현하는 것"이라고 적습니다.
- ② 입력 부담 줄이기: 사진과 한 문장에서 읽은 값은 저장하고 부족한 부분만 묻습니다. 시험 기록으로는 키보드 사진 1장 + 문장 1개로 최종 결과까지 조작이 ${FACTS.interactions}회였습니다(한 페이지 입력, 실제 AI). 이전 방식(결과를 본 뒤 다시 여는 두 번째 입력 창)은 ${FACTS.interactionsBefore}회였습니다. 다만 처음의 칸별 입력 방식과 비교한 측정은 없어서 "몇 배 줄었다"고는 말하지 않습니다.
- ③ 같은 입력, 같은 계산: 11개 기준과 REBA는 버전이 고정된 규칙 엔진(MOEL_2020_12_GENERAL_V2)이 계산하고, AI는 계산 결과를 바꾸지 못합니다.
- ④ 조사 시간 단축은 가설입니다. 요구사항 문서의 목표는 실제 조사자 3~5명이 같은 작업 사례를 수기로 정리한 과정과 LOCO로 정리한 과정을 비교해 입력부터 보고서까지 걸린 시간의 중앙값을 30% 이상 줄이는 것입니다. 이 측정은 아직 하지 않았고, 문서에도 "측정하기 전까지 목표이지 성과 주장이 아니다"라고 적혀 있습니다.
- 아래 주황 상자는 소리 내어 읽어 주세요: 효과 미측정, 의학적 효과·법적 적합성 미입증, 최종 판단은 조사자.`);
  const items = [
    ['FiCheckCircle', '기록 누락 줄이기', '11개 기준마다 입력·누락·계산 초안·조사자 결론이 이어져, 빠진 근거가 눈에 보입니다.'],
    ['FiZap', '입력 부담 줄이기', '사진과 한 문장에서 읽은 값은 저장하고, 부족한 부분만 묻습니다.'],
    ['FiRepeat', '같은 입력, 같은 계산', '버전이 고정된 규칙으로 계산해, 같은 입력이면 같은 근거가 재현됩니다.'],
    ['FiClock', '조사 시간 단축 (가설)', '입력부터 보고서까지 걸리는 시간의 중앙값을 수기보다 30% 이상 줄이는 것이 목표입니다. 측정 전입니다.'],
  ];
  const cw = 5.95, ch = 2.0, gx = CW - 2 * cw;
  for (let i = 0; i < 4; i++) {
    const x = MX + (i % 2) * (cw + gx), y = 1.75 + Math.floor(i / 2) * (ch + 0.2);
    box(s, x, y, cw, ch, { shadow: true, name: `기대 카드 ${i + 1}` });
    await iconDot(s, items[i][0], x + 0.28, y + 0.3, 0.74, { alt: items[i][1], bg: i === 3 ? AMBER : VIOLET, fg: i === 3 ? INK : WHITE });
    txt(s, items[i][1], { x: x + 1.25, y: y + 0.2, w: cw - 1.5, h: 0.55, fontSize: 22, bold: true, color: INDIGO });
    txt(s, items[i][2], { x: x + 1.25, y: y + 0.78, w: cw - 1.5, h: 1.12, fontSize: 16, color: SUB, lineSpacingMultiple: 1.1 });
  }
  amberNote(s, '※ 위 내용은 설계 의도와 목표입니다. 시간 단축 같은 효과는 측정하지 않았고, 의학적 효과와 법적 적합성은 입증하지 않았습니다. 점수·해당 여부는 조사자가 검토해 정합니다.', MX, 6.1, CW, 0.82, { size: 15 });
}

// 4. 개발 환경 ① 구성과 기술 ───────────────────────────
{
  pres.addSection({ title: '프로그램 개발 환경' });
  const s = contentSlide('프로그램 개발 환경', '구성과 기술: 화면·서비스·계산·저장', `[말할 내용 · 약 1분 30초]
- 구조는 한 줄입니다: Electron 화면 → preload → Python JSON Lines 서비스 → 기능 모듈 → SQLite. 화면은 계산하지 않고 Python 서비스에 요청만 합니다.
- 화면: Electron 44.7(frontend/package.json), 프레임워크 없이 네이티브 ES module로 만들었습니다. 지금 보시는 '간편 흐름'은 frontend/quick-flow.js입니다.
- 서비스: CPython 3.12. 실행 서비스는 ergo/service/json_lines.py 하나입니다(옛 가짜 서비스·별도 샘플 서버는 제거).
- 계산: 규칙 엔진이 11개 기준과 REBA를 각각 계산합니다. 높은 REBA를 곧바로 '법정 해당'으로, 낮은 REBA를 '해당 없음'으로 바꾸지 않고, 두 결과를 한 점수로 합치지도 않습니다.
- 자세: MediaPipe Pose Landmarker Heavy(mediapipe 1.1.1)가 기본이고 관절 33점을 냅니다. Full 모델과 예전 MoveNet Lightning(17점)은 설정에서 고를 수 있습니다.
- AI: OpenAI 호환 API. 모델은 gpt-6-luna, 추론 강도는 high입니다(기본값. 2026-10-26에 소유자 지시로 xhigh에서 낮춤). 환경변수 OPENAI_API_KEY로 키를 주며 키는 화면(renderer)·SQLite·패키지에 저장하지 않습니다. OPENAI_BASE_URL로 호환 서버를 지정할 수도 있습니다.
- 저장: SQLite 테이블 여섯 개(SURVEY, TASK, PHOTO, ANALYSIS, APP_SETTINGS, EXPORT_LOG). 규칙과 계산은 DB에 넣지 않고, 분석 결과는 바뀌지 않는 snapshot으로 저장합니다.
- 출력: Excel(openpyxl 3.1). 미리보기와 저장 파일은 같은 시트 정의에서 나옵니다. 배포는 scripts/build_windows.py가 포터블 폴더(LOCO.exe)를 만듭니다.

[질문 대비]
- "사진이 외부로 나가나요?" → AI 사진 관찰을 쓰면 사진(EXIF를 제거한 JPEG)이 AI API로 전송됩니다. 키와 이미지 base64는 저장하지 않습니다(docs/photo-vision.md). 현장에 도입하기 전에 사내 보안 정책 확인이 필요합니다.`);
  const cols = [
    { x: 0, w: 2.6, name: '화면', ic: 'FiMonitor', chips: [['Electron 44.7', 'Windows 데스크톱 앱'], ['ES module', '프레임워크 없이 만든 화면']] },
    { x: 0, w: 2.6, name: '서비스', ic: 'FiServer', chips: [['Python 3.12', 'JSON Lines 서비스'], ['하나의 실행 서비스', '화면은 요청만 보냅니다']] },
    { x: 0, w: 3.2, name: '계산 · AI', ic: 'FiCpu', chips: [['규칙 엔진', '법정 11개 기준 · REBA'], ['MediaPipe · 관절 33점', 'Pose Landmarker Heavy'], ['OpenAI 호환 API', 'gpt-6-luna · 추론 강도 high']] },
    { x: 0, w: 2.6, name: '저장 · 출력', ic: 'FiDatabase', chips: [['SQLite · 테이블 6개', '조사 · 작업 · 사진 · 분석 · 설정 · 출력 이력'], ['Excel 출력', 'openpyxl 3.1 · 저장 전 미리보기']] },
  ];
  const gapC = (CW - cols.reduce((a, c) => a + c.w, 0)) / 3;
  let cx = MX;
  const top = 1.75, ch = 4.3;
  for (let i = 0; i < cols.length; i++) {
    const c = cols[i]; c.x = cx;
    box(s, cx, top, c.w, ch, { fill: SURFACE, name: `${c.name} 층` });
    await iconDot(s, c.ic, cx + 0.2, top + 0.2, 0.56, { alt: c.name });
    txt(s, c.name, { x: cx + 0.9, y: top + 0.2, w: c.w - 1.0, h: 0.56, fontSize: 20, bold: true, color: INDIGO, valign: 'middle' });
    const n = c.chips.length, chH = n === 3 ? 0.98 : 1.3, chGap = 0.12;
    c.chips.forEach(([a, b], k) => {
      const y = top + 0.98 + k * (chH + chGap);
      box(s, cx + 0.16, y, c.w - 0.32, chH, { fill: WHITE, radius: 0.12, name: `${c.name} 항목 ${k + 1}` });
      txt(s, a, { x: cx + 0.3, y: y + 0.1, w: c.w - 0.6, h: 0.38, fontSize: 15, bold: true, color: INK });
      txt(s, b, { x: cx + 0.3, y: y + 0.5, w: c.w - 0.6, h: chH - 0.58, fontSize: b.length > 28 ? 12 : 13.5, color: SUB, lineSpacingMultiple: 1.05 });
    });
    if (i < cols.length - 1) arrow(s, cx + c.w + 0.05, top + 0.48, cx + c.w + gapC - 0.05, { width: 3 });
    cx += c.w + gapC;
  }
  box(s, MX, 6.22, CW, 0.7, { fill: INDIGO, radius: 0.14, name: '원칙 배너' });
  txt(s, '계산·판정은 규칙 엔진이, AI는 문장 정리·사진 설명·설명문만 — 점수와 판정은 바꾸지 못합니다', { x: MX + 0.35, y: 6.22, w: CW - 0.7, h: 0.7, fontSize: 18, bold: true, color: WHITE, valign: 'middle' });
}

// 5. 개발 환경 ② 시험 체계 ─────────────────────────────
{
  const s = contentSlide('프로그램 개발 환경', '시험 체계: 숫자로 보는 확인 범위', `[말할 내용 · 약 1분]
- 계산은 시험으로 확인합니다: Python 시험 ${FACTS.pythonTests}개(커밋 457b5f5 기준). 알려진 환경 문제 1개는 PDF 시험에 쓰는 pdfplumber가 이 PC 환경에 설치되어 있지 않아서입니다. 이 밖에 가끔 실패하는 오래된 시험 2개(test_intake_evidence의 absence replay, test_no_repeat_questions의 weight 시험)가 있고 수정 전 기준 커밋의 복사본에서도 같았습니다(커밋 fcfa0a5 검증 기록: 혼자 돌리면 10회 중 5회·9회 통과). 사용자 출력은 Excel이며 PDF는 내부 구현입니다.
- 화면은 실제 앱으로 확인합니다: 프런트엔드 시험 ${FACTS.frontendFiles}개 파일이 전부 통과했습니다(커밋 457b5f5 기준). 그리고 실제 Electron 앱(숨김 창)을 화면에서 누르는 방식으로 처음부터 끝까지 돌렸고, 뒤쪽은 실제 Python 서비스·실제 MediaPipe Pose Landmarker Heavy·실제 외부 AI(gpt-6-luna)입니다.
- 독립 검토를 두 번 받았고, 두 번째 검토가 찾은 결함 ${FACTS.defects}건(중요 1·보통 5·사소 6)을 모두 고쳤습니다.
- 공개 사진 4종으로 끝까지 갔습니다: 키보드 작업, 상자 들어 올리기, 재봉틀 작업, 두 사람이 함께 나온 사진(사진을 쓰지 않는 경로). 모두 최종 REBA 점수, 법정 11개 기준 초안, Excel 미리보기까지 나왔습니다.
- 가장 중요한 한계: 이 시험은 공개 사진(Wikimedia Commons)으로 했습니다. 우리 현장에서 찍은 사진으로 한 시험이 아닙니다. 현장 사진 정확도는 말씀드릴 수 없습니다.
- 그 밖에 일부러 규칙을 망가뜨려 시험이 잡아내는지 보는 변이 시험(tests/mutation)과 계약 점검(scripts/audit_contract.py)도 있습니다.
- 모든 숫자는 ${FACTS.asOf} 시점의 기록입니다. 코드가 더 바뀌면 시험 개수도 달라지니 발표 직전에 다시 확인하세요.`);
  const stats = [
    [String(FACTS.pythonTests), 'Python 시험', '환경 문제 1개(pdfplumber 미설치)와 간헐 실패 2개'],
    [String(FACTS.frontendFiles), '프런트엔드 시험 파일', '전부 통과'],
    [String(FACTS.defects), '독립 검토에서 고친 결함', '2회 검토 · 중요 1 · 보통 5 · 사소 6'],
    ['4', '끝까지 돌린 공개 사진', '키보드·상자·재봉틀·두 사람'],
  ];
  const cw = 2.85, gap = (CW - 4 * cw) / 3;
  stats.forEach(([num, label, sub], i) => {
    const x = MX + i * (cw + gap), y = 1.75;
    box(s, x, y, cw, 3.45, { shadow: true, name: `수치 카드 ${i + 1}` });
    txt(s, num, { x: x + 0.3, y: y + 0.1, w: cw - 0.6, h: 1.42, fontSize: 64, bold: true, color: VIOLET, valign: 'middle' });
    txt(s, label, { x: x + 0.3, y: y + 1.56, w: cw - 0.6, h: 0.88, fontSize: 19, bold: true, color: INDIGO });
    txt(s, sub, { x: x + 0.3, y: y + 2.46, w: cw - 0.6, h: 0.92, fontSize: 14, color: SUB, lineSpacingMultiple: 1.08 });
  });
  // 실제로 이어 돌린 순서
  const steps = ['실제 Electron 앱', '실제 Python 서비스', '실제 MediaPipe', '실제 AI (gpt-6-luna)'];
  const sw = 2.6, sg = (CW - 4 * sw) / 3, sy = 5.4;
  steps.forEach((t, i) => {
    const x = MX + i * (sw + sg);
    chip(s, t, x, sy, { fill: SURFACE, fg: INDIGO, size: 15, h: 0.5, w: sw });
    if (i < 3) arrow(s, x + sw + 0.04, sy + 0.25, x + sw + sg - 0.04, { width: 2.5 });
  });
  txt(s, `${FACTS.asOf}, 숨김 창에서 처음부터 끝까지 이어서 돌린 구성`, { x: MX, y: 5.98, w: CW, h: 0.3, fontSize: 13, color: MUTED });
  amberNote(s, '공개 사진으로 한 시험입니다. 우리 현장에서 찍은 사진으로 한 시험이 아닙니다.', MX, 6.32, CW, 0.62, { size: 17 });
}

// 6. 사용 방법 ① ─────────────────────────────────────
{
  pres.addSection({ title: '프로그램 사용 방법' });
  const s = contentSlide('프로그램 사용 방법', '① 입력부터 1차 점수까지', `[말할 내용 · 약 1분 30초]
- 사용자가 하는 일은 사진과 한 문장입니다. 나머지는 LOCO가 합니다.
- 1) 사진 올리기: 옆에서 찍은 작업자 전신 사진이 있으면 관절 각도로 1차 REBA 점수를 바로 보여 줍니다. 왼쪽·정면(또는 후면)·오른쪽 3칸이 있고 한 장만 넣어도 됩니다. 사진을 넣으면 먼저 자르기 영역을 확인합니다.
- 2) 한 문장으로 설명: '1년에 며칠, 하루 몇 시간, 들기는 무게와 하루 횟수·1분에 몇 번, 충격·반복·같은 자세 유지가 있는지'를 적으면 질문이 줄어듭니다(앱의 안내 문구 그대로입니다).
- 3) 분석: '사진·작업 설명 정리' 버튼을 누르면 AI가 문장에서 시간·일수·작업 특징을 칸에 채우고, MediaPipe가 사진에서 관절 각도를 잽니다. AI가 사진 속 동작을 말로도 설명합니다. AI 정리는 보통 1분 안팎이고 4분 넘게 걸린 적도 있습니다.
- 4) 1차 점수: AI를 기다리지 않고 사진 측정만으로 나온 점수를 먼저 보여 줍니다(분석을 누른 뒤 ${firstScoreText}, 세 번 실측). 그동안 화면에는 "AI가 사진과 작업 설명을 정리하고 있어요. 1차 점수는 먼저 보여 드려요." 상태 줄이 나오고 보내는 버튼은 잠깁니다. 점수는 '확정 전'이고, 못 잰 항목은 '부담 없음'으로 가정했다고 화면에 적혀 있으며 실제 점수는 더 높을 수 있습니다.
- 아래 띠는 앱에 실제로 있는 안내 문구입니다.`);
  const steps = [
    ['사진 올리기', '옆에서 찍은 전신 사진 1~3장을 올리고 자릅니다. 한 장만 넣어도 됩니다.', '조사자'],
    ['한 문장으로 설명', '예: ‘키보드와 마우스로 입력하는 작업을 하루 8시간 합니다.’', '조사자'],
    ['분석', 'AI가 문장에서 시간·작업 특징을 채우고, MediaPipe가 관절 각도를 잽니다.', 'LOCO'],
    ['1차 점수', '몇 초 안에 AI보다 먼저 나옵니다. ‘확정 전’이며 못 잰 항목은 ‘부담 없음’으로 가정합니다.', 'LOCO'],
  ];
  const cw = 2.85, gap = (CW - 4 * cw) / 3, y = 1.75, ch = 3.75;
  for (let i = 0; i < 4; i++) {
    const x = MX + i * (cw + gap), auto = steps[i][2] === 'LOCO';
    box(s, x, y, cw, ch, { shadow: true, name: `단계 ${i + 1}` });
    badge(s, i + 1, x + 0.25, y + 0.28, 0.66, { bg: auto ? VIOLET : INDIGO });
    const cwid = auto ? 1.3 : 0.95;
    chip(s, auto ? 'LOCO 자동' : '조사자', x + cw - 0.25 - cwid, y + 0.45, { fill: auto ? VIOLET : WHITE, fg: auto ? WHITE : INDIGO, size: 13, w: cwid, line: auto ? undefined : LINE });
    txt(s, steps[i][0], { x: x + 0.25, y: y + 1.2, w: cw - 0.5, h: 0.85, fontSize: 21, bold: true, color: INDIGO, lineSpacingMultiple: 1.0 });
    txt(s, steps[i][1], { x: x + 0.25, y: y + 2.1, w: cw - 0.5, h: 1.65, fontSize: 16, color: SUB, lineSpacingMultiple: 1.1 });
    if (i < 3) arrow(s, x + cw + 0.03, y + 0.61, x + cw + gap - 0.03, { width: 2.5 });
  }
  box(s, MX, 5.75, CW, 1.1, { fill: SURFACE, radius: 0.14, name: '앱 안내 문구' });
  await iconDot(s, 'FiMessageSquare', MX + 0.25, 6.05, 0.5, { alt: '말풍선', bg: VIOLET });
  txt(s, [
    { text: '문장에 이런 것을 적으면 질문이 줄어요 (앱 안내): ', options: { bold: true, color: INDIGO } },
    { text: '1년에 며칠 하는지, 하루 총 몇 시간 일하는지, 들기는 무게와 하루 횟수·1분에 몇 번인지, 충격·반복·같은 자세 유지가 있는지 없는지.' },
  ], { x: MX + 0.95, y: 5.75, w: CW - 1.25, h: 1.1, fontSize: 16, color: SUB, valign: 'middle', lineSpacingMultiple: 1.1 });
}

// 7. 사용 방법 ② ─────────────────────────────────────
{
  const s = contentSlide('프로그램 사용 방법', '② 한 페이지에서 확인하고 Excel까지', `[말할 내용 · 약 1분 30초]
- 5) 입력 창은 한 번만 열립니다. AI 정리가 끝나면 '작업 정보를 한 번에 확인해 주세요' 창이 열리고, 한 페이지 안에 작업 특징 → 작업 조건 → 사진 확인 → 자세 체크리스트 → 사진이 못 읽은 각도가 차례로 있습니다. 모두 고르기로 답하고, 숫자 칸에도 선택지(예: 연 220일, 하루 480분)가 있으며 직접 입력도 됩니다. 모르면 비워 두면 '미확인'으로 남습니다. 사진 상황('한 사람의 전신이 나온 평소 모습인가요?')을 고르면 같은 창에 체크리스트가 나타납니다.
- 6) 체크리스트: 해당하는 자세에만 체크합니다. '확인 끝 · 체크 안 한 항목은 해당 없음'을 눌러야 나머지가 '해당 없음'으로 채워지고, 누르지 않고 저장하면 '미확인'으로 남습니다. 사진이 이미 잰 값은 묻지 않고, 사진이 못 읽은 각도만 선택칸으로 묻습니다. 한쪽 팔·손목을 정하면 '왼쪽(오른쪽) 팔·손목은 오른쪽(왼쪽)과 같아요'로 복사할 수 있습니다.
- 7) '저장하고 결과 보기 →': 최종 REBA 점수와 법정 11개 기준의 계산 초안(해당 초안 / 입력 필요 / 해당 없음)이 나옵니다. 저장한 뒤에는 화면이 스스로 다시 묻지 않습니다. 비워 둔 칸이 있으면 결과 화면의 '입력 수정하기'를 눌러야만 같은 페이지가 다시 열립니다. 두 결과(REBA·11개 기준)는 한 점수로 합치지 않고, 최종 해당 여부는 조사자가 검토해 정합니다.
- 8) Excel: 저장하기 전에 시트 탭으로 미리 볼 수 있고, 'Excel로 저장'으로 파일을 만듭니다. 'AI 설명 확정'(검토하고 설명 만들기)은 선택입니다.
- 아래 색 띠는 앱 결과 화면의 REBA 위험 단계(1점 무시 가능, 2~3점 낮음, 4~7점 보통, 8~10점 높음, 11~15점 매우 높음)와 같은 색입니다.

[코드 위치] '입력 한 페이지'는 커밋 f66f103으로 푸시되어 있습니다(TEST_FACTS.md '코드가 올라간 곳'). 옛 두 단계 입력 창(작업 특징 → 작업 조건, 결과 후 다시 열림)은 쓰지 않습니다.`);
  const rows = [
    ['입력 창은 한 번만', '조사자', 'AI 정리가 끝나면 작업 특징·조건·사진 확인·체크리스트·각도가 한 대화상자에 나옵니다.'],
    ['체크 → ‘확인 끝’', '조사자', '해당 자세만 체크 → 나머지는 ‘해당 없음’. 못 읽은 각도만 고르고, 한쪽 팔은 반대쪽으로 복사합니다.'],
    ['저장하고 결과 보기', 'LOCO + 조사자', '최종 REBA 점수와 기준별 초안. 저장하면 다시 묻지 않고, 최종 판단은 조사자 몫입니다.'],
    ['Excel 미리보기 → 저장', '조사자', '저장될 시트를 먼저 확인하고 ‘Excel로 저장’합니다. 설명 확정은 선택입니다.'],
  ];
  const rh = 1.0, rg = 0.1, y0 = 1.75;
  for (let i = 0; i < 4; i++) {
    const y = y0 + i * (rh + rg), who = rows[i][1];
    box(s, MX, y, CW, rh, { fill: SURFACE, name: `단계 ${i + 5}` });
    badge(s, i + 5, MX + 0.25, y + (rh - 0.6) / 2, 0.6, { bg: i === 2 ? INDIGO : VIOLET });
    txt(s, rows[i][0], { x: MX + 1.1, y, w: 3.3, h: rh, fontSize: 21, bold: true, color: INDIGO, valign: 'middle', lineSpacingMultiple: 1.0 });
    chip(s, who, MX + 4.55, y + (rh - 0.32) / 2, { fill: who === '조사자' ? WHITE : VIOLET, fg: who === '조사자' ? INDIGO : WHITE, size: 13, line: who === '조사자' ? LINE : undefined });
    txt(s, rows[i][2], { x: MX + 6.3, y, w: CW - 6.3 - 0.25, h: rh, fontSize: 15, color: SUB, valign: 'middle', lineSpacingMultiple: 1.08 });
  }
  // REBA 위험 단계 색 띠 (앱 결과 화면과 같은 색·구간)
  const ly = 6.2, sq = 0.34, sg2 = 0.05;
  txt(s, 'REBA 위험 단계', { x: MX, y: ly, w: 1.9, h: sq, fontSize: 14, bold: true, color: INDIGO, valign: 'middle' });
  const colorOf = n => n === 1 ? REBA.r1 : n <= 3 ? REBA.r23 : n <= 7 ? REBA.r47 : n <= 10 ? REBA.r810 : REBA.r1115;
  for (let n = 1; n <= 15; n++) {
    s.addText(String(n), { isTextBox: true, shape: SHAPE.roundRect, x: MX + 1.95 + (n - 1) * (sq + sg2), y: ly, w: sq, h: sq, rectRadius: 0.06, fill: { color: colorOf(n) }, line: { type: 'none' },
      color: n === 1 || n >= 11 ? WHITE : INK, bold: true, fontSize: 11, fontFace: FONT, align: 'center', valign: 'middle', margin: 0, lang: 'ko-KR', objectName: `REBA ${n}점` });
  }
  txt(s, '1점 무시 가능 · 2~3점 낮음 · 4~7점 보통 · 8~10점 높음 · 11~15점 매우 높음  (앱 결과 화면의 색상바와 같은 구간)', { x: MX + 1.95, y: ly + 0.42, w: CW - 1.95, h: 0.3, fontSize: 13, color: SUB });
}

// 8. 시연 1~3 사진·한 문장 ───────────────────────────────
{
  pres.addSection({ title: '시연' });
  const s = contentSlide('시연', '사진을 올리고 한 문장 쓰기', `[시연 시작 — 앱 화면으로 전환 · 큐카드 1~3 · 약 1분]
대본·큐카드·플랜 B의 정본은 docs/presentation/demo/시연-시나리오.md 입니다. 이 슬라이드(8번)부터 13번까지는 같은 순서의 앱 화면 캡처이고, 라이브 시연이 막히면 이 캡처로 같은 순서·같은 대본으로 설명하세요. 슬라이드 위쪽의 '시연 1~3' 같은 표시가 큐카드 번호입니다.
전체 길이는 보통 7분(AI 대기 포함)이고 4분 압축판이 있습니다. 핵심 메시지 3개: ① 첫 점수는 몇 초 안에 나온다 ② 입력은 한 페이지에서 끝나고 다시 묻지 않는다 ③ 해당 여부와 점수는 조사자가 검토해 정한다.

[시작 대사 · 20초]
"지금부터 실제 앱으로 보여 드리겠습니다. 사진은 현장 사진이 아니라 공개 사진이고, 한 장과 문장 하나로 시작합니다."

[시연 전 준비]
- 하루 전과 시연 10분 전: PowerShell에서 docs\\presentation\\demo 폴더로 가서 .\\prepare-demo.ps1 을 실행합니다(시연용 새 DB 만들기, AI 설정, 가상환경·Electron·자세 모델·시연 사진·AI 키·AI 연결 점검. 모두 [OK]여야 하고 [!!]가 나오면 뒤에 적힌 해결 방법을 따릅니다). 이어서 .\\start-demo.ps1 로 앱을 열어 첫 화면('＋ 새 분석 시작')에서 멈춰 둡니다. 하루 전에는 한 번 끝까지 돌려 둡니다(첫 분석은 자세 모델을 불러오느라 몇 초 더 걸릴 수 있습니다).
- demo\\photos 폴더를 바탕화면 LOCO-시연으로 복사해 두고, 시연-문장-키보드.txt 의 한 줄을 복사해 둡니다(직접 치면 오타와 시간이 듭니다).
- 전원 연결, 절전·화면 보호기·알림 끄기, 다른 앱 닫기, 해상도 1920×1080 이상, 앱 확대 100%(Ctrl+0). PowerPoint와는 Alt+Tab으로 오갑니다. 네트워크가 불안하면 휴대전화 핫스팟을 준비합니다.

[눌러야 할 순서]
 1) '＋ 새 분석 시작'.
 2) '왼쪽에서' 칸의 '사진 선택' → 파일 창에서 바탕화면 LOCO-시연의 01-키보드작업(CC0).jpg → 자르기 창에서 '선택 영역 등록'.
 3) '어떤 작업인가요?' 칸에 문장을 붙여 넣습니다: “키보드와 마우스로 입력하는 작업을 하루 8시간 합니다. 1년에 220일 일하고 일회성 작업은 아니에요. 다른 작업은 하지 않아요.”
 (분석 단추는 다음 슬라이드(9번)의 4번입니다.)

[대본 · 약 40초]
"사진 한 장과, 평소 말하듯이 쓴 문장 하나입니다. 서식을 채우는 게 아니라 이야기하듯 적습니다."

[막혔을 때]
- 앱이 안 열린다·너무 느리다: 슬라이드 8~13의 캡처로 같은 순서로 말합니다. 대본은 그대로 씁니다.
- 파일 선택 창이 사진을 못 찾는다: 바탕화면 LOCO-시연 폴더를 엽니다. 파일을 끌어다 놓아도 됩니다.
- 화면 글자가 너무 작거나 크다: Ctrl+0 으로 100%로 되돌립니다.
- 사진이 인식되지 않으면 다른 옆모습 전신 사진으로 바꿉니다. 사진을 쓰지 않는 경로도 있어 직접 질문으로 채울 수 있습니다.
- AI 키·네트워크가 없으면 AI 정리는 건너뛰고 첫 점수까지만 보입니다(prepare-demo.ps1 이 [!!]로 알려 줍니다). 질문 창에서 직접 고르면 계산은 계속됩니다(계산은 AI 없이 규칙 엔진이 합니다).
- 미리 한 번 돌려 둔 분석이 있으면 홈의 '이어서 하기'로 열 수 있습니다(작성 중인 분석은 이 PC에 보관됨).

[말할 내용]
- 사진은 공개 사진(CC0, Wikimedia Commons)이고 현장 사진이 아닙니다. 시연을 시작할 때 이 한 문장을 먼저 말합니다.
- 입력은 사진 한 장과 한 문장이 전부입니다. 칸마다 값을 일일이 넣지 않습니다.
- 시연 문장은 붙여 넣으므로 키보드로 치는 시간이 없습니다. 조작 횟수는 18회입니다(리허설 기록, 11번 노트).`, '시연 1~3');
  const h = 4.82, w = fitW(IMG.d01, h);
  s.addImage({ path: IMG.d01.path, x: MX, y: 1.72, w, h, altText: '사진을 올리고 작업을 한 문장으로 적은 LOCO 화면. 키보드 작업 사진 1장이 올라가 있다.', objectName: '화면 캡처: 사진과 한 문장' });
  const px = MX + w + 0.35, pw = W - MX - px;
  box(s, px, 1.72, pw, h, { fill: SURFACE, name: '시연 순서 1~3' });
  txt(s, '시연 순서 (큐카드 1~3)', { x: px + 0.3, y: 1.9, w: pw - 0.6, h: 0.5, fontSize: 22, bold: true, color: INDIGO });
  const steps = [
    [1, '‘＋ 새 분석 시작’', '홈 화면에서 누릅니다.', 0.85],
    [2, '‘사진 선택’ → ‘선택 영역 등록’', '‘왼쪽에서’ 칸에 키보드 작업 사진 1장(CC0)을 올립니다.', 1.1],
    [3, '‘어떤 작업인가요?’에 문장 붙여 넣기', '“키보드와 마우스로 입력하는 작업을 하루 8시간 합니다. 1년에 220일 일하고 일회성 작업은 아니에요. 다른 작업은 하지 않아요.”', 1.5],
  ];
  let sy = 2.55;
  for (const [n, head, body, hh] of steps) {
    badge(s, n, px + 0.3, sy + 0.04, 0.46);
    txt(s, [{ text: head, options: { bold: true, color: INDIGO, fontSize: 17, breakLine: true } }, { text: body }], { x: px + 1.15, y: sy, w: pw - 1.4, h: hh, fontSize: 15, color: SUB, lineSpacingMultiple: 1.08 });
    sy += hh + 0.12;
  }
  credit(s, '화면 속 사진: Apple-blogging-coder-36990.jpg · CC0 · Wikimedia Commons — 공개 사진이며 현장 사진이 아닙니다.', 6.66);
}

// 9. 시연 4~5 1차 점수가 먼저 나온다 ───────────────────────────
{
  const s = contentSlide('시연', '1차 점수는 AI보다 먼저 나옵니다', `[큐카드 4~5 · 약 1~1.5분]
[눌러야 할 순서]
 4) '사진·작업 설명 정리'를 누릅니다. 몇 초 안에(첫 점수 ${demoFirstScore}) '2. 자동 정리·1차 점수' 화면이 나오고, 위쪽에 "AI가 사진과 작업 설명을 정리하고 있어요. 1차 점수는 먼저 보여 드려요."가 뜹니다. 이 동안 버튼은 일부러 잠겨 있습니다(두 요청이 겹치지 않게 하려는 것입니다).
 5) AI가 끝날 때까지(보통 1~1.5분) 화면은 건드리지 않고 아래 이야기를 합니다. AI가 끝나면 입력 창이 저절로 한 번 열립니다(다음 슬라이드).

[AI가 도는 동안 말할 거리 — 가운데 것부터 쓰고, AI가 끝나면 그 자리에서 멈춥니다]
1. 첫 점수: "사진 한 장에서 관절 33개를 재서 먼저 낸 점수입니다. 아래팔이 88도, 왼쪽 1단계로 읽혔습니다."
2. 가정: "사진에 안 보이는 항목은 '부담 없음'으로 가정했다고 화면에 적혀 있습니다. 확정 점수가 아니라서 '확정 전'이라고 표시합니다."
3. AI가 지금 하는 일: "지금 AI가 둘을 합니다. 문장에서 시간·일수 같은 값을 칸에 옮기고, 사진 속 동작을 말로 설명합니다. 점수는 AI가 만들지 않습니다."
4. 왜 몇 초 만에 점수가 나오나: "예전에는 AI가 끝나야 화면이 나왔습니다. 지금은 사진 측정이 먼저 보이고, AI는 뒤에서 일합니다."
5. 시간: "AI는 보통 1분 남짓 걸립니다. 120초 안에 답이 없으면 같은 요청을 자동으로 다시 보냅니다."

[시간 근거]
- 첫 점수 ${demoFirstScore}: 단독 실행 실측 ${firstScoreText}, 리허설에서 두 개를 동시에 돌렸을 때 7.4초·9.9초(동시 실행이라 단독보다 늦었습니다).
- 리허설에서 AI까지 전부 끝나는 데 65.0초·87.3초가 걸렸습니다. 같은 작업을 high로 돌린 6번(TEST_FACTS.md 4번 + 리허설 2번)은 55·65·73·73·87초, 6번 중 1번은 256초였습니다. 그 한 번은 첫 AI 요청이 235초 만에 '불완전 응답'으로 끝나고 이어진 후속 호출이 같은 값을 채워 결과는 정상이었습니다. ${resendNote}
- 범위 정리(점수 계산에 쓰이지 않는 입력 4묶음 제거, 2026-10-27, 커밋 457b5f5) 뒤 같은 시연을 실제 AI로 한 번 더 돌렸을 때: 첫 점수 4.2초, 전부 끝남 81.9초, 입력 창 1번, 조작 18회, 최종 REBA 1점 · 무시 가능(한 번 돌린 값).

[화면 설명]
- 왼쪽: 사진 위에 MediaPipe가 관절을 찾아 각도를 잽니다(이 사진은 '아래팔 88.0°'). 점선·옅은 점은 '낮은 신뢰도·위치 확인 필요'를 뜻합니다.
- 오른쪽: 1차 REBA 점수 1점·무시 가능. 화면에 "사진에서 보이지 않는 항목은 부담 없음으로 가정한 1차 점수입니다. 질문에 답하면 달라질 수 있습니다."라고 적혀 있습니다. 사진에서 측정한 값은 '아래팔 굽힘 88° → 왼쪽 1단계'입니다. 못 잰 값을 몰래 채우지 않고 가정했다는 사실을 화면에 적는 것이 핵심입니다.
- 사진이 없거나 사진 측정만으로 점수를 내지 못하면 이 점수는 나오지 않고 상태 줄만 보입니다.
- 4분 압축판: 이 대기 이야기를 30초로 줄입니다.

[주의]
- 점수는 '확정 전'이며 시연 점수는 흐름 확인용입니다. 화면 속 사진은 CC0 공개 사진이며 현장 사진이 아닙니다.

[막혔을 때]
- 분석 뒤 AI 오류 문구(키·네트워크)가 나온다: 첫 점수는 정상입니다. "AI 없이도 점수는 먼저 나옵니다"로 넘어갑니다. 입력 창이 열리면 '문장으로 더 적기'를 열어 문장을 지우고 직접 고른 뒤 저장합니다(문장이 남아 있으면 저장 때 AI를 다시 부릅니다). 리허설에서 이 경로로 최종 점수까지 간 것을 확인했습니다.
- AI가 90초를 넘긴다: 첫 점수 화면을 계속 설명하고 질문을 받습니다. 120초에 자동으로 다시 보냅니다(최대 3번). 3분을 넘기면 슬라이드 10~13으로 넘어갑니다.
- 1차 점수가 나오지 않으면(사진 측정을 못 낸 경우): 상태 줄만 보입니다. 다른 옆모습 전신 사진으로 바꾸거나 캡처로 설명을 이어 갑니다.
- 대기 중인 요청은 앱을 끄지 마세요.`, '시연 4~5');
  const bh = fitH(IMG.op01banner, CW);
  s.addImage({ path: IMG.op01banner.path, x: MX, y: 1.65, w: CW, h: bh, altText: 'AI가 사진과 작업 설명을 정리하고 있어요. 1차 점수는 먼저 보여 드려요. 라는 상태 줄과 경과 시간, 진행 막대', objectName: '화면 캡처: AI 정리 중 상태 줄' });
  const ty = 1.65 + bh + 0.17, h = 3.7, w1 = fitW(IMG.op01photo, h), w2 = fitW(IMG.op01score, h);
  s.addImage({ path: IMG.op01photo.path, x: MX, y: ty, w: w1, h, altText: '키보드를 치는 작업자 사진 위에 MediaPipe가 잰 관절과 아래팔 88도 각도가 표시된 화면', objectName: '화면 캡처: 사진 위 관절 각도' });
  s.addImage({ path: IMG.op01score.path, x: MX + w1 + 0.25, y: ty, w: w2, h, altText: '1차 REBA 점수 1점 무시 가능, 점수별 위험 수준 색상바, 사진에서 측정한 값, 잠긴 버튼', objectName: '화면 캡처: 1차 점수' });
  const rx = MX + w1 + 0.25 + w2 + 0.4, rw = W - MX - rx;
  const call = [
    [4, '‘사진·작업 설명 정리’', `누르면 ${demoFirstScore} 안에 사진 측정만으로 나온 1차 점수가 먼저 보입니다.`],
    [5, 'AI가 끝날 때까지 기다립니다', '화면은 건드리지 않고 이야기합니다. AI는 보통 1~1.5분이고 그동안 버튼은 잠겨 있습니다.'],
    ['!', '‘확정 전’이라고 적습니다', '못 잰 항목은 ‘부담 없음’으로 가정했다고 화면에 적혀 있습니다.'],
  ];
  call.forEach(([n, a, b], i) => {
    const cy = ty + 0.02 + i * 1.25;
    badge(s, n, rx, cy, 0.46, n === '!' ? { bg: AMBER, fg: INK } : {});
    txt(s, a, { x: rx + 0.6, y: cy, w: rw - 0.6, h: 0.46, fontSize: 18, bold: true, color: INDIGO, valign: 'middle' });
    txt(s, b, { x: rx + 0.6, y: cy + 0.5, w: rw - 0.6, h: 0.72, fontSize: 14, color: SUB, lineSpacingMultiple: 1.05 });
  });
  credit(s, '화면 속 사진: Apple-blogging-coder-36990.jpg · CC0 · Wikimedia Commons — 공개 사진이며 현장 사진이 아닙니다. 점수는 확정 전 값입니다.', 6.5);
}

// 10. 시연 6 ①~④ 입력 창은 한 번만 열린다 ───────────────────────────
{
  const s = contentSlide('시연', '입력 창은 한 번만 열립니다', `[큐카드 6 ①~④ · 한 페이지 입력의 앞부분, 약 1분]
입력 창 제목은 "작업 정보를 한 번에 확인해 주세요"입니다. 이 창이 시연 중 처음이자 마지막 입력 창입니다. AI가 끝나면 저절로 한 번 열립니다.

[눌러야 할 순서와 대본]
 ① 맨 아래 접힌 '이미 확인한 정보 N개'를 열어서 AI가 문장에서 채운 값(키보드 작업, 하루 8시간, 연 220일 등)을 잠깐 보여 줍니다. → "이 값들은 제가 입력한 게 아니라 문장에서 AI가 옮겨 적은 것입니다. 다시 묻지 않습니다."
 ② '작업 특징' 아래의 '선택하지 않은 나머지 작업은 모두 안 해요'를 한 번 누릅니다. 위쪽 '작업 특징' 8개가 처음엔 모두 '모름 / 미확인'(왼쪽 캡처)이었다가 모두 '아니오'가 됩니다(오른쪽 캡처). → "나머지는 한 번에 '안 한다'로 채웁니다. 칸마다 답할 필요가 없습니다."
 ③ '사진 확인': "올린 사진이 모두 한 사람의 전신이 나온 평소 작업 모습인가요?" → '예, 모두 맞아요'. → "사진을 믿어도 되는지는 사람이 정합니다." 같은 창에 체크리스트가 나타납니다(다음 슬라이드).
 ④ '이 순간 손에 든 물건이나 미는 힘이 있나요?' → '없음'.
 (숫자 칸에도 선택지(예: 연 220일, 하루 480분)가 있고 직접 입력도 됩니다.)
 4분 압축판: ③⑤⑦만 말하고 ①④는 조용히 넘어갑니다.

[말할 내용]
- 예전에는 작업 특징 → 작업 조건 → 결과 → 다시 열림으로 같은 창을 세 번 만났습니다(중간에 두 번). 지금은 한 페이지에 모두 있고 저장하면 다시 열리지 않습니다(실제 앱 실행 4번에서 열림 횟수 1을 확인, 리허설 2번도 1번).
- 창 맨 위: "남은 확인 10개 · 모르면 비워 두세요(미확인으로 남아요)", "아직 확인하지 못한 항목만 보여 드려요. 이미 정리한 값은 다시 입력하지 않아도 돼요." 비워 둔 값을 0이나 '아니오'로 채우지 않는다는 원칙입니다(null과 실제 0을 구분).
- 창 아래에 '나중에 확인'도 있습니다. 화면의 진행 표시는 계산 완성률이 아닙니다.

[막혔을 때]
- 입력 창이 실수로 닫혔다('나중에 확인'·Esc): 결과 화면의 '입력 수정하기'를 누르면 같은 창이 다시 열립니다. 스스로 다시 열리지는 않습니다.
- 창이 안 열리거나 AI 오류가 나면: 직접 입력으로 이어 갈 수 있습니다(AI 없이도 선택지 답은 저장됩니다). 오류 안내에 '다시 시도'가 있으면 한 번만 누르고, 안 되면 캡처로 넘어갑니다.
- 칸을 비워 둔 채 저장해도 됩니다. 결과 화면의 '입력 수정하기'를 누르면 같은 페이지가 다시 열립니다.
- 숫자 칸의 선택지(연 220일 등)는 렌더링한 화면과 자동 시험으로 확인했고 브라우저의 제안 목록을 직접 눌러 보지는 않았습니다(커밋 f66f103 기록). 리허설에서 한 번 눌러 보고, 안 되면 숫자를 직접 입력하세요.

[코드 위치] 이 '한 페이지 입력'은 커밋 f66f103으로 푸시되어 있습니다.`, '시연 6 ①~④');
  const h = 4.3, w = fitW(IMG.dlg1, h), y = 1.7;
  s.addImage({ path: IMG.dlg1.path, x: MX, y, w, h, altText: '작업 정보를 한 번에 확인해 주세요 창. 남은 확인 10개, 작업 특징 8개가 모두 모름 미확인으로 보인다.', objectName: '화면 캡처: 입력 창 처음 모습' });
  s.addImage({ path: IMG.dlg5.path, x: MX + w + 0.3, y, w, h, altText: '같은 창에서 작업 특징 8개가 모두 아니오로 답해지고 선택하지 않은 나머지 작업은 모두 안 해요 버튼이 보인다.', objectName: '화면 캡처: 작업 특징에 답한 모습' });
  txt(s, '처음: 작업 특징 8개 ‘모름 / 미확인’', { x: MX, y: y + h + 0.1, w, h: 0.6, fontSize: 14, bold: true, color: INDIGO, lineSpacingMultiple: 1.0 });
  txt(s, '② 누른 뒤: 8개 모두 ‘아니오’', { x: MX + w + 0.3, y: y + h + 0.1, w, h: 0.6, fontSize: 14, bold: true, color: INDIGO, lineSpacingMultiple: 1.0 });
  const x0 = MX + 2 * w + 0.3 + 0.45, tw = W - MX - x0;
  const items = [
    ['①', '다시 묻지 않는 정보', '맨 아래 ‘이미 확인한 정보 N개’를 열면 AI가 문장에서 채운 값이 보입니다.'],
    ['②', '나머지 작업은 한 번에', '‘선택하지 않은 나머지 작업은 모두 안 해요’ 한 번 → 8개 모두 ‘아니오’'],
    ['③', '사진 확인 → 체크리스트', '‘예, 모두 맞아요’를 고르면 같은 창에 체크리스트가 나타납니다.'],
    ['④', '손에 든 물건', '‘이 순간 손에 든 물건이나 미는 힘이 있나요?’ → ‘없음’'],
  ];
  items.forEach(([n, a, b], i) => {
    const by = 1.7 + i * 1.2;
    box(s, x0, by, tw, 1.1, { fill: SURFACE, name: `설명 ${n}` });
    badge(s, n, x0 + 0.2, by + 0.3, 0.5);
    txt(s, a, { x: x0 + 0.9, y: by + 0.08, w: tw - 1.1, h: 0.38, fontSize: 18, bold: true, color: INDIGO, valign: 'middle' });
    txt(s, b, { x: x0 + 0.9, y: by + 0.46, w: tw - 1.1, h: 0.6, fontSize: 13.5, color: SUB, lineSpacingMultiple: 1.04 });
  });
}

// 11. 시연 6 ⑤~⑦ 체크리스트 ───────────────────────────────
{
  const s = contentSlide('시연', '체크리스트로 확정하고 저장하기', `[큐카드 6 ⑤~⑦ · 한 페이지 입력의 뒷부분, 약 1분]
[눌러야 할 순서와 대본]
 ⑤ '자세 체크리스트': '앉아서 작업함'만 체크하고 '확인 끝 · 체크 안 한 항목은 해당 없음'을 누릅니다. 창 아래에 "18개 항목을 채웠어요. 저장하면 반영돼요. 다르면 직접 고쳐 주세요."가 나옵니다. → "해당하는 것만 체크하고 나머지는 한 번에 '해당 없음'입니다. 눌러야만 저장됩니다."
 ⑥ '사진이 읽지 못해 직접 골라야 하는 항목': 아래 표대로 고른 뒤 '왼쪽 팔·손목은 오른쪽과 같아요'를 누릅니다. → "사진이 못 읽는 것만 묻습니다. 한쪽을 고르면 반대쪽은 복사합니다."
 ⑦ '저장하고 결과 보기 →'. → "여기서 입력은 끝입니다. 이후 다시 묻지 않습니다."

[⑥에서 고를 값 — 발표자가 사진을 보고 고른 값이라고 말합니다]
 목 → 똑바로·조금 숙임(20° 이내) / 몸통을 얼마나 굽히나요 → 똑바로 / 오른쪽 양팔 위팔을 얼마나 드나요 → 몸 옆(20° 이내) / 오른쪽 양팔 팔꿈치 각도 → 60~100° / 오른쪽 손목을 앞뒤로 얼마나 굽히거나 젖히나요 → 15° 이내 / 오른쪽 손잡이나 잡는 상태 → 좋음 / 왼쪽 팔꿈치는 사진이 이미 재서(88°) 묻지 않습니다.
 '앉아서 작업함'을 체크하면 무릎 질문은 나오지 않습니다(리허설에서 나오지 않았습니다). 화면에 나오는 질문만 고르면 됩니다.

[조작 횟수]
- 리허설 2번 모두 18회: 새 분석·문장·사진 선택·자르기·분석 5회, '나머지 작업은 모두 안 해요' 1회, 물건 '없음'·사진 상황 2회, 체크 1회, '확인 끝' 1회, 각도 선택 6회, 복사 1회, 저장 1회. 시연에서는 문장을 붙여 넣으므로 키보드로 치는 시간은 없습니다.
- TEST_FACTS.md의 시험 기록은 17회(체크 칸을 누른 횟수가 따로 없는 내역)이고, 이전 방식(결과를 본 뒤 다시 여는 두 번째 입력 창)은 ${FACTS.interactionsBefore}회였습니다. 처음의 칸별 입력 방식과 비교한 측정은 없어 "몇 배 줄었다"고 말하지 않습니다.
- 저장된 사용자 답의 근거(리허설): '직접 입력' 12, '자세 체크리스트에서 해당한다고 직접 체크' 2, '…해당 없음으로 직접 확인' 34, '왼쪽은 오른쪽과 같다고 직접 선택' 4.

[말할 내용]
- 이 단계가 '묻는 것을 줄이는' 핵심입니다. 예/아니오 항목 18개를 한 장에서 해당하는 것만 체크하게 했고, 나머지는 '확인 끝' 한 번으로 '해당 없음'이 됩니다.
- 단, '확인 끝'을 누르지 않고 저장하면 미확인으로 남습니다. 저장하기 전에는 아무것도 기록되지 않습니다. 이미 고른 칸은 덮어쓰지 않습니다.
- 사진이 이미 잰 값은 다시 묻지 않고, 사진이 읽지 못한 각도·상태만 직접 고르게 합니다. 이 부분이 아직 사용자 몫입니다(조작 중 각도 고르기 6회 → 향후 계획 14번).

[주의]
- 시연 결과의 점수는 사진이 못 읽는 각도를 사람이 고른 값이라 '흐름 확인용'입니다. 리허설의 각도 값은 표대로 사진을 보고 고른 값이지 측정이 아닙니다.
- 각도 선택칸의 설명 문장은 화면에 따라 "결과 계산에 필요한 정보가 아직 없어요"가 되풀이되어 보일 수 있습니다.

[막혔을 때]
- 체크리스트가 안 보이면: 사진 상황(한 사람·전신·평소 작업) 선택('예, 모두 맞아요')을 먼저 해야 자세 항목이 나타납니다. 선택한 뒤 창을 아래로 스크롤합니다.
- 사진 상황에 '아니오·모름'으로 답해도 질문으로 REBA 입력을 채울 수 있는 길이 있습니다(막다른 길 없음).
- 입력 창이 실수로 닫혔다: 결과 화면의 '입력 수정하기'를 누르면 같은 창이 다시 열립니다.`, '시연 6 ⑤~⑦');
  const h = 3.85, w = fitW(IMG.dlg2, h), imgs = [IMG.dlg2, IMG.dlg3, IMG.dlg4];
  const g = (CW - 3 * w) / 2;
  const caps = [
    ['⑤', '‘앉아서 작업함’만 체크', '해당하는 자세만 체크합니다'],
    ['⑤', '‘확인 끝’ → 나머지는 해당 없음', '눌러야만 저장됩니다(18개 항목을 채워요)'],
    ['⑥', '못 읽은 각도만 선택', [{ text: '한쪽만 정하면 반대쪽은 복사', options: { breakLine: true } }, { text: '⑦ ‘저장하고 결과 보기 →’', options: { bold: true, color: INDIGO } }]],
  ];
  const alts = ['해당하는 자세에 체크해 주세요 체크리스트 구역', '확인 끝을 누른 뒤 18개 항목을 채웠다는 안내가 보이는 창', '사진이 읽지 못해 직접 골라야 하는 항목의 선택칸'];
  imgs.forEach((im, i) => {
    const x = MX + i * (w + g);
    s.addImage({ path: im.path, x, y: 1.7, w, h, altText: alts[i], objectName: `화면 캡처: ${caps[i][1]}` });
    badge(s, caps[i][0], x, 5.7, 0.44, { bg: INDIGO });
    txt(s, caps[i][1], { x: x + 0.55, y: 5.66, w: w - 0.55, h: 0.66, fontSize: 16, bold: true, color: INDIGO, valign: 'middle', lineSpacingMultiple: 1.0 });
    txt(s, caps[i][2], { x, y: 6.38, w, h: 0.62, fontSize: 13, color: SUB, lineSpacingMultiple: 1.05 });
    if (i < 2) arrow(s, x + w + 0.25, 1.7 + h / 2, x + w + g - 0.25, { width: 3.5 });
  });
}

// 12. 시연 7 최종 점수와 11개 기준 초안 ──────────────────────
{
  const s = contentSlide('시연', '최종 점수와 11개 기준 초안', `[큐카드 7 · 약 40초]
[눌러야 할 순서]
 7) 결과 화면을 보여 줍니다: 최종 REBA 점수와 '법정 기준 11개 중 N개가 해당 초안' 표. 입력은 앞 슬라이드의 '저장하고 결과 보기 →'로 끝났고, 이 화면에서 다시 묻지 않습니다.

[리허설 결과]
- 리허설 2번 모두 최종 REBA 1점 · 무시 가능, 왼쪽 1점·오른쪽 1점 중 높은 쪽, '법정 기준 11개 중 1개가 해당 초안'(키보드·마우스 집중 입력, 법정 1호)이었습니다. 입력에 따라 달라질 수 있습니다.

[대본]
"점수는 규칙 계산이고 AI가 바꾸지 않습니다. '해당 초안'은 입력한 값으로 계산한 결과이고, 최종 해당 여부는 조사자가 검토해 정합니다."
- 점수가 낮게 나온 것은 사진 속 자세가 양호했기 때문입니다. "안전하다"고 말하지 않습니다.
- 화면의 이 문장을 그대로 읽어도 됩니다: "초안은 입력한 값으로 계산한 결과예요. 최종 해당 여부는 조사자가 검토해 정해요."

[화면 설명]
- 왼쪽은 키보드 작업의 최종 결과입니다. 최종 REBA 점수 1점(무시 가능), 점수별 위험 수준 색상바에서 현재 위치가 표시됩니다. "왼쪽 1점 · 오른쪽 1점 중 높은 쪽 · 1차 점수 1점에서 답변을 반영했어요"라고 점수의 근거가 적힙니다. 법정 기준 11개 중 1개가 '해당 초안'입니다.
- 오른쪽은 상자 들기 예시(같은 방법, 다른 결과)의 '관련 법정 기준 초안'입니다. '10kg 이상 불편한 위치 들기(법정 9호)'는 입력이 더 필요해서 '입력 필요', '반복 들기(법정 10호)'는 '해당 초안'이고, 나머지 9개는 '해당 없음'으로 접혀 있습니다. 이 캡처는 입력 창이 두 번 열리던 때의 시험입니다.
- 저장한 뒤에는 화면이 스스로 다시 묻지 않습니다. 비워 둔 칸이 있으면 결과 화면의 '입력 수정하기'를 눌러야만 같은 페이지가 다시 열립니다.
- REBA 점수와 법정 11개 기준은 서로 다른 방법이라 한 점수로 합치지 않습니다. 높은 REBA를 곧바로 법정 해당으로 바꾸지도 않습니다.
- 4분 압축판: 결과는 점수와 '해당 초안' 한 줄만 말합니다.

[꼭 말해야 하는 한계]
- 이 점수는 사진이 못 읽는 각도(목·몸통·손목 등)를 사람이 고른 값입니다. 리허설의 각도 값은 사진을 보고 고른 값이지 측정이 아니고, 흐름을 확인한 것입니다. 공개 사진 시험이며 현장 사진 시험이 아닙니다.

[막혔을 때]
- 점수가 리허설과 다르다(예: 2점): 정상입니다. 입력한 값에 따라 달라집니다. "그래서 조사자가 검토합니다"로 잇고, 점수 자체가 아니라 '근거 문장과 초안 상태가 같이 나온다'는 점에 집중합니다.
- 다음은 결과 화면 아래 'Excel 미리보기'(다음 슬라이드). 'AI 설명'을 만들려면 '검토하고 설명 만들기'.`, '시연 7');
  const h = 4.2, w1 = fitW(IMG.op07score, h), y = 1.7;
  s.addImage({ path: IMG.op07score.path, x: MX, y, w: w1, h, altText: '최종 REBA 점수 1점 무시 가능, 색상바, 왼쪽 오른쪽 점수 근거, 관련 법정 기준 초안(키보드·마우스 집중 입력 해당 초안)', objectName: '화면 캡처: 최종 점수(키보드)' });
  const x2 = MX + w1 + 0.4, w2 = 6.3, h2 = fitH(IMG.d06table, w2);
  s.addImage({ path: IMG.d06table.path, x: x2, y, w: w2, h: h2, altText: '상자 들기 예시의 관련 법정 기준 초안. 10kg 이상 불편한 위치 들기는 입력 필요, 반복 들기는 해당 초안', objectName: '화면 캡처: 기준 초안 표(상자)' });
  txt(s, '상자 들기 예: 3점 · 낮음 / 입력 필요 1개 · 해당 초안 1개', { x: x2, y: y + h2 + 0.08, w: w2, h: 0.32, fontSize: 13, color: MUTED });
  const call = [['점수와 위험 단계', '1~15점 색상바와 근거 문장'], ['11개 기준마다 상태', '해당 초안 · 입력 필요 · 해당 없음'], ['규칙 계산, AI는 안 바꿈', '최종 해당 여부는 조사자가 정함']];
  const cy0 = y + h2 + 0.5;
  call.forEach(([a, b], i) => {
    const cy = cy0 + i * 0.56;
    badge(s, i + 1, x2, cy + 0.04, 0.44);
    txt(s, [{ text: a + '   ', options: { bold: true, color: INDIGO, fontSize: 17 } }, { text: b, options: { fontSize: 15, color: SUB } }], { x: x2 + 0.6, y: cy, w: W - MX - x2 - 0.6, h: 0.52, valign: 'middle', lineSpacingMultiple: 1.0 });
  });
  amberNote(s, '※ 시연 점수는 사진이 못 읽는 각도를 사람이 고른 값이라 흐름 확인용입니다. 측정 결과가 아니며, 공개 사진 시험입니다.', MX, 6.32, CW, 0.62, { size: 14 });
}

// 13. 시연 8 Excel 미리보기와 저장 ───────────────────────────────────
{
  const s = contentSlide('시연', 'Excel 미리보기와 저장', `[큐카드 8 · 약 40초]
[눌러야 할 순서]
 8) 결과 화면 아래의 'Excel 미리보기' → 시트 탭('조사 결과' / '부담작업 해당 여부' / '자세 분석(REBA)' / '입력한 값'. 조건에 따라 'AI 사진 관찰', 사람 검토, 쉬운 설명, 개선 전후 비교가 붙습니다) → 탭 '입력한 값'으로 가서 각 값에 '직접 입력: …', '자세 체크리스트에서 …' 같은 근거가 붙은 것을 보여 줍니다. → (선택) 'Excel로 저장'을 누르면 파일로 저장됩니다(저장 위치 창이 뜹니다). 이 PC에 Excel이 없으면 미리보기까지만 합니다.

[대본]
"어떤 값이 사람이 고른 것이고 어떤 값이 AI·사진에서 온 것인지 근거가 함께 남습니다."

[화면 설명 — 실제 앱·실제 AI 리허설 캡처]
- 왼쪽 캡처: 'Excel 미리보기'의 첫 탭 '조사 결과'. 조사 개요·작업 정보·유해요인 기록·REBA 자세 평가(1점·무시 가능, "조치가 필요 없어요")·분석 결과가 보이고, 맨 아래에 앱의 안내 문구가 있습니다: "이 보고서는 작업 분석을 돕는 참고 자료예요. 법정 유해요인조사표·증상조사표를 대신하지 않아요." / "'해당 초안'은 입력한 값으로 계산한 결과예요. 최종 해당 여부는 조사자가 검토해 정해요. 조사자 결론은 법적 승인을 뜻하지 않아요." 대표 사진 이미지는 저장되는 파일에만 들어가서 미리보기에서는 빈 칸으로 보입니다.
- 오른쪽 캡처: 탭 '입력한 값'(같은 표의 위쪽 행과 아래쪽 행, 중간 행은 생략했습니다). 위쪽 행은 'AI: …'(문장에서 AI가 옮겨 적은 값), 아래쪽 행은 '사진 자동 측정: 88.0°', '직접 입력: …', '자세 체크리스트에서 해당한다고 직접 체크', '왼쪽은 오른쪽과 같다고 직접 선택'처럼 값마다 입력 방법과 근거가 붙습니다. 미리보기와 저장되는 파일은 같은 시트 정의에서 만들어서 서로 같습니다.
- 기록한 값과 계산 가능한 결과가 있는 시트만 만들어지고, 빈 법정 서식은 만들지 않습니다.
- 이 캡처는 미리보기 카드 영역까지만 썼습니다. 그 아래 'Excel 만들기 전 확인' 상자는 실제 화면에서 '빠진 항목이 없어요. 그대로 Excel로 저장해도 돼요.'라고 나오고 '입력하러 가기' 버튼은 없습니다(계산에 실제로 빠진 값이 있을 때만 그 줄과 버튼이 나옵니다). 점수 계산에 쓰이지 않는 근로자 참여·증상조사·작업장 상황·수시조사 사유는 묻지도 보여주지도 받지도 않습니다(2026-10-27 범위 정리, 커밋 457b5f5).

[마무리 대사 · 20초]
"정리하면, 첫 점수는 몇 초, 입력은 한 페이지, 판단은 조사자입니다. 한 페이지에서 비운 칸이 있으면 결과 화면의 '입력 수정하기'를 눌러야만 같은 창이 다시 열립니다. 스스로 다시 묻지 않습니다."
- 4분 압축판: 이 슬라이드에서는 '입력한 값' 탭을 10초만 보여 줍니다.

[막혔을 때]
- Excel이 없다·저장 창이 안 뜬다: 미리보기 탭까지만 보여 주고, "저장 파일은 미리보기와 같은 시트 정의"라고 설명한 뒤 넘어갑니다. 미리 저장해 둔 .xlsx가 있으면 그 파일을 엽니다. Excel 저장은 앱 안에서만 됩니다. 브라우저 미리보기에서는 저장되지 않습니다.

[시연 뒤 정리]
- 앱을 닫습니다(창으로 돌아옵니다). 시연 기록을 지우려면 Remove-Item ..\\..\\..\\.local\\demo.db 입니다. 다음 시연 전에는 .\\prepare-demo.ps1 이 새 DB를 만듭니다. AI 키는 어디에도 저장되지 않았고, 창을 닫으면 환경 변수도 사라집니다.
- 예상 질문과 답은 시연-시나리오.md §5와 16번 노트에 있습니다.`, '시연 8');
  const hA = 4.2, wA = fitW(IMG.exA, hA), yTop = 1.7;
  s.addImage({ path: IMG.exA.path, x: MX, y: yTop, w: wA, h: hA, altText: 'Excel 미리보기의 첫 탭 조사 결과. 조사 개요, 작업 정보, REBA 자세 평가 1점 무시 가능, 분석 결과와 참고 자료 안내 문구가 보인다.', objectName: '화면 캡처: Excel 미리보기(조사 결과 탭)' });
  const x0 = MX + wA + 0.35, wB = W - MX - x0;
  const h1 = fitH(IMG.exB1, wB), h2 = fitH(IMG.exB2, wB);
  s.addImage({ path: IMG.exB1.path, x: x0, y: yTop, w: wB, h: h1, altText: 'Excel 미리보기의 입력한 값 탭 위쪽. 작업 조건과 법정 기준 입력값마다 AI 정리 근거가 붙어 있다.', objectName: '화면 캡처: 입력한 값 탭(위쪽 행)' });
  txt(s, '···  중간 행 생략 (같은 표)  ···', { x: x0, y: yTop + h1 + 0.03, w: wB, h: 0.27, fontSize: 11, color: MUTED, align: 'center' });
  const y2 = yTop + h1 + 0.31;
  s.addImage({ path: IMG.exB2.path, x: x0, y: y2, w: wB, h: h2, altText: 'Excel 미리보기의 입력한 값 탭 아래쪽. 사진 자동 측정 88.0도, 직접 입력, 자세 체크리스트에서 해당한다고 직접 체크 같은 근거가 붙어 있다.', objectName: '화면 캡처: 입력한 값 탭(아래쪽 행)' });
  txt(s, '‘Excel 미리보기’ 첫 탭 ‘조사 결과’', { x: MX, y: yTop + hA + 0.06, w: wA, h: 0.42, fontSize: 12.5, bold: true, color: INDIGO, lineSpacingMultiple: 1.0 });
  txt(s, [{ text: '탭 ‘입력한 값’ — 값마다 근거가 붙습니다: AI 정리 · 직접 입력 · 사진 자동 측정', options: { bold: true, color: INDIGO, breakLine: true } },
    { text: '(선택) ‘Excel로 저장’ → 같은 내용이 파일로 저장됩니다', options: { color: SUB } }], { x: x0, y: y2 + h2 + 0.05, w: wB, h: 0.52, fontSize: 12.5, lineSpacingMultiple: 1.0 });
  amberNote(s, '앱의 안내 문구: “이 보고서는 작업 분석을 돕는 참고 자료예요. 법정 유해요인조사표·증상조사표를 대신하지 않아요.”', MX, 6.5, CW, 0.5, { size: 14 });
}

// 14. 향후 계획 ① 알려진 한계 ─────────────────────────────
{
  pres.addSection({ title: '향후 계획' });
  const s = contentSlide('향후 계획', '알려진 한계: 숨기지 않습니다', `[말할 내용 · 약 1분 30초]
- 향후 계획을 말씀드리기 전에, 지금 알려진 한계부터 정직하게 말씀드립니다(docs/presentation/TEST_FACTS.md '알려진 한계').
- ① 사진이 못 읽는 각도: 목·몸통·손목 등은 사용자가 골라야 합니다. 앞서 본 시연 점수는 시험 스크립트가 그 각도를 임의로 고른 값이라 '흐름을 확인한 것'이지 측정이 아닙니다. 시험에서 조작 ${FACTS.interactions}회 중 6회가 이 각도 고르기였습니다(한쪽 팔을 반대쪽으로 복사한 1회는 따로).
- ② AI 대기: 같은 키보드 사진·같은 문장 기준으로 AI 정리 시간은 추론 강도 xhigh일 때 ${FACTS.waitXhigh.join('초·')}초(3회 실측), 소유자 지시로 high로 낮춘 뒤 ${FACTS.waitHigh.slice(0, 3).join('초·')}초이고 한 번은 ${FACTS.waitHigh[3]}초가 걸렸습니다(TEST_FACTS.md, 4회 실측). ${FACTS.waitHigh[3]}초는 첫 AI 요청이 235초 만에 '불완전 응답'으로 끝났고 이어진 후속 점검 호출이 같은 값을 채워 결과는 정상이었던 경우입니다. 매번 값이 달라 한 숫자로 말하지 않으며 네트워크·모델 상태에 따라 크게 달라집니다. 이 실측은 120초 재전송을 넣기 전의 기록입니다. ${resendNote} 최악의 경우 시간 초과 오류가 나기까지 120초씩 세 번을 기다립니다. 개선된 점: 분석을 누르면 사진 측정만으로 나온 1차 점수를 AI보다 먼저 보여 줍니다(${firstScoreText}, 세 번 실측). 남은 점: 입력 창은 AI 정리가 끝나야 열려서 그 대기(보통 1분 안팎, 길면 4분 넘게)는 그대로입니다. 사진이 없거나 사진 측정만으로 점수를 못 내면 상태 줄만 보입니다.
- ③ AI가 한 문장에서 '반복 작업' 같은 작업 특징을 넓게 읽어(예: '1분에 2번'을 반복 작업으로 읽음) 입력칸이 늘어날 때가 있습니다(원래 있던 동작).
- ④ 상자 사진 결과 화면의 'AI가 사진에서 확인한 모습' 영역에 같은 안내 문장이 두 번 이어서 보입니다(이번 수정 범위 밖이라 손대지 않았고 원인은 확인하지 않았습니다).
- 그리고 이 모든 시험은 공개 사진으로 했습니다. 최종 해당 여부와 점수는 조사자가 검토해 정하며, 의학적 효과나 법적 적합성은 입증하지 않았습니다.`);
  const items = [
    ['FiTarget', '사진이 못 읽는 각도', '목·몸통·손목 등은 직접 골라야 합니다. 시연 점수는 임의로 고른 값입니다.'],
    ['FiClock', 'AI 정리 시간이 일정하지 않음', '4분 넘게 걸린 적도 있어 120초 무응답이면 같은 요청을 다시 보내게 했습니다(실제 AI로 120초 초과는 미시험).'],
    ['FiList', '입력칸이 늘어날 때가 있음', '‘반복 작업’ 같은 특징을 AI가 넓게 읽는 경우입니다(예: ‘1분에 2번’).'],
    ['FiCopy', '화면 문구가 겹쳐 보임', '상자 사진 결과 화면에 같은 안내 문장이 두 번 나옵니다. 원인은 미확인입니다.'],
  ];
  const lw = 6.6, rh = 1.06, rg = 0.08;
  for (let i = 0; i < 4; i++) {
    const y = 1.75 + i * (rh + rg);
    box(s, MX, y, lw, rh, { fill: SURFACE, name: `한계 ${i + 1}` });
    await iconDot(s, items[i][0], MX + 0.22, y + 0.25, 0.56, { alt: items[i][1], bg: AMBER, fg: INK });
    txt(s, items[i][1], { x: MX + 0.98, y: y + 0.07, w: lw - 1.2, h: 0.42, fontSize: 17, bold: true, color: INDIGO });
    txt(s, items[i][2], { x: MX + 0.98, y: y + 0.5, w: lw - 1.2, h: 0.56, fontSize: 13, color: SUB, lineSpacingMultiple: 1.0 });
  }
  // AI 대기시간 막대 그래프 (실측값)
  const cx = MX + lw + 0.4, cw = W - MX - cx, chH = 4 * rh + 3 * rg;
  box(s, cx, 1.75, cw, chH, { fill: WHITE, radius: 0.14, line: LINE, name: '그래프 틀' });
  s.addChart(pres.charts.BAR, [{ name: 'AI 대기시간(초)', labels: [...FACTS.waitXhigh.map(() => 'xhigh'), ...FACTS.waitHigh.map(() => 'high')], values: [...FACTS.waitXhigh, ...FACTS.waitHigh] }], {
    x: cx + 0.15, y: 1.85, w: cw - 0.3, h: 3.4, barDir: 'col', barGapWidthPct: 45, chartColors: [AMBER, AMBER, AMBER, VIOLET, VIOLET, VIOLET, VIOLET],
    showValue: true, dataLabelPosition: 'outEnd', dataLabelFormatCode: '0"초"', dataLabelFontSize: 14, dataLabelFontBold: true, dataLabelColor: INK, dataLabelFontFace: FONT,
    catAxisLabelFontSize: 13, catAxisLabelColor: SUB, catAxisLabelFontFace: FONT, valAxisHidden: true, valAxisMinVal: 0, valAxisMaxVal: 300,
    valGridLine: { style: 'none' }, catGridLine: { style: 'none' }, showLegend: false,
    showTitle: true, title: 'AI 대기시간 (초) · 추론 강도별', titleFontSize: 15, titleColor: INDIGO, titleFontFace: FONT, titleFontBold: true,
  });
  txt(s, '같은 키보드 사진·문장, 120초 재전송 도입 전 실측(xhigh 3회, high 4회). 256초는 첫 요청이 ‘불완전 응답’으로 끝나 후속 점검이 이어진 경우(결과 정상). 값은 매번 달라집니다.', { x: cx + 0.3, y: 5.28, w: cw - 0.6, h: 0.9, fontSize: 12, color: MUTED, lineSpacingMultiple: 1.05 });
  amberNote(s, '공개 사진 시험 · 최종 해당 여부와 점수는 조사자가 검토해 정합니다 · 의학적 효과·법적 적합성은 입증하지 않았습니다', MX, 6.36, CW, 0.56, { size: 14 });
}

// 15. 향후 계획 ② 다음에 할 일 ─────────────────────────────
{
  const s = contentSlide('향후 계획', '다음에 할 일: 빠르게·일관되게·덜 묻게', `[말할 내용 · 약 1분 30초]
출처: docs/remaining-improvements-20261023.md(남은 개선 3가지)와 TEST_FACTS.md, 요구사항 문서 8장.
- 더 빠르게: AI 대기의 원인은 사진 분석 → 첫 문장 정리 → 누락 교차확인이 순서대로 이어지는 구조입니다. 이번에 반영한 것은 두 가지입니다. 하나는 1차 점수를 AI보다 먼저 보여 주는 것입니다(커밋 fcfa0a5, 분석을 누른 뒤 ${firstScoreText}). 다른 하나는 요청이 오래 걸릴 때 같은 요청을 다시 보내는 것입니다(커밋 4fb3dc3). ${resendNote} 이 변경으로 대기시간이 얼마나 줄어드는지는 측정하지 못했습니다. 다음 작업은 사진 분석과 첫 문장 정리를 동시에 시작하고, AI 요청의 응답 구조를 압축하는 것입니다. 설계 단계에서 압축 사본 기준으로 89개 분기를 12개로 묶어 32,848자를 9,242자로 줄일 수 있음을 확인했지만, 실제 구현·동치 검증·품질 검증은 아직 없습니다. 병렬 실행 시제품은 별도 브랜치에 있으며 이번 병합에는 넣지 않았습니다. 누락 교차확인은 없애지 않습니다. 완료 기준은 같은 시나리오의 실제 전체 대기시간 감소입니다(단일 호출 성능을 보장하지 않음).
- 점수가 서로 맞게: 화면의 1차(가정) 점수와 확정된 최종 점수·AI 설명이 서로 다른 기준을 말하지 않도록 같은 계약으로 저장·화면·AI·Excel에 연결합니다. '지금까지 확인한 값 기준 (확정 전)'과 가정한 항목 수를 화면·Excel·AI 요약에 같이 쓰도록 고친 것은 커밋 fcfa0a5에 들어 있지만, 합성 좌표·임시 DB로 확인한 범위이고 실제 AI 문장까지 점검하는 일은 남았습니다.
- 덜 묻게: 이미 반영한 것은 입력 화면을 한 페이지로 합치는 것입니다(커밋 f66f103). 작업 특징·작업 조건·사진 확인·자세 체크리스트·못 읽은 각도를 한 대화상자에 두고, 저장한 뒤에는 스스로 다시 묻지 않습니다(실제 앱 실행에서 입력 창 열림 횟수 1을 확인. docs/adaptive-intake.md '한 페이지에서 끝내고 다시 묻지 않는다'). 남은 일은 사진이 못 읽는 각도를 고르는 조작을 줄이는 것입니다(시험 조작 ${FACTS.interactions}회 중 6회). 그 밖에 Excel 생성에 꼭 필요한 정보, 최종 REBA에 필요한 정보, 선택 보완 항목을 실제 경로에서 전수 대조합니다. 이미 알려진 값은 다시 묻지 않고, 현재 정보로 출력할 수 있으면 선택 보완 때문에 막지 않습니다. 미확정 항목은 빈값·확인 필요로 보존하고 NO나 0을 임의로 채우지 않습니다.
- 현장에서 확인할 것(요구사항 문서·README): 현장 사진으로 시험, 실제 조사자 3~5명과 같은 작업 사례로 수기 vs LOCO 시간 비교(목표 30% 단축, 아직 미측정), 깨끗한 별도 Windows PC에서 설치·실행, 실제 외부 AI 계정·기존 1.3 DB 표본 검증. 이것들은 로컬 합성 검증으로 대체하지 않습니다.
- 장기: 근거 수집과 보고서 연결의 품질이 먼저고, 그다음 관찰 보조와 분석 범위 확장입니다. 새 모델 학습이나 사업화는 반복 사용과 비용을 확인한 뒤 결정합니다(요구사항 문서 8장).`);
  const cols = [
    ['FiZap', '더 빠르게', ['사진 분석과 문장 정리를 동시에 시작', 'AI 요청 구조 압축 (설계상 89개 분기 → 12개)', '반영: 1차 점수 먼저 보이기, 120초 재전송(실제 AI 미시험)']],
    ['FiLink', '점수가 서로 맞게', ['1차(가정) 점수와 확정 점수·AI 설명을 같은 근거로 연결', '‘확정 전’ 표시와 가정 항목 수: 반영 (커밋 fcfa0a5)', '실제 AI 문장까지 점검하는 일이 남음']],
    ['FiMinusCircle', '덜 묻게', ['입력을 한 페이지로 합치기: 반영 (커밋 f66f103)', `사진이 못 읽는 각도 고르기를 줄이기 (조작 ${FACTS.interactions}회 중 6회)`, 'Excel에 꼭 필요한 정보와 선택 보완을 분리']],
  ];
  const cw = 3.92, gap = (CW - 3 * cw) / 2, top = 1.75, ch = 3.6;
  for (let i = 0; i < 3; i++) {
    const x = MX + i * (cw + gap);
    box(s, x, top, cw, ch, { shadow: true, name: `계획 ${cols[i][1]}` });
    await iconDot(s, cols[i][0], x + 0.28, top + 0.25, 0.62, { alt: cols[i][1] });
    txt(s, cols[i][1], { x: x + 1.1, y: top + 0.25, w: cw - 1.3, h: 0.62, fontSize: 22, bold: true, color: INDIGO, valign: 'middle' });
    s.addText(cols[i][2].map((t, k) => ({ text: t, options: { bullet: { indent: 16 }, breakLine: k < cols[i][2].length - 1, paraSpaceAfter: 7 } })),
      { isTextBox: true, x: x + 0.28, y: top + 1.1, w: cw - 0.55, h: ch - 1.25, fontFace: FONT, lang: 'ko-KR', fontSize: 16, color: SUB, valign: 'top', margin: 0, lineSpacingMultiple: 1.06 });
  }
  box(s, MX, 5.58, CW, 1.35, { fill: INDIGO, radius: 0.16, name: '현장 확인 배너' });
  txt(s, '현장에서 확인할 것', { x: MX + 0.4, y: 5.66, w: 4, h: 0.38, fontSize: 16, bold: true, color: 'C9CCFF' });
  txt(s, '현장 사진으로 시험  ·  조사자 3~5명과 시간 비교 (목표 30% 단축, 미측정)  ·  별도 Windows PC 설치 확인', { x: MX + 0.4, y: 6.08, w: CW - 0.8, h: 0.78, fontSize: 18, bold: true, color: WHITE, valign: 'middle', lineSpacingMultiple: 1.05 });
}

// 16. 마무리 · Q&A ───────────────────────────────────
{
  pres.addSection({ title: '마무리 · Q&A' });
  const s = pres.addSlide({ masterName: 'CLOSING', sectionTitle: '마무리 · Q&A' });
  if (process.env.QA_FLAT) s.addImage({ path: bgClosing, x: 0, y: 0, w: W, h: H });
  s.addText('정리 · Q&A', { placeholder: 'title', lang: 'ko-KR' });
  const msgs = [
    ['1', '사진과 한 문장으로 시작해, 필요한 것만 묻고, Excel까지 이어집니다.'],
    ['2', '계산은 규칙 엔진이, 설명은 AI가 — 점수와 해당 여부는 조사자가 정합니다.'],
    ['3', '공개 사진으로 끝까지 확인했고, 현장 검증은 이제부터입니다.'],
  ];
  msgs.forEach(([n, t], i) => {
    const y = 1.95 + i * 1.4;
    badge(s, n, 0.9, y + 0.18, 0.7, { bg: VIOLET });
    txt(s, t, { x: 1.9, y, w: 10.4, h: 1.15, fontSize: 25, bold: true, color: WHITE, valign: 'middle', lineSpacingMultiple: 1.05 });
  });
  txt(s, '감사합니다', { x: 0.9, y: 6.2, w: 5, h: 0.65, fontSize: 28, bold: true, color: 'C9CCFF', valign: 'middle' });
  txt(s, '점수와 해당 여부는 조사자가 검토해 정합니다 · 공개 사진 시험 · 의학적 효과와 법적 적합성은 입증하지 않았습니다', { x: 0.9, y: 6.95, w: 11.5, h: 0.32, fontSize: 12, color: 'B9BDF5' });
  s.addNotes(`[마무리 · 약 30초]
- 세 문장으로 정리합니다: ① 사진과 한 문장으로 시작해 필요한 것만 묻고 Excel까지 ② 계산은 규칙 엔진, 설명은 AI, 점수와 해당 여부는 조사자 ③ 공개 사진으로 끝까지 확인했고 현장 검증은 이제부터.

[예상 질문과 답 — 모두 저장소 문서에 근거]
Q. 정확도는 어느 정도인가요?
A. 공개 사진으로 끝까지 돌려 본 시험만 했습니다. 현장 사진 정확도는 말씀드릴 수 없습니다. 사진이 못 읽는 각도는 사용자가 직접 고릅니다.
Q. AI가 점수나 해당 여부를 정하나요?
A. 아니요. 11개 기준과 REBA는 규칙 엔진이 계산합니다. AI는 문장 정리, 사진 속 동작 설명, 설명문 작성을 맡고 점수와 판정을 바꾸지 못합니다(AGENTS.md).
Q. 법적으로 이 Excel을 제출할 수 있나요?
A. 이 Excel은 작업 분석을 돕는 참고 자료입니다. 법정 유해요인조사표·증상조사표를 대신하지 않고, 최종 해당 여부는 조사자가 검토해 정합니다. 법령의 최신 개정과 현장 적용은 별도로 확인해야 합니다.
Q. 시간이 얼마나 줄었나요?
A. 측정하지 않았습니다. 목표(가설)는 입력부터 보고서까지 걸리는 시간 중앙값 30% 단축이고 아직 미검증입니다. 시험 기록의 조작 ${FACTS.interactions}회(한 페이지 입력)는 시간이 아니라 조작 횟수이고 1회 실측입니다. 수기 작업과 비교한 측정은 없습니다.
Q. 사진이 외부로 나가나요?
A. AI 사진 관찰을 쓰면 사진(EXIF를 제거한 JPEG)이 AI API로 전송됩니다. 키와 이미지 base64는 저장하지 않습니다. 현장 도입 전에 사내 보안 정책을 확인해야 합니다.
Q. 왜 AI가 1분이나 걸리나요?
A. 사진 분석 → 첫 문장 정리 → 누락 교차확인이 순서대로 이어지고, 추론 강도도 영향을 줍니다. xhigh일 때 113~170초였고(3회 실측) high로 낮춘 뒤 55초·73초·73초였으며 한 번은 256초가 걸렸습니다(4회 실측). 다만 1차 점수는 사진 측정만으로 AI보다 먼저(${firstScoreText}, 세 번 실측) 보여 줍니다. ${resendNote} 병렬화·요청 압축은 시제품·설계 단계입니다.
Q. REBA와 11개 기준을 왜 한 점수로 합치지 않나요?
A. 서로 다른 방법이기 때문입니다. 높은 REBA를 곧바로 법정 해당으로, 낮은 REBA를 해당 없음으로 바꾸지 않습니다(요구사항 문서 4장).
Q. 사진 없이도 쓸 수 있나요?
A. 네. 11개 기준은 직접 입력만으로 평가할 수 있고, 사진은 선택 기능입니다.
Q. 어떻게 설치하나요?
A. 저장소 README의 '설치·실행' 절차(Python 3.12 가상환경, requirements-desktop.txt, 자세 모델 내려받기, npm ci, run-integrated.ps1) 또는 scripts/build_windows.py로 만든 포터블 폴더의 LOCO.exe입니다. 별도 Windows PC 설치 확인은 아직 하지 않았습니다.`);
}

// ───────────────────────────── 저장 + 후처리 ─────────────────────────────
const tmp = path.join(WORK, 'raw.pptx');
await pres.writeFile({ fileName: tmp });

// 테마 색·글꼴(한글 East Asian 글꼴 포함)을 써 넣고, 모든 글자 설정에 한글 글꼴을 지정한다.
const zip = await JSZip.loadAsync(fs.readFileSync(tmp));
let theme = await zip.file('ppt/theme/theme1.xml').async('string');
const slots = ['dk1', 'lt1', 'dk2', 'lt2', 'accent1', 'accent2', 'accent3', 'accent4', 'accent5', 'accent6', 'hlink', 'folHlink'];
const scheme = `<a:clrScheme name="${THEME.name}">` + slots.map(k => `<a:${k}><a:srgbClr val="${THEME.colors[k]}"/></a:${k}>`).join('') + '</a:clrScheme>';
theme = theme.replace(/<a:clrScheme\b[\s\S]*?<\/a:clrScheme>/, () => scheme)
  .replace(/(<a:(?:theme|fontScheme)\b[^>]*?\bname=")[^"]*"/g, (_, head) => `${head}${THEME.name}"`);
theme = theme.replace(/(<a:(?:major|minor)Font>)([\s\S]*?)(<\/a:(?:major|minor)Font>)/g, (_, a, body, c) => {
  body = body.replace(/<a:latin\b[^>]*\/>/, `<a:latin typeface="${FONT}"/>`).replace(/<a:ea\b[^>]*\/>/, `<a:ea typeface="${FONT}"/>`);
  return a + body + c;
});
zip.file('ppt/theme/theme1.xml', theme);
// pptxgenjs 는 슬라이드 수만큼 없는 slideMaster 부품의 Override 를 [Content_Types].xml 에 적는다. 실제 부품이 없는 항목은 지운다.
let contentTypes = await zip.file('[Content_Types].xml').async('string');
contentTypes = contentTypes.replace(/<Override PartName="([^"]+)"[^>]*\/>/g, (m, part) => (zip.file(part.replace(/^\//, '')) ? m : ''));
zip.file('[Content_Types].xml', contentTypes);
for (const name of Object.keys(zip.files)) {
  if (!/^ppt\/(slides|slideLayouts|slideMasters)\/[^/]+\.xml$/.test(name)) continue;
  let xml = await zip.file(name).async('string');
  xml = xml.replace(/(<a:latin typeface="[^"]*"[^>]*\/>)(?!<a:ea )/g, `$1<a:ea typeface="${FONT}"/>`)
    .replace(/(<a:ea typeface="[^"]*"[^>]*?)charset="-122"/g, '$1charset="-127"');   // 한글 글꼴 힌트(129)
  zip.file(name, xml);
}
fs.writeFileSync(OUT, await zip.generateAsync({ type: 'nodebuffer', compression: 'DEFLATE' }));
console.log('saved', OUT, fs.statSync(OUT).size, 'bytes');
