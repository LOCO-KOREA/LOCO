export const inputs={
get(name) { return this.host.querySelector(`[data-intake="${name}"]`); },
set(name, value) { const node=this.get(name); if(node)node.value=value??''; },
fill(data={}) { this.set('previous_survey_date',data.previous_survey_date); },
collect(values=Object.fromEntries(new FormData(this.form))) {
    values={...values};for(const node of this.host.querySelectorAll('[data-intake]'))values[node.dataset.intake]=node.value;
    return {previous_survey_date:values.previous_survey_date||null};
  }
};
