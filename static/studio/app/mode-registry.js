const modes = new Map();
let imageAssetsEnabled = false;
let assemblyEnabled = false;
let creationEnabled = false;
export function setCreationEnabled(value){creationEnabled=value===1;}
export function setAssemblyEnabled(value){assemblyEnabled=value===1;}
export function setImageAssetsEnabled(value) { imageAssetsEnabled = Boolean(value); }
export function registerMode(definition) {
  if (!definition.id || !definition.load || modes.has(definition.id))
    throw new Error("模式注册无效或重复");
  modes.set(definition.id, Object.freeze(definition));
}
export const listModes = () => [...modes.values()].filter(m => (m.id !== 'image_assets' || imageAssetsEnabled) && (m.id !== 'video_assembly' || assemblyEnabled) && (!['authoring','movie'].includes(m.id) || creationEnabled));
export const getMode = (id) => modes.get(id);
registerMode({
  id: "swap",
  name: "参考视频换人",
  code: "RV2V",
  art: "mode-rv2v.webp",
  description: "沿用表演与镜头，让你的角色走进画面。",
  entry: "源视频与角色",
  load: () => import("../modes/swap/workspace.js"),
});
registerMode({
  id: "image_story",
  name: "参考图长视频",
  code: "R2V",
  art: "mode-r2v.webp",
  description: "从角色、场景和色彩出发，铺开你的片段。",
  entry: "角色与片段",
  load: () => import("../modes/image-story/workspace.js"),
});
registerMode({
  id: "text_story",
  name: "文生视频",
  code: "T2V",
  art: "mode-t2v.webp",
  description: "写下镜头与声音，让一段文字成为长片。",
  entry: "剧本与镜头",
  load: () => import("../modes/text-story/workspace.js"),
});
registerMode({id:'image_assets',kind:'image',name:'图片资产创作',code:'IMAGE',art:'mode-image-assets.webp',description:'编辑角色、服装与场景，让每张图片成为可复用的创作资产。',entry:'图片创作',load:()=>import('./image-workspace-controller.js')});

registerMode({id:'video_assembly',kind:'assembly',name:'视频接续',code:'JOIN',art:'mode-video-continuation.webp',description:'把已有片段串成作品，沿视频末尾继续生长。',entry:'视频与排序',load:()=>import('../modes/video-assembly/workspace.js')});
registerMode({id:'authoring',kind:'authoring',name:'剧本创作',code:'SCRIPT',art:'mode-authoring.webp',description:'从故事与参考出发，写成剧本，整理分镜与片段提示词。',entry:'故事起点',load:()=>import('../modes/authoring/workspace.js')});
registerMode({id:'movie',kind:'movie',name:'电影创作',code:'FILM',art:'mode-movie.webp',description:'把准备好的剧本逐段拍出来，在时间轴上组织成片。',entry:'片段生成',load:()=>import('../modes/movie/workspace.js')});
