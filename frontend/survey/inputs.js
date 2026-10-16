export const inputs={
get(name) { return this.host.querySelector(`[data-intake="${name}"]`); },
set(name, value) { const node=this.get(name); if(node)node.value=value??''; },
fill(data={}) {
    const situation={equipment_status:'UNKNOWN',equipment_notes:'',workload_status:'UNKNOWN',workload_notes:'',speed_status:'UNKNOWN',speed_notes:'',work_pattern_status:'UNKNOWN',work_pattern_notes:'',...(data.workplace_situation||{})};
    const participation={status:'UNKNOWN',role:'UNKNOWN',participant_code:'',method:'UNKNOWN',date:null,notes:'',...(data.participation||{})};
    const symptom={method:'UNKNOWN',date:null,respondent_count:null,summary:'',responses:[],...(data.symptom_survey||{})};
    this.set('occasional_cause',data.occasional_cause);
    this.set('previous_survey_date',data.previous_survey_date);
    for(const key of ['equipment_status','equipment_notes','workload_status','workload_notes','speed_status','speed_notes','work_pattern_status','work_pattern_notes'])this.set(key,situation[key]);
    this.set('participation_status',participation.status);this.set('participation_role',participation.role);this.set('participant_code',participation.participant_code);this.set('participation_method',participation.method);this.set('participation_date',participation.date);this.set('participation_notes',participation.notes);
    this.set('symptom_method',symptom.method);this.set('symptom_date',symptom.date);this.set('symptom_respondent_count',symptom.respondent_count);this.set('symptom_summary',symptom.summary);
    this.responses=structuredClone(symptom.responses||[]);this.renderResponses();
    this.clearResponseForm();
  },
collect(values=Object.fromEntries(new FormData(this.form))) {
    values={...values};for(const node of this.host.querySelectorAll('[data-intake]'))values[node.dataset.intake]=node.value;
    const situation={};for(const key of ['equipment_status','equipment_notes','workload_status','workload_notes','speed_status','speed_notes','work_pattern_status','work_pattern_notes'])situation[key]=values[key]||'';
    for(const key of ['equipment_status','workload_status','speed_status','work_pattern_status'])situation[key]=situation[key]||'UNKNOWN';
    const participant={status:values.participation_status||'UNKNOWN',role:values.participation_role||'UNKNOWN',participant_code:values.participant_code||'',method:values.participation_method||'UNKNOWN',date:values.participation_date||null,notes:values.participation_notes||''};
    const rawCount=values.symptom_respondent_count;
    return {occasional_cause:values.occasional_cause||null,previous_survey_date:values.previous_survey_date||null,workplace_situation:situation,participation:participant,symptom_survey:{method:values.symptom_method||'UNKNOWN',date:values.symptom_date||null,respondent_count:rawCount===''||rawCount===undefined?(this.responses.length||null):Number(rawCount),summary:values.symptom_summary||'',responses:structuredClone(this.responses)}};
  },
captureResponse() {
    const val=name=>this.get(name)?.value??'';
    const numeric=name=>val(name)===''?null:Number(val(name));
    const response={response_code:val('response_code').trim(),name:val('response_name').trim(),age_years:numeric('response_age'),sex:val('response_sex')||'UNKNOWN',workplace_tenure_months:numeric('response_tenure'),department:val('response_department').trim(),job:val('response_job').trim(),current_work:val('response_current_work').trim(),current_work_months:numeric('response_current_months'),daily_work_hours:numeric('response_daily_hours'),rest_breaks:val('response_rest_breaks').trim(),previous_work:val('response_previous_work').trim(),previous_work_months:numeric('response_previous_months'),leisure_activities:val('response_leisure').trim(),household_work:val('response_household')||'UNKNOWN',medical_history:val('response_medical')||'UNKNOWN',injury_history:val('response_injury')||'UNKNOWN',injury_sites:val('response_injury_sites').split(/[，,、]/).map(x=>x.trim()).filter(Boolean).map(x=>({'목':'neck','어깨':'shoulder','팔':'arm_elbow','팔꿈치':'arm_elbow','손':'hand_wrist','손목':'hand_wrist','허리':'back','다리':'leg_foot','발':'leg_foot'}[x])).filter(Boolean),physical_burden:numeric('response_burden'),work_related_symptoms_last_year:val('response_work_related')||'UNKNOWN',regions:{}};
    for(const site of ['neck','shoulder','arm_elbow','hand_wrist','back','leg_foot'])response.regions[site]={side:val(`region-${site}-side`)||'UNKNOWN',duration:val(`region-${site}-duration`)||'UNKNOWN',severity:val(`region-${site}-severity`)||'UNKNOWN',last_week:val(`region-${site}-last_week`)||'UNKNOWN'};
    return response;
  },
clearResponseForm() {
    const codes=this.responses.map(x=>x.response_code);let index=this.responses.length+1;let code;
    do{code=`익명-${String(index++).padStart(3,'0')}`}while(codes.includes(code));
    for(const name of ['response_name','response_age','response_tenure','response_department','response_job','response_current_work','response_current_months','response_daily_hours','response_rest_breaks','response_previous_work','response_previous_months','response_leisure','response_injury_sites'])this.set(name,'');
    this.set('response_code',code);this.set('response_sex','UNKNOWN');this.set('response_household','UNKNOWN');this.set('response_medical','UNKNOWN');this.set('response_injury','UNKNOWN');this.set('response_burden','');this.set('response_work_related','UNKNOWN');
    for(const site of ['neck','shoulder','arm_elbow','hand_wrist','back','leg_foot'])for(const key of ['side','duration','severity','last_week'])this.set(`region-${site}-${key}`,key==='side'?'UNKNOWN':key==='last_week'?'UNKNOWN':'UNKNOWN');
  }
};
