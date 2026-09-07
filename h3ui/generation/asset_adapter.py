"""Mode input adapters expose only paths actually compiled by H3 recipes."""
from dataclasses import dataclass


@dataclass(frozen=True)
class InputAdapter:
    mode: str
    max_images: int
    source_video: bool = False

    def contract(self, recipe):
        return dict(mode=self.mode, recipe=recipe,
                    slots=[dict(kind='image', purposes=['character', 'face', 'costume', 'scene', 'palette', 'prop'],
                                maximum=0 if recipe == 'official_text' else self.max_images,
                                node='MiniMaxH3AudioConditioningT8' if recipe=='wenxi_av' else 'MiniMaxH3ReferenceToVideo', input='ref_images.ref_image_N'),
                           dict(kind='audio', purposes=['voice'], maximum=0 if recipe == 'official_text' else 3,
                                min_seconds=2, max_total_seconds=15, input='ref_audios.ref_audio_N')],
                    source_video=self.source_video, unsupported=['control', 'texture', 'accessory', 'workflow'],
                    reference_switch='text_ref' if recipe == 'official_text' else None,
                    note='目录整理用途不等于输入槽；资料PROMPT和设定不参与生成。')

    def classify(self, entry, selected_media, purpose):
        meta = selected_media['meta']
        if purpose in ('control', 'texture', 'accessory') or 'control' in entry.get('categories', []):
            return dict(state='unsupported', note='可存档导出；当前H3配方没有此用途的独立输入槽')
        if meta['kind'] == 'audio':
            if purpose != 'voice':
                return dict(state='unsupported', note='当前声音输入只参考音色与说话方式，请明确指定声线用途')
            if not 2 <= meta.get('duration', 0) <= 15.05:
                return dict(state='derive', note='请先在资产详情裁出2～15秒的音色参考，原始声音保留')
        elif meta['kind'] == 'image':
            if purpose not in ('character', 'face', 'costume', 'scene', 'palette', 'prop'):
                return dict(state='unsupported', note='请指定可用的图片用途')
        else:
            return dict(state='unsupported', note='视频须作为换人源或先抽帧／提取声音；工作流附件不能作为参考图')
        return dict(state='direct', note='可直接作为参考媒体，执行时准备模型所需副本')


ADAPTERS = {mode: InputAdapter(mode, 1 if mode == 'swap' else 9, mode == 'swap')
            for mode in ('swap', 'image_story', 'text_story')}


def adapter(mode):
    if mode not in ADAPTERS:
        raise ValueError('该创作模式尚未登记资产输入适配器')
    return ADAPTERS[mode]
