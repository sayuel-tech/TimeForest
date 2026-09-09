import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
export function validateDesign(read,cssFiles){
 const errors=[],entry=read('static/studio/style.css'),tokens=read('static/studio/styles/design-tokens.css');
 const require=(ok,message)=>{if(!ok)errors.push(message);};
 require(entry.indexOf('styles/design-tokens.css')>=0&&entry.indexOf('styles/design-tokens.css')<entry.indexOf('styles/base.css'),'公共尺寸必须在基础样式之前加载');
 require(entry.includes('styles/task-layouts.css'),'缺少任务布局与阅读角色公共层');
 const names=['title-page','title-dialog','title-section','title-card','text-body','text-control','text-meta','text-reading','text-summary','leading-reading','reading-width','control-height','control-compact','panel-padding','dialog-padding','layout-gap','page-gutter','nav-width'];
 for(const name of names)require(tokens.includes('--'+name+':'),'缺少公共尺寸 '+name);
 for(const file of cssFiles){if(file.endsWith('/design-tokens.css'))continue;const css=read(file);for(const name of names)require(!new RegExp('--'+name+'\\s*:').test(css),file+' 重定义公共尺寸 '+name);}
 for(const [file,token] of [['base.css','title-page'],['components.css','control-height'],['components.css','title-dialog'],['production-settings.css','title-dialog'],['workbench.css','title-page'],['collection-navigation.css','title-page']])require(read('static/studio/styles/'+file).includes('var(--'+token+')'),file+' 未消费公共尺寸 '+token);
 return errors;
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const dir='static/studio/styles',files=fs.readdirSync(path.join(root,dir)).filter(f=>f.endsWith('.css')).map(f=>dir+'/'+f);
 const errors=validateDesign(file=>fs.readFileSync(path.join(root,file),'utf8'),files);
 if(errors.length){console.error(errors.join('\n'));process.exitCode=1;}else console.log('公共视觉尺寸检查通过；页面布局与截图仍须核对。');
}
