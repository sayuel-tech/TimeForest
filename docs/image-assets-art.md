# 图片资产创作：美术资源

更新日期：2026-09-07。使用内置 imagegen，以原站 mode-r2v.webp 和 mode-t2v.webp 为风格参考，生成三张配套插画。暖象牙纸、水彩与细墨线、森林灰绿和烟蓝、柔和拼贴边缘；文字由网页渲染。

| 资源 | 页面用途 |
|---|---|
| static/assets/modes/mode-image-assets.webp | 首页第四个创作模式入口 |
| static/assets/image-studio/empty-editor.webp | 图片尚未上传时的编辑画布 |
| static/assets/image-studio/empty-results.webp | 生成与挑选、保存与使用步骤暂无候选时 |

原始 PNG 保留在 <本地用户目录>。生产资源为 WebP，保持原尺寸和构图，仅转换网页编码；网站不依赖生成缓存。旧 SVG 已归档至 <本地维护归档>。

插画仅用于入口和空状态，上传图片后沿用原画布。空状态采用紧凑排版；装饰图 alt 为空，说明文字保留为可访问文本。

## 生成提示词：入口插画

Use case: stylized-concept, finished website illustration asset.
Reference image 1 and reference image 2 are STYLE REFERENCES ONLY from the existing website. Create one new companion illustration, not a UI mockup. Match their aged warm ivory watercolor paper, finely textured natural pigment, muted forest green and smoky blue-gray, restrained sepia, ink detail, delicate torn-paper collage edges and atmospheric realism. Match their soft quiet cinematic editorial character and similar visual weight.
Subject: image asset creation in a woodland film studio. An elegant arrangement of three overlapping handmade picture studies: a full-length character in an olive cloak, a separate carefully painted garment study on paper, and a woodland landscape study. A small artist brush and a few fine botanical twigs visually connect these editable visual assets. This should communicate crafting character, wardrobe and scenery images, with a cohesive natural hand-painted composition. Detailed painterly images, not geometric flat vector icons. No camera as the main subject.
Layout: landscape 3:2, intended displayed at 600x400. Central composition occupying about 75% of canvas, all objects inside safe margins, soft pigment fades into warm ivory paper at perimeter. Balanced contrast similar to supplied art. No labels, lettering, logos, watermarks, interface, buttons or frame around whole image. Generate a single polished raster illustration.

## 生成提示词：编辑空状态

Use case: stylized-concept, website empty-state illustration, one single landscape 3:2 raster asset.
Images 1 and 2 are STYLE REFERENCES ONLY from the existing website. Match their warm ivory aged watercolor paper, atmospheric forest green, subtle gray-blue, sepia, fine ink-and-watercolor pigment and soft organically faded edges. Quiet, handcrafted cinematic editorial look. No flat vector design or saturated color.
Subject: an inviting small artist's workspace waiting for its first image: one mostly blank ivory deckle-edged drawing sheet resting on two thin papers, a fine wooden paintbrush laid beside it, and a tiny restrained sprig of fern. A very faint woodland watercolor wash only at one corner of the sheet suggests creative possibility, while the sheet remains predominantly blank.
Composition: compact, simple central vignette that remains legible when rendered at 160x106 pixels. The paper and brush occupy about 70% of the frame, plenty of clean warm ivory breathing room, delicate contact shadows, low visual density, gently fading perimeter with no hard rectangular border. Designed to sit beside website text that is rendered separately. No text, writing, symbols, logos, watermark, UI controls, people or additional props.

## 生成提示词：候选空状态

Use case: stylized-concept, finished website empty-state art. Create a single landscape 3:2 raster illustration.
Images 1 and 2 are STYLE REFERENCES ONLY. Match the original site's warm ivory textured watercolor paper, muted forest olive green, smoky blue-gray, sepia, fine natural ink details, torn-paper photo-study collage and soft washed edges. Atmospheric handmade cinematic editorial illustration.
Subject: a small carefully arranged collection of three loose image studies waiting to be selected and filed: one soft forest landscape watercolor study, one subtle olive garment study, one mostly blank ivory sheet. They rest together in a shallow open paper portfolio, accompanied by one fine botanical twig. Visual metaphor for reviewing image candidates and preserving a chosen creative asset. No people, no badges or selection checkmarks.
Composition: a simple quiet central vignette occupying about 65% of the canvas, clear silhouette that remains recognizable at 240x160 pixels, ample warm ivory negative space all around, delicate shadows, faded watercolor edges. Natural restrained detail, visually coherent with the references. No writing, labels, letterforms, logo, watermark, UI mockup, buttons, flat vector shapes, bright colors or border around whole image.
