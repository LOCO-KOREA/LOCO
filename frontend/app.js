// Native SVG prototype. Original artwork and text stay in their original groups.
const NS = "http://www.w3.org/2000/svg",
  HTML = "http://www.w3.org/1999/xhtml";
const screens = {
  S01: "02_조사목록_조사생성.svg",
  S02: "02_조사목록_조사생성.svg",
  S03: "03_작업정보_작업자.svg",
  conditions: "04_작업조건입력.svg",
  S04: "05_사진등록.svg",
  S05: "09_분석진행.svg",
  S06: "06_자세분석결과.svg",
  manual: "06a_REBA수동입력.svg",
  S07: "07_조사자확인.svg",
  S08: "08_엑셀문서출력.svg",
  S09: "10_설정.svg",
};
const labels = [
  "조사 목록",
  "조사 개요",
  "작업·직접입력",
  "사진 등록",
  "분석 진행",
  "사진·REBA 분석",
  "11호 초안·검토",
  "보고서 내보내기",
  "설정",
];
const navBounds = [24, 155, 286, 453, 584, 715, 887, 1059, 1247, 1390];
const edits = new Map();
let page = "S01",
  generation = 0;
const $ = (s) => document.querySelector(s),
  number = (el, key) => Number(el.getAttribute(key) || 0);
function el(name, attrs = {}) {
  const node = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  return node;
}
function toast(text) {
  $("#toast").textContent = text;
  $("#toast").hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => ($("#toast").hidden = true), 4200);
}
function modal(title, text) {
  $("#dialog-title").textContent = title;
  $("#dialog-body").textContent = text;
  $("#dialog").showModal();
}
function hit(parent, box, name, callback) {
  const g = el("g", {
    class: "hit",
    role: "button",
    tabindex: 0,
    "aria-label": name,
  });
  g.append(
    el("rect", {
      x: box.x,
      y: box.y,
      width: box.width,
      height: box.height,
      rx: box.rx || 6,
      fill: "transparent",
    }),
  );
  g.addEventListener("click", callback);
  g.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      callback();
    }
  });
  parent.append(g);
  return g;
}
function localBox(rect) {
  return {
    x: number(rect, "x"),
    y: number(rect, "y"),
    width: number(rect, "width"),
    height: number(rect, "height"),
    rx: number(rect, "rx"),
  };
}
function contains(rect, text) {
  const x = number(text, "x"),
    y = number(text, "y"),
    b = localBox(rect);
  return x >= b.x && x <= b.x + b.width && y > b.y && y < b.y + b.height;
}
function editFields(svg) {
  // Replace only literal text inside existing input rectangles with a real input.
  // Rectangle, group transform, font, and text baseline remain derived from the SVG.
  const rects = [...svg.querySelectorAll("rect")];
  for (const rect of rects) {
    const b = localBox(rect),
      parent = rect.parentElement;
    if (
      b.y < 200 ||
      b.width < 120 ||
      b.width > 600 ||
      b.height < 32 ||
      b.height > 60 ||
      rect.getAttribute("fill")?.toLowerCase() !== "#ffffff" ||
      !rect.hasAttribute("stroke")
    )
      continue;
    const values = [...parent.children].filter(
      (t) =>
        t.tagName === "text" &&
        contains(rect, t) &&
        t.getAttribute("text-anchor") !== "middle" &&
        Number(t.getAttribute("font-weight") || 400) <= 500,
    );
    if (values.length !== 1) continue;
    const text = values[0],
      original = text.textContent.trim();
    if (original.length > 100 || number(text, "x") - b.x > 30) continue;
    const preceding = [...parent.children]
      .filter(
        (t) =>
          t.tagName === "text" &&
          number(t, "x") >= b.x - 2 &&
          number(t, "x") < b.x + 40 &&
          number(t, "y") < b.y &&
          number(t, "y") > b.y - 45,
      )
      .pop();
    const label =
      preceding?.textContent.trim() ||
      original.replace(/[∨▾]/g, "").trim() ||
      "입력";
    const key = `${screens[page]}:${b.x}:${b.y}`;
    const foreign = el("foreignObject", {
      x: b.x,
      y: b.y,
      width: b.width,
      height: b.height,
    });
    const input = document.createElementNS(HTML, "input");
    input.className = "design-field";
    input.type = "text";
    input.setAttribute("aria-label", label);
    input.value = edits.get(key) ?? original;
    input.style.fontFamily =
      text.getAttribute("font-family") || "Pretendard, sans-serif";
    input.style.fontSize = (text.getAttribute("font-size") || 14) + "px";
    input.style.fontWeight = text.getAttribute("font-weight") || 400;
    input.style.color = text.getAttribute("fill") || "#242D41";
    if (edits.has(key)) text.textContent = input.value;
    input.style.color = "transparent";
    input.style.caretColor = "#242D41";
    input.addEventListener("focus", () => {
      text.style.visibility = "hidden";
      input.style.color = text.getAttribute("fill") || "#242D41";
    });
    input.addEventListener("blur", () => {
      text.textContent = input.value;
      text.style.visibility = "";
      input.style.color = "transparent";
    });
    input.addEventListener("input", () => edits.set(key, input.value));
    foreign.append(input);
    parent.append(foreign);
  }
}
function actionFor(text) {
  const t = text.replace(/\s+/g, " ").trim();
  if (/작업 조건 입력/.test(t)) return () => go("conditions");
  if (/관찰값|수동 입력|수동 관찰|REBA 입력/.test(t) && page !== "manual")
    return () => go("manual");
  if (/사진 등록|사진 배정/.test(t)) return () => go("S04");
  if (/조사 만들고|작업 등록|조사 다시 열기|작업 조건 살펴/.test(t))
    return () => go("S03");
  if (/11개 기준|11호 초안|판정 검토|조사자 확인/.test(t))
    return () => go("S07");
  if (/내보내기|Excel 저장|엑셀 저장/.test(t))
    return () =>
      page === "S08"
        ? toast("화면 시안 목업입니다. 실제 Excel 출력은 연결 전입니다.")
        : go("S08");
  if (/분석 시작|분석 실행/.test(t)) return () => go("S05");
  if (/결과 보기|결과 확인|사진·REBA 살펴|분석 결과/.test(t))
    return () => go("S06");
  if (/촬영 안내/.test(t))
    return () =>
      modal(
        "촬영 안내",
        "같은 작업자의 정상 작업 3회 × 지정 순간 5개를 촬영합니다. 중간 사진은 상자 바닥면이 선반 높이의 절반을 통과하는 순간입니다. 정측면·수평 렌즈·고정 카메라로 촬영합니다.",
      );
  if (/이전/.test(t))
    return () =>
      go(
        {
          S03: "S01",
          conditions: "S03",
          S04: "conditions",
          S05: "S04",
          S06: "S04",
          manual: "S06",
          S07: "S06",
          S08: "S07",
        }[page] || "S01",
      );
  if (
    /저장|적용|다시 계산|생성|계산|취소|검토|삭제|작업 추가|사진 선택|사진 추가|업로드|해제|비우기/.test(
      t,
    )
  )
    return () =>
      toast(
        "시안 확인용 목업입니다. 입력은 탭 메모리에 유지되며 실제 저장·분석·출력은 연결 전입니다.",
      );
  return null;
}
function bindActions(svg) {
  for (const text of [...svg.querySelectorAll("text")]) {
    if (number(text, "y") < 200 || text.style.visibility === "hidden") continue;
    const callback = actionFor(text.textContent);
    if (!callback) continue;
    const parent = text.parentElement;
    const rect = [...parent.children]
      .filter(
        (r) =>
          r.tagName === "rect" &&
          contains(r, text) &&
          number(r, "height") >= 26 &&
          number(r, "height") <= 65,
      )
      .sort((a, b) => number(a, "width") - number(b, "width"))[0];
    if (rect) {
      if (rect.dataset.bound) continue;
      rect.dataset.bound = "true";
      hit(parent, localBox(rect), text.textContent.trim(), callback);
    }
  }
  // Original stepper uses separate circles and labels; overlay its exact spans.
  if (!["S01", "S02", "S09"].includes(page)) {
    ["S03", "S04", "S06", "S07", "S08"].forEach((id, i) =>
      hit(
        svg,
        { x: 48 + i * 270, y: 290, width: 235, height: 40 },
        ["작업 정보", "사진 등록", "자세 분석", "판정 검토", "보고서"][i],
        () => go(id),
      ),
    );
  }
  labels.forEach((name, i) =>
    hit(
      svg,
      {
        x: navBounds[i],
        y: 55,
        width: navBounds[i + 1] - navBounds[i] - 5,
        height: 46,
      },
      name,
      () => go("S0" + (i + 1)),
    ),
  );
  hit(svg, { x: 24, y: 5, width: 90, height: 36 }, "LOCO 조사 목록", () =>
    go("S01"),
  );
  hit(svg, { x: 1380, y: 10, width: 32, height: 29 }, "목업 안내", () =>
    modal(
      "LOCO 시안 목업",
      "docs/ui 원본 SVG 배치를 사용하고 헤더 로고만 C 로고로 교체했습니다. 화면에 보이는 사진·점수는 원본 시안의 예시입니다. 입력란은 편집할 수 있으나 메모리에만 유지됩니다. 실제 분석·저장·출력은 연결 전입니다.",
    ),
  );
  const guide = svg.querySelector('g[aria-label^="로코 안내 위젯"]');
  if (guide) {
    hit(
      guide,
      { x: 1290, y: 817, width: 28, height: 25 },
      "로코 말풍선 접기",
      () => {
        for (const child of guide.children)
          if (child.tagName !== "svg") child.style.display = "none";
      },
    );
    const robot = guide.querySelector("svg");
    if (robot)
      hit(
        guide,
        {
          x: number(robot, "x"),
          y: number(robot, "y"),
          width: number(robot, "width"),
          height: number(robot, "height"),
        },
        "로코 안내 다시 열기",
        () => {
          for (const child of guide.children) child.style.display = "";
        },
      );
    const cta = guide.querySelector('text[font-weight="600"]');
    if (cta) {
      const callback = actionFor(cta.textContent);
      if (callback)
        hit(
          guide,
          { x: 1080, y: 930, width: 230, height: 35 },
          cta.textContent.trim(),
          callback,
        );
    }
  }
}
async function render() {
  const request = ++generation;
  try {
    const response = await fetch(
      "assets/screens/" + encodeURIComponent(screens[page]),
    );
    if (!response.ok) throw new Error("시안을 불러오지 못했습니다.");
    const xml = await response.text();
    if (request !== generation) return;
    const doc = new DOMParser().parseFromString(xml, "image/svg+xml");
    if (doc.querySelector("parsererror"))
      throw new Error("SVG 문서를 읽지 못했습니다.");
    const svg = document.importNode(doc.documentElement, true);
    svg.setAttribute(
      "aria-label",
      svg.querySelector("title")?.textContent || "LOCO 화면",
    );
    $("#screen").replaceChildren(svg);
    document.title =
      "LOCO · " + (svg.querySelector("title")?.textContent || "UI 목업");
    editFields(svg);
    bindActions(svg);
  } catch (error) {
    $("#screen").textContent = error.message;
  }
}
function go(id) {
  if (!screens[id]) return;
  page = id;
  location.hash = id;
  render();
  window.scrollTo({ top: 0 });
}
window.addEventListener("hashchange", () => {
  const id = location.hash.slice(1);
  if (screens[id] && id !== page) {
    page = id;
    render();
  }
});
$("#close-dialog").addEventListener("click", () => $("#dialog").close());
page = screens[location.hash.slice(1)] ? location.hash.slice(1) : "S01";
render();
