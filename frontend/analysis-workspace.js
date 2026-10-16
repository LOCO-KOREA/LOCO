/* Compose per-workspace state, views, actions and navigation without global screen state. */
import * as labels from './analysis/labels.js';
import {LocoReview} from './review-links.js';
import {createAnalysisState} from './analysis/state.js';
import {createUi} from './analysis/ui.js';
import {createRebaView} from './analysis/reba-view.js';
import {createProgressView} from './analysis/progress-view.js';
import {createCriteriaView} from './analysis/criteria-view.js';
import {createExplanationView} from './analysis/explanation-view.js';
import {createExportView} from './analysis/export-view.js';
import {createSettingsView} from './analysis/settings-view.js';
import {createPhotoCanvas} from './analysis/photo-canvas.js';
import {createActions} from './analysis/actions.js';
import {createController} from './analysis/controller.js';

export function createAnalysisWorkspace(host){
 host.element.innerHTML='<div id="content"></div><div id="overlay-root"></div>';
 const ctx={host,s:createAnalysisState(),LocoReview,...labels};
 Object.assign(ctx,createUi(ctx));
 Object.assign(ctx,createRebaView(ctx));
 Object.assign(ctx,createProgressView(ctx));
 Object.assign(ctx,createCriteriaView(ctx));
 Object.assign(ctx,createExplanationView(ctx));
 Object.assign(ctx,createExportView(ctx));
 Object.assign(ctx,createSettingsView(ctx));
 Object.assign(ctx,createPhotoCanvas(ctx));
 Object.assign(ctx,createActions(ctx));
 return createController(ctx);
}
