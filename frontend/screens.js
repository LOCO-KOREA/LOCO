// Screen IDs are the public navigation contract in docs/화면설계서.md (2.0).
export const SCREENS = [
  {id:'S01', name:'대시보드', view:'dashboard', description:'저장된 조사를 열고 작업 기록을 이어갑니다.'},
  {id:'S02', name:'조사 목록·생성', view:'survey', description:'조사 개요를 기록합니다.'},
  {id:'S03', name:'작업 목록·개요', view:'task', editor:'info', description:'작업 개요를 기록하고 입력할 기준을 선택합니다.'},
  {id:'S04', name:'작업 조건·11개 기준', view:'task', editor:'conditions', description:'관찰·면담으로 확인한 하루 시간·중량·힘·횟수를 입력합니다.'},
  {id:'S05', name:'사진 등록·배정', view:'photo', description:'사진을 등록하고 분석할 사진과 확인한 관찰값을 고릅니다.'},
  {id:'S06', name:'자세 결과·REBA', view:'analysis', description:'사진에서 읽은 자세와 점수, 직접 확인한 값을 살펴봅니다.'},
  {id:'S07', name:'조사자 검토·결과 설명', view:'analysis', description:'11개 기준의 계산 결과와 조사자 결론·설명을 확인합니다.'},
  {id:'S08', name:'Excel 저장·전후 비교', view:'analysis', description:'결과를 확인하고 Excel에 담을 내용을 선택합니다.'},
  {id:'S09', name:'분석 상태', view:'analysis', description:'사진 처리 상태와 분석 결과를 확인합니다.'},
  {id:'S10', name:'설정', view:'analysis', navigation:false, description:'모델·규칙 버전과 GPT·로코 안내 설정을 확인합니다.'}
];
export const SCREEN_INFO = Object.fromEntries(SCREENS.map(s=>[s.id,[s.name,s.id,s.description]]));
export const isAnalysisScreen = id => SCREENS.some(s=>s.id===id && s.view==='analysis');
export const WORKFLOW = SCREENS.filter(s=>['S03','S04','S05','S06','S07','S08'].includes(s.id));
