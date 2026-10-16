export function createAnalysisState(){
 return {page:'S01',surveys:[],survey:null,tasks:[],bundle:null,analysis:null,selectedAnalysis:null,aiTextId:null,history:[],settings:null,slot:1,previews:new Map(),selectedSlots:new Set(),poll:null,overview:null,exportSelections:{},comparisonPool:[],comparisonBefore:null,comparisonAfter:null,comparisonNote:'',viewEpoch:0,aiEpoch:0,editEpoch:0,analysisIntent:0,readSequence:0,exportSequence:0,pollOwner:null,pendingWrites:new Map(),runningJobs:new Map(),modalContext:null,pendingSelection:null};
}
