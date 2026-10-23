"""Verify copied source evidence and numeric units; never infer task facts."""
import math
import re

NUMBER_WORDS = {'한':1,'하나':1,'두':2,'둘':2,'세':3,'셋':3,'네':4,'넷':4,'다섯':5,'여섯':6,'일곱':7,'여덟':8,'아홉':9,'열':10,'스무':20}
NUMBER = r'(\d+(?:\.\d+)?|스무|여덟|일곱|여섯|다섯|아홉|하나|둘|셋|넷|한|두|세|네|열)'
DURATION_SUM='SUM_STATED_DURATIONS'
CONVERT_DURATION='NORMALIZE_STATED_DURATION'
MAX_DURATION_TERMS=64
MINUTES={'시간':60,'분':1,'초':1/60}
SINO_DIGITS={char:value for value,char in enumerate('영일이삼사오육칠팔구')}
SINO_DIGITS['공']=0
SINO_SCALES={'십':10,'백':100,'천':1000}
NATIVE_TENS={'열':10,'스물':20,'서른':30,'마흔':40,'쉰':50,'예순':60,'일흔':70,'여든':80,'아흔':90}
TIME_WORDS=dict(NUMBER_WORDS)
for prefix,base in NATIVE_TENS.items():
    TIME_WORDS[prefix]=base
    for word,value in NUMBER_WORDS.items():
        if value<10:TIME_WORDS[prefix+word]=base+value
TIME_NUMBER=r'(?:\d+(?:\.\d+)?|'+ '|'.join(sorted(TIME_WORDS,key=len,reverse=True))+r'|[영공일이삼사오육칠팔구십백천]+)'
# A half-hour token may have Korean duration qualifiers, particles and endings.
# Require the end of that whole token, so 반복 and 반도체 are not half-hours.
HALF_QUALIFIERS=('정도','가량','동안','이상','이하','이내')
HALF_PARTICLES=('은','을','이','도','만','과','하고','으로','까지','부터','이나','쯤','씩')
HALF_ENDINGS=('이에요','예요','입니다','이었어요','이고','이지만','인데','이니까','이라서','이라고','이면','이요','요')
HALF_DURATION=(r'반(?:'+ '|'.join(HALF_QUALIFIERS)+r')?(?:'+ '|'.join(HALF_PARTICLES)+r')?(?:'+
               '|'.join(HALF_ENDINGS)+r')?(?![가-힣\w])')
DURATION=re.compile(r'(?<![\d.])('+TIME_NUMBER+r')\s*(시간|분|초)(?:\s*('+HALF_DURATION+r'))?')
EVIDENCE_POLICY=dict(min_joined_sentences=2, sentence_end=r'(?<!\d)\.|\.(?!\d)|[!?。]')
SENTENCE_END=re.compile(EVIDENCE_POLICY['sentence_end'])
# These expressions do not establish disjoint daily working periods.
AMBIGUOUS_SUM=re.compile(r'동시|겹|중복|그중|중에서|중에|포함|휴게|휴식|점심|쉬는|제외|빼고|뺀|또는|혹은|둘\s*중|두\s*작업\s*중|[~～∼]|에서.{0,8}까지|주당|매주|일주일|매월|월당|시간당|분당|매시간|매분|분에|시간에|하루.{0,5}(?:일부|중)|더\s*있|일부\s*작업|그\s*외|나머지\s*작업')
# Negation changes the meaning of overlap. Remove only its local negative phrase,
# so a second positive overlap, break, inclusion or unknown period still rejects a sum.
NEGATED_OVERLAP=re.compile(r'(?:겹치지|중복되지|동시에\s*(?:작업|일|수행)?하지)\s*않|(?:겹침|중복|동시\s*작업)(?:이|은|는|도)?\s*없')
# A labelled numeric total is not another operand. A heading such as
# "총 작업은 팔 들기 2시간 ..." does not label that work period as the total.
TOTAL_PREFIX=re.compile(r'(?:총|전체|합계|합쳐|합하면)(?:\s|하루|작업|시간|실제|은|는|이|가|:|=|으로|해서)*$')


def _compact(text):
    return re.sub(r'\s+','',text)


def _sentences(text):
    """Retain actual source offsets and punctuation, including the final sentence."""
    start=0
    for match in SENTENCE_END.finditer(text):
        end=match.end()
        while start<end and text[start].isspace():start+=1
        if start<end:yield start,end,_compact(text[start:end])
        start=end
    while start<len(text) and text[start].isspace():start+=1
    end=len(text.rstrip())
    if start<end:yield start,end,_compact(text[start:end])


def evidence_quote(quote,source):
    """Resolve copied sentences to one real source span, without rewriting claims.

    Exact contiguous excerpts retain their existing spelling. A joined excerpt
    must copy whole source sentences, in order and from distinct occurrences in
    one message. Its stored evidence includes all intervening source context.
    """
    if not isinstance(quote,str) or not quote.strip() or not isinstance(source,str):return None
    if _compact(quote) in _compact(source):return quote
    pieces=list(_sentences(quote))
    if len(pieces)<EVIDENCE_POLICY['min_joined_sentences']:return None
    sentences=list(_sentences(source));cursor=0;matched=[]
    for _,_,piece in pieces:
        index=next((index for index in range(cursor,len(sentences)) if sentences[index][2]==piece),None)
        if index is None:return None
        matched.append(sentences[index]);cursor=index+1
    return source[matched[0][0]:matched[-1][1]]


def _number(word):
    if word in TIME_WORDS:return TIME_WORDS[word]
    if re.fullmatch(r'\d+(?:\.\d+)?',word):return float(word)
    total=0;digit=None;last_scale=math.inf
    for char in word:
        if char in SINO_DIGITS:
            if digit is not None:raise ValueError('ambiguous number')
            digit=SINO_DIGITS[char]
        else:
            scale=SINO_SCALES[char]
            if scale>=last_scale:raise ValueError('invalid number order')
            total+=(1 if digit is None else digit)*scale;digit=None;last_scale=scale
    return total+(digit or 0)


def _durations(text,*,strict=True):
    """Lex quantities and compound units; never determine task meaning from words."""
    terms=[];last_scale=None
    for match in DURATION.finditer(text):
        word,unit,half=match.groups();scale=MINUTES[unit]
        valid=not (half and unit!='시간' or re.search(r'[-−~～∼]\s*$',text[:match.start()]))
        try:minutes=_number(word)*scale+(30 if half else 0)
        except (KeyError,ValueError):minutes=0;valid=False
        valid=bool(valid and math.isfinite(minutes))
        if strict and not valid:return None
        if terms and not text[terms[-1]['end']:match.start()].strip() and scale<last_scale:
            terms[-1].update(minutes=terms[-1]['minutes']+minutes,end=match.end())
            terms[-1]['quote']=text[terms[-1]['start']:match.end()]
            terms[-1]['components']+=1
            terms[-1]['valid']=terms[-1]['valid'] and valid
        else:
            terms.append(dict(minutes=minutes,quote=match.group(),start=match.start(),end=match.end(),components=1,valid=valid))
        last_scale=scale
    return terms


def _compact_durations(text,*,strict=True):
    """Keep lexical word boundaries when comparing whitespace-free offsets."""
    groups=_durations(text,strict=strict)
    if groups is None:return None
    offsets=[0]
    for char in text:offsets.append(offsets[-1]+(not char.isspace()))
    return [dict(group,start=offsets[group['start']],end=offsets[group['end']]) for group in groups]


def _whole_quantity_quote(quote,source):
    """An excerpt may not split '1시간 30분' into an independent 30-minute claim."""
    needle=_compact(quote);haystack=_compact(source)
    groups=_compact_durations(source,strict=False)
    if not needle or groups is None:return False
    start=haystack.find(needle)
    while start>=0:
        end=start+len(needle)
        intersect=[group for group in groups if group['start']<end and group['end']>start]
        numeric=re.fullmatch(r'\d+(?:\.\d+)?',needle)
        partial_number=numeric and (start>0 and haystack[start-1] in '0123456789.' or end<len(haystack) and haystack[end] in '0123456789.')
        if not partial_number and all(group['valid'] and start<=group['start'] and group['end']<=end for group in intersect):return True
        start=haystack.find(needle,start+1)
    return False


def _operand_duration(text):
    """A copied '2시간(120분)' is one operand only if both units agree."""
    groups=_durations(text)
    if not groups:return None
    annotations=set()
    for match in re.finditer(r'\([^()]*\)',text):
        children=[index for index,group in enumerate(groups) if match.start()<group['start'] and group['end']<match.end()]
        if not children:continue
        if len(children)!=1:return None
        index=children[0];child=groups[index]
        if _compact(match.group()[1:-1])!=_compact(child['quote']):return None
        prior=next((group for group in reversed(groups[:index]) if group['end']<=match.start()),None)
        if not prior or text[prior['end']:match.start()].strip() or not math.isclose(prior['minutes'],child['minutes'],abs_tol=1e-6):return None
        annotations.add(index)
    values=[group for index,group in enumerate(groups) if index not in annotations]
    return values[0] if len(values)==1 else None


def calculation_schema(operations):
    term=dict(type='object',additionalProperties=False,required=['quote','minutes'],
              properties=dict(quote=dict(type='string'),minutes=dict(type='number')))
    return dict(anyOf=[dict(type='null'),dict(type='object',additionalProperties=False,
        required=['operation','terms'],properties=dict(operation=dict(type='string',enum=list(operations)),
        terms=dict(type='array',items=term,minItems=2,maxItems=MAX_DURATION_TERMS)))])


def number_grounded(value, quote, unit, *, bare=False):
    def number(s): return NUMBER_WORDS[s] if s in NUMBER_WORDS else float(s)
    text = re.sub(r'\s+', '', quote).lower()
    minute_rate=bool(re.search(r'분당|매분|(?<![\d.])(?:1|한)?분에|/분',text))
    hour_rate=bool(re.search(r'시간당|매시간|(?<![\d.])(?:1|한)?시간에|/시간',text))
    day_rate=bool(re.search(r'하루|일일|일당|/일',text))
    if unit=='회/분' and not minute_rate and not bare: return False
    if unit=='회/시간' and not hour_rate and not bare: return False
    if unit=='회/일' and (minute_rate or hour_rate): return False
    if unit=='일' and re.search(r'주당|매주|주\d|월당|매월',text): return False
    if unit.startswith('분'):
        groups=_durations(quote)
        return bool(groups is not None and any(math.isclose(value,group['minutes'],abs_tol=1e-6) for group in groups)) or bool(
            bare and re.fullmatch(r'\d+(?:\.\d+)?',text) and math.isclose(value,float(text)))
    units = {'kg': [('kg',1),('킬로그램',1),('킬로',1),('g',.001)],
             'kg 상당': [('kg',1),('킬로',1)], '분': [('시간',60),('분',1),('초',1/60)],
             '일': [('일',1)], '회/일': [('번',1),('회',1)], '회/시간': [('번',1),('회',1)],
             '회/분': [('번',1),('회',1)],'개월':[('개월',1),('달',1)]}
    choices = units.get(unit, units['분'] if unit.startswith('분') else [])
    for suffix, scale in choices:
        for match in re.finditer(NUMBER + re.escape(suffix), text):
            observed = number(match.group(1))*scale
            if suffix=='시간' and text[match.end():].startswith('반'): observed += 30
            if math.isclose(value, observed, abs_tol=1e-6): return True
    return bool(bare and re.fullmatch(r'\d+(?:\.\d+)?',text) and math.isclose(value,float(text)))


def stated_duration_sum(quote,context,calculation=None):
    """Verify operands supplied by AI, or read a simple legacy list of durations."""
    if AMBIGUOUS_SUM.search(NEGATED_OVERLAP.sub('',context)) or re.search(r'[-−]\s*'+NUMBER,quote):return None
    groups=_durations(quote)
    if groups is None:return None
    if calculation is None:
        if '(' in quote or ')' in quote:return None  # May repeat a unit or a subtotal.
        if any(TOTAL_PREFIX.search(quote[:group['start']]) for group in groups):return None
        terms=[dict(minutes=group['minutes'],quote=group['quote']) for group in groups]
    else:
        if not isinstance(calculation,dict) or set(calculation)!={'operation','terms'} or calculation['operation']!=DURATION_SUM:return None
        proposed=calculation['terms']
        if not isinstance(proposed,list) or not 2<=len(proposed)<=MAX_DURATION_TERMS:return None
        terms=[];cursor=0;source=_compact(quote)
        for term in proposed:
            if not isinstance(term,dict) or set(term)!={'quote','minutes'}:return None
            raw=term['quote'];minutes=term['minutes']
            if not isinstance(raw,str) or not raw.strip() or type(minutes) not in (int,float) or not math.isfinite(minutes) or minutes<0:return None
            start=source.find(_compact(raw),cursor)
            if start<0 or not _whole_quantity_quote(raw,quote):return None
            end=start+len(_compact(raw))
            # Validate this occurrence, not another identical duration elsewhere.
            source_groups=_compact_durations(quote)
            related=[group for group in source_groups if group['start']<end and group['end']>start]
            if not related or not all(start<=group['start'] and group['end']<=end for group in related):return None
            if TOTAL_PREFIX.search(source[:related[0]['start']]):return None
            parsed=_operand_duration(raw)
            if parsed is None or not math.isclose(minutes,parsed['minutes'],abs_tol=1e-6):return None
            terms.append(dict(minutes=parsed['minutes'],quote=raw));cursor=end
    if not 2<=len(terms)<=MAX_DURATION_TERMS:return None
    return dict(operation=DURATION_SUM,unit='분',terms=terms,value=sum(t['minutes'] for t in terms))


def number_proof(field,value,quote,*,bare=False,context='',source=None,calculation=None):
    if not isinstance(quote,str) or type(value) not in (int,float) or not math.isfinite(value):return None
    is_duration=field['unit'].startswith('분')
    original=source if source is not None else context or quote
    copied=evidence_quote(quote,original)
    excerpts=[quote] if _compact(quote) in _compact(original) else [quote[start:end] for start,end,_ in _sentences(quote)]
    if is_duration and (copied is None or not all(_whole_quantity_quote(excerpt,original) for excerpt in excerpts)):return None
    allowed=DURATION_SUM in field.get('derivations',[])
    if calculation is not None:
        if not allowed:return None
        proof=stated_duration_sum(quote,context,calculation)
        return proof if proof is not None and math.isclose(value,proof['value'],abs_tol=1e-6) else None
    if allowed:
        groups=_durations(quote)
        if groups is None:return None
        if len(groups)>1:
            proof=stated_duration_sum(quote,context)
            return proof if proof is not None and math.isclose(value,proof['value'],abs_tol=1e-6) else None
        if len(groups)==1 and groups[0]['components']>1 and math.isclose(value,groups[0]['minutes'],abs_tol=1e-6):
            return dict(operation=CONVERT_DURATION,unit='분',terms=[dict(minutes=value,quote=groups[0]['quote'])],value=value)
    if number_grounded(value,quote,field['unit'],bare=bare):return dict(quote=quote)
    return None
