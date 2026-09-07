const modes = new Map();
let imageAssetsEnabled = false;
export function setImageAssetsEnabled(value) { imageAssetsEnabled = Boolean(value); }
export function registerMode(definition) {
  if (!definition.id || !definition.load || modes.has(definition.id))
    throw new Error("模式注册无效或重复");
  modes.set(definition.id, Object.freeze(definition));
}
export const listModes = () => [...modes.values()].filter(m => m.id !== 'image_assets' || imageAssetsEnabled);
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
