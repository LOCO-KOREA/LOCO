// Display geometry only. Values come from the service; these checks never produce scores.
const DEG = 180 / Math.PI;
const finite = value => typeof value === 'number' && Number.isFinite(value);
const sub = (a, b) => ({x: a.x - b.x, y: a.y - b.y});
const length = v => Math.hypot(v.x, v.y);
const signed = (a, b) => Math.atan2(a.x * b.y - a.y * b.x, a.x * b.x + a.y * b.y) * DEG;
const normalized = n => ((n + 180) % 360 + 360) % 360 - 180;
const magnitude = (a, b) => Math.abs(signed(a, b));
const near = (a, b) => Math.abs(a - b) <= 0.11; // Service preview values are rounded to one decimal.
const escape = value => String(value).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const codeLabel = {TRUNK_TILT_VERT: '몸통', UPPER_ARM_FLEX_TRUNK: '위팔', ELBOW_FLEX: '아래팔', KNEE_FLEX: '무릎'};
const sideLabel = side => side === 'LEFT' ? '왼쪽' : '오른쪽';
const equalDimensions = (photo, width, height) => (!photo?.width_px || photo.width_px === width) && (!photo?.height_px || photo.height_px === height);

// Confidence changes presentation only; no points are inferred or promoted for scoring.
export function renderPhotoSkeleton(scene, bones, options = {}) {
  const {width, height} = scene;
  if (!finite(width) || !finite(height) || width <= 0 || height <= 0)
    return {markup: '', hasLowConfidence: false};
  const points = Object.fromEntries((scene.points || []).filter(p =>
    finite(p.x_px) && finite(p.y_px) && finite(p.confidence) && p.confidence > 0 && p.confidence <= 1 &&
    p.x_px >= 0 && p.x_px < width && p.y_px >= 0 && p.y_px < height).map(p => [p.name, p]));
  const threshold = finite(options.confidenceMin) && options.confidenceMin >= 0 && options.confidenceMin <= 1 ? options.confidenceMin : 0.3;
  const low = p => p.confidence < threshold;
  const lines = bones.filter(([a, b]) => points[a] && points[b]).map(([a, b]) => {
    const from = points[a], to = points[b];
    return `<line class="${low(from) || low(to) ? 'pose-low-line' : 'pose-line'}" x1="${from.x_px}" y1="${from.y_px}" x2="${to.x_px}" y2="${to.y_px}"/>`;
  }).join('');
  const dots = Object.values(points).map(p => `<circle class="${low(p) ? 'pose-low-point' : 'pose-point'}" cx="${p.x_px}" cy="${p.y_px}" r="${Math.max(width, height) / 120}">${low(p) ? '<title>낮은 신뢰도 · 위치 확인 필요</title>' : ''}</circle>`).join('');
  return {markup: lines + dots, hasLowConfidence: Object.values(points).some(low)};
}

function pointMap(points, width, height) {
  const result = {};
  for (const p of points || []) {
    if (finite(p.x_px) && finite(p.y_px) && finite(p.confidence) && p.confidence > 0 &&
        p.x_px >= 0 && p.x_px < width && p.y_px >= 0 && p.y_px < height)
      result[p.name] = {x: p.x_px, y: p.y_px};
  }
  return result;
}

// Both screen vectors and signed values follow joint_angles.py. In particular, elbow/knee
// use the extension of the proximal segment: their inner joint angle is NOT the flexion value.
export function sideAngleGeometry(points, row, forward, width, height) {
  if (!finite(row?.value_deg) || !['LEFT', 'RIGHT'].includes(row.side) || !codeLabel[row.angle_code]) return null;
  const map = pointMap(points, width, height), prefix = row.side.toLowerCase() + '_';
  const at = joint => map[prefix + joint];
  let pivot, reference, ray, calculated;
  const sign = forward === 'SCREEN_RIGHT' ? 1 : forward === 'SCREEN_LEFT' ? -1 : null;
  if (row.angle_code === 'TRUNK_TILT_VERT') {
    if (!at('hip') || !at('shoulder') || sign === null) return null;
    pivot = at('hip'); reference = {x: 0, y: -1}; ray = sub(at('shoulder'), pivot);
    calculated = Math.atan2(sign * ray.x, -ray.y) * DEG;
  } else if (row.angle_code === 'UPPER_ARM_FLEX_TRUNK') {
    if (!at('hip') || !at('shoulder') || !at('elbow') || sign === null) return null;
    pivot = at('shoulder'); reference = sub(at('hip'), pivot); ray = sub(at('elbow'), pivot);
    calculated = normalized(-sign * signed(reference, ray));
  } else {
    const elbow = row.angle_code === 'ELBOW_FLEX';
    const proximal = at(elbow ? 'shoulder' : 'hip');
    pivot = at(elbow ? 'elbow' : 'knee');
    const distal = at(elbow ? 'wrist' : 'ankle');
    if (!proximal || !pivot || !distal) return null;
    reference = sub(pivot, proximal); ray = sub(distal, pivot);
    calculated = magnitude(reference, ray);
  }
  if (length(reference) < 1e-6 || length(ray) < 1e-6 || !near(calculated, row.value_deg)) return null;
  return {key: `${row.side}:${row.angle_code}`, label: codeLabel[row.angle_code], value: row.value_deg,
    side: row.side, pivot, reference, ray, calculated, code: row.angle_code,
    description: `${sideLabel(row.side)} 관절 · ${codeLabel[row.angle_code]} ${row.value_deg}° · ${
      row.angle_code === 'TRUNK_TILT_VERT' ? '수직 기준' : row.angle_code === 'UPPER_ARM_FLEX_TRUNK' ? '몸통 기준' : '펴진 선의 연장선 기준'}`};
}

function frontGeometry(points, rows, width, height) {
  const map = pointMap(points, width, height);
  const mid = (a, b) => map[a] && map[b] ? {x: (map[a].x + map[b].x) / 2, y: (map[a].y + map[b].y) / 2} : null;
  const shoulder = mid('left_shoulder', 'right_shoulder'), hip = mid('left_hip', 'right_hip');
  if (!shoulder || !hip || length(sub(shoulder, hip)) < 1e-6) return [];
  const up = sub(shoulder, hip), output = [];
  for (const row of rows || []) {
    if (!finite(row.value_deg)) continue;
    let pivot, reference, ray, label, side = null;
    if (row.key === 'trunk_turn') {
      pivot = hip; reference = {x: 0, y: -1}; ray = up; label = '몸통 옆';
    } else if (row.key === 'neck_turn' && map.nose) {
      pivot = shoulder; reference = up; ray = sub(map.nose, shoulder); label = '목 옆(추정)';
    } else if (row.key === 'arm_abducted') {
      const down = sub(hip, shoulder);
      const arms = ['left', 'right'].flatMap(s => {
        const a = map[`${s}_shoulder`], b = map[`${s}_elbow`];
        return a && b && length(sub(b, a)) > 1e-6 ? [{side: s.toUpperCase(), pivot: a, ray: sub(b, a), value: magnitude(down, sub(b, a))}] : [];
      }).sort((a, b) => b.value - a.value);
      if (!arms.length) continue;
      ({pivot, ray, side} = arms[0]); reference = down; label = `${side === 'LEFT' ? '왼팔' : '오른팔'} 벌림`;
    } else continue;
    if (length(ray) < 1e-6 || !near(magnitude(reference, ray), row.value_deg)) continue;
    output.push({key: `FRONT:${row.key}`, label, side, value: row.value_deg, code: row.key,
      pivot, reference, ray, calculated: magnitude(reference, ray),
      description: `${label} ${row.value_deg}° · ${row.key === 'neck_turn' ? '양 어깨 중점과 코를 사용한 몸통 대비 추정' : row.key === 'trunk_turn' ? '양 어깨·골반 중점과 수직 기준' : '양쪽 팔 중 큰 값 · 몸통 기준'}`});
  }
  return output;
}

function matchingPreviewRows(items, view, output = []) {
  for (const item of items || []) {
    if (item.view === view) output.push(...(item.angles || []));
    matchingPreviewRows(item.alternatives, view, output);
  }
  return output;
}

export function photoAngleScene({view, photo, image, preview, result, step}) {
  const width = image?.width_px || photo?.width_px, height = image?.height_px || photo?.height_px;
  const empty = {points: [], angles: [], width, height};
  if (!finite(width) || !finite(height) || width <= 0 || height <= 0) return empty;
  // Later screens keep the same photo candidates visible, explicitly separate from the
  // immutable analysis. Each scene uses one coordinate source for both bones and arcs.
  if (result && ['result', 'review', 'excel'].includes(step)) {
    const savedPhoto = result.snapshot?.photos?.find(p => p.photo_id === photo.photo_id);
    if (savedPhoto && equalDimensions(savedPhoto, width, height)) {
      const candidate = photoAngleScene({view, photo, image, preview, step: 'provisional'});
      if (candidate.angles.length) return candidate;
    }
  }
  let points, rows, forward;
  const origin = result && ['result', 'review', 'excel'].includes(step) ? 'analysis' : 'preview';
  if (result && ['result', 'review', 'excel'].includes(step)) {
    const poses = (result.pose?.slots || []).filter(s => s.photo_id === photo.photo_id);
    const source = poses[0];
    if (!source) return empty;
    const savedPhoto = result.snapshot?.photos?.find(p => p.photo_id === photo.photo_id);
    if (!equalDimensions(savedPhoto, width, height)) return empty;
    points = source.points || [];
    if (poses.length !== 1) return {...empty, points};
    const slots = (result.snapshot?.capture?.slots || []).filter(s => s.photo_id === photo.photo_id && s.slot_no === source.slot_no);
    if (slots.length !== 1 || !['LEFT', 'RIGHT'].includes(slots[0].camera_side)) return {...empty, points};
    forward = slots[0].forward_direction;
    rows = (source.angles || []).filter(a => a.side === slots[0].camera_side && !a.diagnostic);
  } else {
    const source = preview?.views?.[view];
    if (!source || source.photo_id !== photo.photo_id || !equalDimensions(source, width, height)) return empty;
    points = source.points || [];
    if (view === 'FRONT') {
      const angles = source.guess && source.guess.orientation !== 'SIDE' ? frontGeometry(points, preview.front, width, height) : [];
      return {...empty, points, angles, origin};
    }
    forward = source.guess?.forward_direction;
    rows = matchingPreviewRows(preview.measured, view);
  }
  const seen = new Set();
  const angles = (rows || []).flatMap(row => {
    const geometry = sideAngleGeometry(points, row, forward, width, height);
    if (!geometry || seen.has(geometry.key)) return [];
    seen.add(geometry.key); return [geometry];
  });
  return {...empty, points, angles, origin};
}

const overlaps = (a, b, pad = 0) => a.x < b.x + b.w + pad && a.x + a.w + pad > b.x && a.y < b.y + b.h + pad && a.y + a.h + pad > b.y;
const scaled = (pivot, vector, distance) => ({x: pivot.x + vector.x / length(vector) * distance, y: pivot.y + vector.y / length(vector) * distance});
const number = n => Number(n.toFixed(3));
const xy = p => `${number(p.x)} ${number(p.y)}`;

// Font loading can finish after the first render. Resize just the SVG labels, never
// rerender forms or replace user edits. SVG text length includes actual font shaping.
export function fitPhotoAngleLabels(root) {
  for (const group of root.querySelectorAll('.quick-photo .angle-overlay [data-angle]')) {
    if (!group.isConnected) continue;
    const rect = group.querySelector('rect'), label = group.querySelector('.angle-label');
    const content = group.querySelector('.angle-label-text');
    const font = Number(group.parentElement.getAttribute('font-size'));
    const svg = group.ownerSVGElement, scale = svg.getScreenCTM()?.a;
    const width = svg.viewBox.baseVal.width, margin = font * 0.4;
    if (!finite(scale) || !(scale > 0) || !(font > 0)) continue;
    const boxWidth = (content.getBoundingClientRect().width + 8) / scale, height = font * 1.65;
    if (!finite(boxWidth) || !(boxWidth > 0)) continue;
    const x = Math.max(margin, Math.min(width - boxWidth - margin, Number(rect.getAttribute('x'))));
    const y = Math.max(margin, Math.min(svg.viewBox.baseVal.height - height - margin, Number(rect.getAttribute('y'))));
    for (const element of [rect, label]) {
      element.setAttribute('x', x); element.setAttribute('y', y);
      element.setAttribute('width', boxWidth); element.setAttribute('height', height);
    }
    const leader = group.querySelector('.angle-leader');
    leader.setAttribute('x2', Math.max(x, Math.min(x + boxWidth, Number(leader.getAttribute('x1')))));
    leader.setAttribute('y2', Math.max(y, Math.min(y + height, Number(leader.getAttribute('y1')))));
  }
}

export function renderPhotoAngles(scene, options = {}) {
  if (!scene.angles.length) return '';
  if (typeof document !== 'undefined' && document.fonts)
    document.fonts.ready.then(() => fitPhotoAngleLabels(document));
  const {width, height} = scene, font = Math.max(width, height) / 47;
  const family = options.fontFamily || (typeof document !== 'undefined' ? getComputedStyle(document.body).fontFamily : 'sans-serif');
  const context = typeof document !== 'undefined' ? document.createElement('canvas').getContext('2d') : null;
  if (context) context.font = `750 ${font}px ${family}`;
  const measure = options.measureText || (context ? text => context.measureText(text).width :
    text => [...text].reduce((n, c) => n + (/[^\x00-\x7f]/.test(c) ? 1 : 0.56), 0) * font);
  const radius = Math.min(width, height) * 0.065, boxes = [];
  const points = Object.values(pointMap(scene.points, width, height));
  return `<g class="angle-overlay" font-size="${font}" font-family="${escape(family)}" aria-label="현재 사진의 측정 각도">${scene.angles.map(angle => {
    const {pivot, reference, ray} = angle, a = scaled(pivot, reference, radius), b = scaled(pivot, ray, radius);
    const sweep = signed(reference, ray) >= 0 ? 1 : 0;
    const arc = Math.abs(signed(reference, ray)) < 0.01 ? '' : `<path class="angle-arc" d="M ${xy(a)} A ${radius} ${radius} 0 0 ${sweep} ${xy(b)}"/>`;
    const text = `${angle.label} ${angle.value.toFixed(1)}°`;
    const textWidth = measure(text);
    // Text is anchored to the box center on both axes; no padding or glyph offsets.
    const bw = textWidth + 8, bh = font * 1.65, margin = font * 0.4;
    const candidates = [[1,-1],[-1,-1],[1,1],[-1,1],[1,0],[-1,0],[0,-1],[0,1]].map(([dx, dy]) => {
      const box = {x: Math.max(margin, Math.min(width - bw - margin, pivot.x + dx * radius * 1.8 - (dx < 0 ? bw : dx === 0 ? bw / 2 : 0))),
        y: Math.max(margin, Math.min(height - bh - margin, pivot.y + dy * radius * 1.5 - (dy < 0 ? bh : dy === 0 ? bh / 2 : 0))), w: bw, h: bh};
      box.cost = boxes.filter(old => overlaps(box, old, margin)).length * 10000 + points.filter(p => overlaps(box, {x: p.x, y: p.y, w: 1, h: 1}, margin)).length * 500 +
        Math.hypot(box.x + bw / 2 - pivot.x, box.y + bh / 2 - pivot.y);
      return box;
    });
    const box = candidates.sort((a, b) => a.cost - b.cost)[0]; boxes.push(box);
    const refEnd = scaled(pivot, reference, radius * 1.65), rayEnd = scaled(pivot, ray, radius * 1.4);
    const anchor = {x: Math.max(box.x, Math.min(box.x + bw, b.x)), y: Math.max(box.y, Math.min(box.y + bh, b.y))};
    return `<g data-angle="${escape(angle.key)}"><title>${escape(angle.description)}</title>
      <line class="angle-reference" x1="${pivot.x}" y1="${pivot.y}" x2="${refEnd.x}" y2="${refEnd.y}"/>
      <line class="angle-ray" x1="${pivot.x}" y1="${pivot.y}" x2="${rayEnd.x}" y2="${rayEnd.y}"/>${arc}
      <line class="angle-leader" x1="${b.x}" y1="${b.y}" x2="${anchor.x}" y2="${anchor.y}"/>
      <rect x="${box.x}" y="${box.y}" width="${bw}" height="${bh}" rx="${font * 0.25}"/>
      <foreignObject class="angle-label" x="${box.x}" y="${box.y}" width="${bw}" height="${bh}"><div xmlns="http://www.w3.org/1999/xhtml" class="angle-label-center"><span class="angle-label-text">${escape(text)}</span></div></foreignObject></g>`;
  }).join('')}</g>`;
}

// Keep the horizontal inset at four screen pixels when the photo viewer resizes.
if (typeof window !== 'undefined' && typeof window.addEventListener === 'function')
  window.addEventListener('resize', () => fitPhotoAngleLabels(document));
