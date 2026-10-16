export const events={
click(event) {
    if(event.target.closest('[data-add-response]')){
      const response=this.captureResponse();
      if(!response.response_code){response.response_code=`익명-${String(this.responses.length+1).padStart(3,'0')}`;this.set('response_code',response.response_code);}
      if(this.responses.some(item=>item.response_code===response.response_code)){this.onChanged(new Error('응답 코드가 중복됩니다. 다른 익명 코드를 사용해 주세요.'));return;}
      this.responses.push(response);this.renderResponses();this.clearResponseForm();this.onChanged();
    } else {
      const button=event.target.closest('[data-remove-response]');if(button){this.responses.splice(Number(button.dataset.removeResponse),1);this.renderResponses();this.onChanged();}
    }
  }
};
