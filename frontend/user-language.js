// The same dictionary is used for AI prose, screen labels and exported explanations.
import terms from './user-language.json' with {type:'json'};
const tokens = Object.keys(terms).sort((a,b)=>b.length-a.length).join('|');
const pattern = new RegExp(`(?<![A-Za-z0-9_])(${tokens})(?![A-Za-z0-9_])`, 'g');
export function userText(value) {
  return typeof value === 'string' ? value.replace(pattern, token=>terms[token]) : value;
}
