import {api} from '../../core/api-client.js';
export const promptApi=(path='',method='GET',body,signal)=>api('/prompt-library'+path,method,body,signal);
export async function promptCatalog(signal){
  let c;
  try{c=await promptApi('/catalog','GET',undefined,signal);}
  catch(error){if(error.status===404)error.message='当前后台未加载提示词库，请在任务结束后重启导演台并刷新。';throw error;}
  if(c.prompt_library_version!==1)throw new Error('当前后台未加载提示词库，请在任务结束后重启导演台并刷新。');
  return c;
}
