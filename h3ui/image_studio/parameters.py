"""Curated, tool-specific UI fields; not a dump of plugin node widgets."""
import copy

PARAMETER_CONTRACT_VERSION = 1


def field(key, label, group, kind='number', **extra):
    return dict(key=key, label=label, group=group, type=kind, **{'scope': 'settings', **extra})


COMMON = [
    field('unet', '底模文件', 'core', 'model', scope='models', help='使用当前工作流的底模加载器；保留完整相对文件名。'),
    field('steps', '采样步数', 'sampling', min=1, max=50, step=1, help='本次图片采样的总步数。'),
    field('cfg', 'CFG', 'sampling', min=1, max=10, step=.1, help='采样器 CFG 引导值；与参考权重、LoRA 强度分别控制。'),
    field('sampler_name', '采样器', 'sampling', 'select', options=['euler', 'heun', 'dpmpp_2m'], help='当前图片工作流公开的采样器。'),
    field('scheduler', '调度器', 'sampling', 'select', options=['simple', 'normal', 'karras'], help='本次图片采样使用的噪声调度。'),
    field('seed', '种子', 'sampling', 'seed', min=0, max=2**53-1, step=1, help='每次随机或固定整数；0 有效。实际种子以对应运行记录为准。'),
    field('ref_boost', '参考权重', 'assets', min=0, max=20, step=.1, help='当前编辑补丁的参考控制权重，不是保真百分比。'),
    field('grounding_px', '图像理解尺寸（px）', 'assets', min=0, max=2048, step=1, advanced=True, help='图文编码阶段的 grounding_px；不是最终输出尺寸，0 原样交给节点处理。'),
    field('fit_mode', '参考适配方式', 'assets', 'select', options=['fit', 'crop (legacy)'], advanced=True, help='编辑补丁的参考适配选项；保留工作流现有语义。'),
    field('lora', 'LoRA 文件', 'lora', 'model', scope='models', help='当前工作流的一个编辑 LoRA 加载位置。'),
    field('strength_model', 'LoRA 强度', 'lora', min=0, max=2, step=.05, help='编辑 LoRA 的模型强度；该工作流没有独立 Bypass 开关。'),
    field('clip', '图文编码器文件', 'advanced', 'model', scope='models', help='当前 CLIPLoader 使用 krea2 类型，不改变加载器。'),
    field('vae', '图片 VAE 文件', 'advanced', 'model', scope='models', help='当前图片工作流编码与解码使用的 VAE。'),
]
AREA = field('megapixels', '处理像素面积（MP）', 'picture', min=.25, max=2, step=.05, quick=True,
             help='按原图比例缩放处理图，也决定最终输出面积；1 MP 按 1024×1024 像素计算，边长按 8 像素对齐。')


def public_parameters():
    """Each tool lists only fields its source branch meaningfully consumes."""
    result = {tool: copy.deepcopy(COMMON) for tool in ('single', 'dual', 'region', 'outpaint')}
    for tool in ('single', 'region'):
        result[tool].append(copy.deepcopy(AREA))
    result['dual'].extend([
        {**copy.deepcopy(AREA), 'label': '输出像素面积（MP）', 'help': '同时控制两张输入的处理面积及按输出比例创建的最终画布；1 MP 按 1024×1024 像素计算。'},
        field('ratio', '输出比例', 'picture', 'select', options=['1:1', '2:3', '3:2', '16:9', '9:16', '4:3', '3:4'], quick=True, help='与输出像素面积共同决定双图结果尺寸，边长按 8 像素对齐。'),
        field('ref_boost_a', '图片 A 参考权重', 'assets', min=0, max=20, step=.1, advanced=True, help='仅双图分支使用的图片 A 独立参考权重。'),
    ])
    result['outpaint'].append(field('output_mp', '输出像素面积（MP）', 'picture', min=.25, max=2, step=.05, quick=True,
                                  help='先将原图处理为固定 1 MP，再扩边；本值控制扩边后用于生成的最终画布面积。'))
    for key, label in (('left', '左侧'), ('right', '右侧'), ('top', '上侧'), ('bottom', '下侧')):
        result['outpaint'].append(field(key, label+'扩展（px）', 'picture', min=0, max=4096, step=1, quick=True,
                                       help='基于固定 1 MP 处理图的扩边像素，与画布精确输入使用同一任务字段。'))
    result['outpaint'].append(field('feathering', '扩边羽化（px）', 'picture', min=0, max=4096, step=1, advanced=True,
                                  help='扩边节点的边缘羽化参数；与局部画笔大小不同。'))
    result['text']=[copy.deepcopy(f) for f in COMMON if f['key'] not in ('ref_boost','grounding_px','fit_mode','lora','strength_model')]
    result['text'].extend([
        {**copy.deepcopy(AREA),'label':'输出像素面积（MP）','help':'与输出比例共同决定文生图画布，边长按8像素对齐；无需底图。'},
        field('ratio','输出比例','picture','select',options=['1:1','2:3','3:2','16:9','9:16','4:3','3:4'],help='与输出像素面积共同决定图片尺寸。'),
    ])
    return result
