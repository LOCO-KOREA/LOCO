/* LOCO field-guide widget ported from LOCO_UI_Navigation.html.
   Load with <script src="./loco-guide.js"></script> and mount with <loco-guide page="S01"></loco-guide>.
   Listen for "loco-guide-action" to connect navigation, capture guide, and review actions. */
const PET_GUIDES = Object.freeze({
  S01:{message:'저장한 조사를 열거나 새 조사를 시작해요. 작업의 근거를 차근차근 기록할 수 있어요.',cta:'조사 목록 열기',action:'S02'},
  S02:{message:'조사 개요와 현장 상황을 기록해 주세요. 모르는 항목은 비워도 괜찮아요.',cta:'작업 개요 살펴보기',action:'S03'},
  S03:{message:'작업 종류와 관계없이 같은 11개 기준을 확인해요. 입력 서식은 질문 순서만 바꿔요.',cta:'작업 조건 입력으로',action:'S04'},
  S04:{message:'하루 시간·중량·힘·횟수는 관찰과 면담으로 기록해요. 사진 없이도 기준 초안을 계산할 수 있어요.',cta:'기준 초안 계산·검토',action:'calculate'},
  S05:{message:'사진은 필요한 만큼 선택해요. 각 사진의 촬영조건과 실제 관찰 하중을 확인해 주세요.',cta:'촬영 안내 다시 보기',action:'guide'},
  S06:{message:'각도는 후보이며 총점이 없는 사진은 0점이 아니에요. 누락된 관찰값을 확인해 주세요.',cta:'현재 사진 관찰값 보기',action:'manual'},
  S07:{message:'계산 초안과 조사자의 결론은 별도로 남아요. 결론을 적어도 부족한 입력을 숨기지 않아요.',cta:'4호 합산 해석 살펴보기',action:'criterion4'},
  S08:{message:'출력할 분석과 전후 비교를 선택해요. 다음 입력 안내에서 부족한 근거로 이동할 수 있어요.',cta:'다음 입력으로 이동',action:'next'},
  S09:{message:'전체 처리 종료와 계산의 완전성은 달라요. 요청 범위와 사진별 진단을 확인해 주세요.',cta:'자세·REBA 결과 보기',action:'S06'},
  S10:{message:'분석 규칙과 모델·설명·안내 설정을 확인해요. 조용한 모드는 반복 안내를 줄여줘요.',cta:'조용한 모드 전환',action:'quiet'}
});

const PET_ANSWERS = Object.freeze({
  missing: '모르는 값은 아직 모르는 값이에요. 0점이나 비해당으로 채우지 않아요. 옆의 입력 안내에서 필요한 관찰을 확인해 주세요.',
  time: '표본 사진의 비율은 하루 노출시간이 아니에요. 하루 시간과 횟수는 현장 관찰·면담·문서에서 직접 기록해야 해요.',
  review: '검토 완료는 조사자가 눌러 남기는 표시예요. 모든 입력이 끝났다거나 법적으로 승인됐다는 뜻은 아니에요.'
});

const PET_STYLE = [
  ':host{position:fixed;right:24px;bottom:21px;z-index:45;display:block;pointer-events:none;font-family:Pretendard,"Noto Sans CJK KR","Malgun Gothic",Arial,sans-serif;color:#242d41;line-height:1.65}',
  ':host([visible="false"]){display:none}',
  '.pet-shell{display:flex;align-items:flex-end;gap:0;touch-action:none;pointer-events:none}',
  '.pet-shell button{border:0;background:none;color:inherit;font-family:inherit;cursor:pointer}',
  '.pet-shell button:focus-visible{outline:3px solid #b9bdff;outline-offset:3px}',
  '.pet-bubble{width:252px;border:1px solid #e1e4f1;background:rgba(255,255,255,.98);box-shadow:0 7px 32px rgba(51,67,106,.07);border-radius:13px 13px 3px 13px;padding:13px 15px;margin-bottom:28px;position:relative;line-height:1.7;touch-action:auto;pointer-events:none}',
  '.pet-title{color:#686da9;font-size:10px;font-weight:650;margin-bottom:4px;display:flex;align-items:center;justify-content:space-between}',
  '.pet-role{font-size:8px;color:#aab0c8;font-weight:400}',
  '.pet-copy{color:#6f7c95;font-size:11px;margin:0}',
  '.pet-cta{font:inherit;font-size:10px;color:#5c61db;margin-top:8px;padding:0;border:0;background:none;cursor:pointer;pointer-events:auto}',
  '.pet-character{display:block;width:94px;height:115px;padding:0;border:0;background:none;cursor:grab;filter:drop-shadow(0 8px 5px rgba(39,51,86,.07));transform-origin:bottom;animation:pet-bob 6s ease-in-out infinite;pointer-events:auto;touch-action:none}',
  '.pet-character:active{cursor:grabbing}',
  '.pet-character svg{width:100%;height:100%;display:block}',
  '.pet-eyes{animation:blink 5s infinite;transform-origin:center 54%}',
  '.pet-mini .pet-bubble{display:none}',
  '.pet-close{height:20px;width:20px;border:0;color:#b5bac9;padding:0;background:none;font:14px Arial,sans-serif;cursor:pointer;pointer-events:auto}',
  '.pet-chat{width:294px;max-height:420px;overflow:auto;touch-action:auto}',
  '.pet-options{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px;pointer-events:auto}',
  '.pet-options button{padding:5px 8px;font-family:inherit;font-size:9px;background:#f4f5fc;color:#8990b9;border:0;border-radius:6px;cursor:pointer}',
  '.pet-disclaimer{font-size:8px;color:#aeb4c4;border-top:1px solid #e8ebf2;padding-top:9px;margin-top:11px}',
  '@keyframes pet-bob{0%,70%,100%{transform:translateY(0) rotate(0)}78%{transform:translateY(-5px) rotate(-3deg)}86%{transform:translateY(0) rotate(2deg)}94%{transform:translateY(-2px)}}',
  '@keyframes blink{0%,44%,48%,100%{transform:scaleY(1)}46%{transform:scaleY(.08)}}',
  '@media(max-width:1200px){:host{right:24px}.pet-bubble{width:228px}}',
  '@media(max-width:950px){.pet-bubble{width:215px}}',
  '@media(max-width:680px){:host{right:8px;bottom:8px}.pet-character{width:69px;height:84px}.pet-bubble{width:200px;margin-bottom:15px;padding:10px 12px}.pet-copy{font-size:10px}.pet-title{font-size:9px}}',
  '@media(prefers-reduced-motion:reduce){.pet-character,.pet-eyes{animation:none}}'
].join('');

class LocoGuide extends HTMLElement {
  static get observedAttributes() { return ['page', 'visible', 'mode']; }

  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this.shadowRoot.innerHTML = '<style>' + PET_STYLE + '</style><div class="pet-shell"></div>';
    this.shell = this.shadowRoot.querySelector('.pet-shell');
    this.state = { open: false, tip: null, dismissedPage: null, position: null, drag: null, skipClick: false };
    this.onKeyDown = this.onKeyDown.bind(this);
    this.onFocusIn = this.onFocusIn.bind(this);
    this.onResize = this.onResize.bind(this);
  }

  connectedCallback() {
    if (!this.hasAttribute('page')) this.setAttribute('page', 'S01');
    this.render();
    document.addEventListener('keydown', this.onKeyDown);
    document.addEventListener('focusin', this.onFocusIn);
    window.addEventListener('resize', this.onResize);
  }

  disconnectedCallback() {
    document.removeEventListener('keydown', this.onKeyDown);
    document.removeEventListener('focusin', this.onFocusIn);
    window.removeEventListener('resize', this.onResize);
  }

  attributeChangedCallback(name, oldValue, newValue) {
    if (oldValue === newValue || !this.shell) return;
    if (name === 'page' && oldValue !== null) {
      this.state.open = false;
      this.state.tip = null;
      this.state.dismissedPage = null;
    }
    this.render();
  }

  get page() { return this.getAttribute('page') || 'S01'; }
  set page(value) { this.setAttribute('page', value); }
  get visible() { return this.getAttribute('visible') !== 'false'; }
  set visible(value) {
    this.setAttribute('visible', String(Boolean(value)));
    this.emit('loco-guide-preference-change', { visible: Boolean(value) });
  }
  get mode() { return this.getAttribute('mode') || 'normal'; }
  set mode(value) {
    this.setAttribute('mode', value === 'quiet' ? 'quiet' : 'normal');
    this.emit('loco-guide-preference-change', { mode: this.mode });
  }

  emit(name, detail) {
    this.dispatchEvent(new CustomEvent(name, { bubbles: true, composed: true, detail: detail }));
  }

  mascot(sleep) {
    const eyes = sleep
      ? '<path d="M35 52h9m16 0h9" stroke="#929bd6" stroke-width="4" stroke-linecap="round"/>'
      : '<g class="pet-eyes"><rect x="34" y="45" width="8" height="13" rx="4" fill="#959eee"/><rect x="61" y="45" width="8" height="13" rx="4" fill="#959eee"/><circle cx="37" cy="48" r="1.5" fill="#e9ecff"/><circle cx="64" cy="48" r="1.5" fill="#e9ecff"/></g>';
    return '<svg viewBox="0 0 104 126" role="img" aria-label="안전모를 쓴 작은 로봇 로코"><defs><linearGradient id="petBody" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#edf0ff"/><stop offset="1" stop-color="#c4cbea"/></linearGradient><linearGradient id="petHat" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#f1c779"/><stop offset="1" stop-color="#dfab59"/></linearGradient></defs><ellipse cx="52" cy="118" rx="28" ry="5" fill="#aeb9d7" opacity=".22"/><path d="M28 74 18 84l4 17 8-5 4-15m42-7 12 10-4 17-8-5-4-15" fill="#bfc8e6" stroke="#a6b3d6" stroke-width="1"/><path d="M35 99v11h-8v6h20v-17m11 0v11h-1v6h20v-6h-8V99" fill="#b8c2e1"/><rect x="29" y="70" width="47" height="35" rx="14" fill="url(#petBody)" stroke="#aebadb"/><path d="M42 82h20v12H42z" fill="#f4f5ff" stroke="#b5bfde"/><path d="m47 88 3 3 7-7" stroke="#8da79e" stroke-width="2" fill="none" stroke-linecap="round"/><rect x="16" y="34" width="10" height="23" rx="5" fill="#9eaaca"/><rect x="78" y="34" width="10" height="23" rx="5" fill="#9eaaca"/><rect x="21" y="29" width="62" height="47" rx="19" fill="url(#petBody)" stroke="#a9b7d9"/><rect x="27" y="37" width="50" height="29" rx="12" fill="#344063"/>' + eyes + '<path d="M47 59q5 4 10 0" stroke="#8a95c5" stroke-width="1.4" fill="none" stroke-linecap="round"/><path d="M26 29C27 13 37 8 52 8s25 5 26 21z" fill="url(#petHat)" stroke="#d5a963"/><path d="M47 10v14m10-14v14" stroke="#f8dfa8" stroke-width="3" stroke-linecap="round"/><rect x="20" y="27" width="64" height="7" rx="3.5" fill="#dfb161"/><path d="M76 16 82 8m-3 14 8-2" stroke="#d4b67d" stroke-width="1.4" stroke-linecap="round" opacity=".65"/></svg>';
  }

  render() {
    if (!this.shell) return;
    if (!this.visible) {
      this.shell.innerHTML = '';
      return;
    }
    const guide = PET_GUIDES[this.page] || PET_GUIDES.S01;
    const quiet = this.mode === 'quiet' || this.state.dismissedPage === this.page;
    const shellClass = quiet && !this.state.open ? 'pet-shell pet-mini' : 'pet-shell';
    const bubbleClass = this.state.open ? 'pet-bubble pet-chat' : 'pet-bubble';
    this.shadowRoot.querySelector('.pet-shell').className = shellClass;
    this.shell = this.shadowRoot.querySelector('.pet-shell');
    this.shell.innerHTML = '<div class="' + bubbleClass + '" role="region" aria-label="로코 안내">' +
      '<div class="pet-title"><span>로코 <span class="pet-role">· 현장 관찰 동료</span></span>' +
      '<button type="button" class="pet-close" data-action="close" aria-label="로코 말풍선 접기">×</button></div>' +
      '<p class="pet-copy" role="status" aria-live="polite"></p>' +
      '<button type="button" class="pet-cta" data-action="cta"></button></div>' +
      '<button type="button" class="pet-character" data-action="toggle" title="로코와 이야기하기 · 끌어서 이동" aria-label="로코 안내 열기 또는 이동" aria-expanded="' + String(this.state.open) + '">' +
      this.mascot(quiet && !this.state.open) + '</button>';

    this.shell.querySelector('.pet-copy').textContent = this.state.tip || guide.message;
    this.shell.querySelector('.pet-cta').textContent = guide.cta + '  →';
    const close = this.shell.querySelector('[data-action="close"]');
    close.addEventListener('click', () => {
      this.state.open = false;
      this.state.dismissedPage = this.page;
      this.render();
    });
    this.shell.querySelector('[data-action="toggle"]').addEventListener('click', () => {
      if (this.state.skipClick) {
        this.state.skipClick = false;
        return;
      }
      this.state.open = !this.state.open;
      this.state.dismissedPage = null;
      this.render();
    });
    this.shell.querySelector('[data-action="cta"]').addEventListener('click', () => this.runAction(guide.action));
    this.bindQuestions(guide);
    this.bindDrag();
    this.applyPosition();
  }

  bindQuestions(guide) {
    if (!this.state.open) return;
    const options = document.createElement('div');
    options.className = 'pet-options';
    const questions = [
      ['missing', '왜 빈칸인가요?'],
      ['time', '사진으로 시간 계산?'],
      ['review', '검토 완료란?']
    ];
    questions.forEach((item) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = item[1];
      button.addEventListener('click', () => {
        this.state.tip = PET_ANSWERS[item[0]];
        this.render();
      });
      options.appendChild(button);
    });
    const disclaimer = document.createElement('div');
    disclaimer.className = 'pet-disclaimer';
    disclaimer.textContent = '문서 기반 고정 안내 · LLM 대화/자동 판정 아님';
    const bubble = this.shell.querySelector('.pet-bubble');
    bubble.appendChild(options);
    bubble.appendChild(disclaimer);
  }

  runAction(action) {
    const sourcePage = this.page;
    if (action === 'quiet') {
      this.state.open = false;
      this.mode = this.mode === 'quiet' ? 'normal' : 'quiet';
    }
    if (/^S\d+$/.test(action)) this.page = action;
    this.emit('loco-guide-action', { page: sourcePage, nextPage: this.page, action: action });
  }

  bindDrag() {
    const handle = this.shell.querySelector('.pet-character');
    handle.addEventListener('pointerdown', (event) => {
      const rect = this.getBoundingClientRect();
      this.state.drag = { x: event.clientX, y: event.clientY, left: rect.left, top: rect.top, moved: false };
      handle.setPointerCapture(event.pointerId);
    });
    handle.addEventListener('pointermove', (event) => {
      if (!this.state.drag) return;
      const drag = this.state.drag;
      const dx = event.clientX - drag.x;
      const dy = event.clientY - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 5) {
        drag.moved = true;
        const x = Math.max(4, Math.min(window.innerWidth - this.offsetWidth - 4, drag.left + dx));
        const y = Math.max(4, Math.min(window.innerHeight - this.offsetHeight - 4, drag.top + dy));
        this.state.position = { x: x, y: y };
        this.applyPosition();
      }
    });
    const finish = () => {
      if (this.state.drag && this.state.drag.moved) {
        this.state.skipClick = true;
        window.setTimeout(() => { this.state.skipClick = false; }, 100);
      }
      this.state.drag = null;
    };
    handle.addEventListener('pointerup', finish);
    handle.addEventListener('pointercancel', finish);
  }

  applyPosition() {
    if (this.state.position) {
      this.style.left = this.state.position.x + 'px';
      this.style.top = this.state.position.y + 'px';
      this.style.right = 'auto';
      this.style.bottom = 'auto';
    } else {
      this.style.left = '';
      this.style.top = '';
      this.style.right = '';
      this.style.bottom = '';
    }
  }

  onKeyDown(event) {
    if (event.key !== 'Escape' || !this.state.open) return;
    const overlay = document.querySelector('#overlay-root');
    if (overlay && overlay.children.length) return;
    this.state.open = false;
    this.state.dismissedPage = this.page;
    this.render();
  }

  onFocusIn(event) {
    const target = event.target;
    if (target && typeof target.matches === 'function' &&
        target.matches('#main-content input,#main-content textarea,#main-content select')) {
      this.state.dismissedPage = this.page;
      this.state.open = false;
      this.render();
    }
  }

  onResize() {
    if (!this.state.position) return;
    this.state.position = null;
    this.applyPosition();
    this.render();
  }
}

if (!customElements.get('loco-guide')) customElements.define('loco-guide', LocoGuide);
