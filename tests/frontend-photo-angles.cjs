const assert = require('node:assert/strict');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const fixture = require('./fixtures/photo-angle-geometry.json');
(async () => {
  const {sideAngleGeometry, photoAngleScene, renderPhotoAngles, renderPhotoSkeleton} = await import(pathToFileURL(path.join(__dirname, '../frontend/photo-angle-overlay.js')).href);
  const joints = [{name: 'shoulder', x_px: 20, y_px: 20, confidence: .3},
    {name: 'elbow', x_px: 30, y_px: 30, confidence: .2999},
    {name: 'wrist', x_px: 40, y_px: 40, confidence: .1952}];
  const skeletonInput = {width: 100, height: 100, points: joints};
  const originalSkeleton = JSON.stringify(skeletonInput);
  const bones = [['shoulder', 'elbow'], ['elbow', 'wrist']];
  const skeleton = renderPhotoSkeleton(skeletonInput, bones);
  assert.equal(skeleton.hasLowConfidence, true);
  assert.equal((skeleton.markup.match(/class="pose-low-point"/g) || []).length, 2);
  assert.equal((skeleton.markup.match(/class="pose-low-line"/g) || []).length, 2);
  assert.equal((skeleton.markup.match(/class="pose-point"/g) || []).length, 1, '0.3 remains a normal point');
  assert.equal(JSON.stringify(skeletonInput), originalSkeleton, 'presentation must not promote confidence or mutate points');
  const confident = renderPhotoSkeleton({...skeletonInput, points: joints.map(p => ({...p, confidence: .8}))}, bones);
  assert.equal(confident.hasLowConfidence, false);
  assert.equal((confident.markup.match(/class="pose-line"/g) || []).length, 2);
  for (const invalid of [{confidence: 0}, {confidence: null}, {confidence: NaN}, {confidence: -1},
    {confidence: 1.1}, {x_px: -1}, {x_px: 100}, {y_px: 100}, {x_px: Infinity}]) {
    const hidden = renderPhotoSkeleton({...skeletonInput, points: [joints[0], {...joints[1], ...invalid}]}, bones);
    assert.equal(hidden.hasLowConfidence, false);
    assert.equal((hidden.markup.match(/<line/g) || []).length, 0, 'missing endpoint must never be fabricated');
  }
  assert.equal(renderPhotoSkeleton({width: 0, height: 100, points: joints}, bones).markup, '');
  const supported = ['TRUNK_TILT_VERT', 'UPPER_ARM_FLEX_TRUNK', 'ELBOW_FLEX', 'KNEE_FLEX'];
  let checked = 0;
  for (const test of fixture.cases) {
    for (const row of test.angles.filter(a => supported.includes(a.angle_code))) {
      const geometry = sideAngleGeometry(test.points, row, test.forward, test.width, test.height);
      assert.ok(geometry, `${test.name} ${row.side} ${row.angle_code}`);
      assert.ok(Math.abs(geometry.calculated - row.value_deg) < 1e-8, 'geometry agrees with the Python engine, including negative and zero angles');
      const joint = {TRUNK_TILT_VERT: 'hip', UPPER_ARM_FLEX_TRUNK: 'shoulder', ELBOW_FLEX: 'elbow', KNEE_FLEX: 'knee'}[row.angle_code];
      const point = test.points.find(p => p.name === `${row.side.toLowerCase()}_${joint}`);
      assert.deepEqual(geometry.pivot, {x: point.x_px, y: point.y_px}, 'the arc belongs to the calculation vertex, not the wrist');
      assert.equal(sideAngleGeometry(test.points, {...row, value_deg: null}, test.forward, test.width, test.height), null);
      assert.equal(sideAngleGeometry(test.points, {...row, value_deg: row.value_deg + 0.3}, test.forward, test.width, test.height), null, 'do not put a mismatched stored value on a plausible-looking arc');
      checked++;
    }
  }
  const test = fixture.cases[0], photo = {photo_id: 11}, image = {width_px: test.width, height_px: test.height};
  const rows = test.angles.filter(row => row.side === 'LEFT' && supported.includes(row.angle_code));
  const preview = {views: {LEFT: {...image, photo_id: 11, points: test.points, guess: {forward_direction: test.forward}}},
    measured: [{view: 'RIGHT', angles: rows.map(a => ({...a, value_deg: 99})), alternatives: [{view: 'LEFT', angles: rows}]}]};
  const scene = photoAngleScene({view: 'LEFT', photo, image, preview, step: 'provisional'});
  assert.equal(scene.angles.length, 4);
  assert.ok(scene.angles.every(a => a.value !== 99), 'merged max from another photo is not an overlay on this photo');
  assert.match(renderPhotoAngles(scene), /angle-reference/);
  assert.match(renderPhotoAngles(scene), /angle-arc/);
  assert.equal(photoAngleScene({view: 'LEFT', photo: {photo_id: 12}, image, preview, step: 'provisional'}).points.length, 0);
  assert.equal(photoAngleScene({view: 'LEFT', photo, image: {...image, width_px: 601}, preview, step: 'provisional'}).angles.length, 0);
  const noJoint = test.points.filter(p => p.name !== 'left_elbow');
  assert.equal(sideAngleGeometry(noJoint, rows.find(a => a.angle_code === 'ELBOW_FLEX'), test.forward, test.width, test.height), null);
  const outside = test.points.map(p => p.name === 'left_elbow' ? {...p, x_px: -1} : p);
  assert.equal(sideAngleGeometry(outside, rows.find(a => a.angle_code === 'ELBOW_FLEX'), test.forward, test.width, test.height), null);
  const zeroLength = test.points.map(p => p.name === 'left_wrist' ? {...p, ...{x_px: 300, y_px: 430}} : p);
  assert.equal(sideAngleGeometry(zeroLength, rows.find(a => a.angle_code === 'ELBOW_FLEX'), test.forward, test.width, test.height), null);
  const zeroScene = fixture.cases.find(c => c.name === 'zero-SCREEN_LEFT');
  const zeroAngle = sideAngleGeometry(zeroScene.points, zeroScene.angles.find(a => a.angle_code === 'KNEE_FLEX'), zeroScene.forward, 600, 1000);
  assert.equal(zeroAngle.value, 0);
  assert.match(renderPhotoAngles({width: 600, height: 1000, points: zeroScene.points, angles: [zeroAngle]}), /0\.0°/);

  const source = {slot_no: 1, photo_id: 11, points: test.points, angles: test.angles};
  const saved = {pose: {slots: [source]}, snapshot: {photos: [{...photo, ...image}], capture: {slots: [{slot_no: 1, photo_id: 11, camera_side: 'RIGHT', forward_direction: test.forward}]}}};
  const historical = photoAngleScene({view: 'LEFT', photo, image, result: saved, step: 'result'});
  assert.equal(historical.angles.length, 4);
  assert.ok(historical.angles.every(a => a.side === 'RIGHT'), 'a left photo slot does not force left body joints');
  const before = JSON.stringify(saved);
  for (const step of ['result', 'review', 'excel']) {
    for (const view of ['LEFT', 'RIGHT']) {
      const candidates = {...preview, views: {[view]: preview.views.LEFT},
        measured: [{view, angles: rows}]};
      const later = photoAngleScene({view, photo, image, preview: candidates, result: saved, step});
      assert.equal(later.origin, 'preview', 'candidate overlays are explicitly distinguished from final analysis');
      assert.equal(later.angles.length, 4);
      assert.deepEqual(later.points, test.points, 'arcs and bones share their source coordinates');
    }
  }
  assert.equal(JSON.stringify(saved), before, 'candidate display must not change saved values or scores');
  assert.equal(historical.origin, 'analysis');
  const wrongPreview = {...preview, views: {LEFT: {...preview.views.LEFT, photo_id: 123}}};
  const fallback = photoAngleScene({view: 'LEFT', photo, image, preview: wrongPreview, result: saved, step: 'review'});
  assert.equal(fallback.origin, 'analysis', 'a stale candidate falls back to the saved source');
  assert.ok(fallback.angles.every(a => a.side === 'RIGHT'));
  const mismatchedSaved = {...saved, snapshot: {...saved.snapshot, photos: [{...photo, width_px: 99}]}};
  assert.equal(photoAngleScene({view: 'LEFT', photo, image, preview, result: mismatchedSaved, step: 'result'}).angles.length, 0);
  const measured = [];
  const markup = renderPhotoAngles(scene, {measureText: text => {measured.push(text); return text.length * 7;}});
  const widths = [...markup.matchAll(/<rect[^>]*width="([^"]+)"/g)].map(m => Number(m[1]));
  for (let i = 0; i < measured.length; i++)
    assert.ok(Math.abs(widths[i] - measured[i].length * 7 - 8) < 1e-6,
      'initial label width includes four pixels on each horizontal side');
  const rects = [...markup.matchAll(/<rect x="([^"]+)" y="([^"]+)" width="([^"]+)" height="([^"]+)"/g)];
  const labels = [...markup.matchAll(/<foreignObject class="angle-label" x="([^"]+)" y="([^"]+)" width="([^"]+)" height="([^"]+)"/g)];
  assert.equal(labels.length, scene.angles.length);
  for (let i = 0; i < labels.length; i++) assert.deepEqual(labels[i].slice(1), rects[i].slice(1), 'centered HTML area matches its SVG box');
  assert.equal((markup.match(/class="angle-label-center"/g) || []).length, scene.angles.length);
  const duplicated = {...saved, pose: {slots: [source, {...source, slot_no: 2}]}};
  assert.equal(photoAngleScene({view: 'LEFT', photo, image, result: duplicated, step: 'review'}).angles.length, 0);
  assert.equal(photoAngleScene({view: 'LEFT', photo, image, preview, result: {pose: {slots: []}}, step: 'result'}).angles.length, 0, 'do not replace a saved analysis with live preview angles');

  const front = fixture.front;
  const frontal = {views: {FRONT: {photo_id: 11, width_px: front.width, height_px: front.height, points: front.points, guess: {orientation: 'FRONT'}}}, front: front.rows};
  const frontalScene = photoAngleScene({view: 'FRONT', photo, image, preview: frontal, step: 'provisional'});
  assert.equal(frontalScene.angles.length, front.rows.length);
  for (const step of ['result', 'review', 'excel']) {
    const later = photoAngleScene({view: 'FRONT', photo, image, preview: frontal, result: saved, step});
    assert.equal(later.angles.length, front.rows.length);
    assert.equal(later.origin, 'preview');
  }
  for (const angle of frontalScene.angles) assert.ok(Math.abs(angle.calculated - angle.value) <= 0.11);
  assert.match(frontalScene.angles.find(a => a.code === 'neck_turn').description, /코/);
  const badFront = {...frontal, front: front.rows.map(r => ({...r, value_deg: r.value_deg + 1}))};
  assert.equal(photoAngleScene({view: 'FRONT', photo, image, preview: badFront, step: 'provisional'}).angles.length, 0);
  assert.equal(renderPhotoAngles({width: 600, height: 1000, points: [], angles: []}), '');
  console.log(`PASS ${checked} Python-engine angle geometries, exact joint vertices, extension-based flexion, signed/zero values, source photo/body-side ownership, stale/missing/bad coordinates, saved analyses and front-plane references`);
})().catch(error => {console.error(error); process.exitCode = 1;});
