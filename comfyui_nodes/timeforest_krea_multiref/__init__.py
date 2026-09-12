"""Optional A–I adapter for comfyui-krea2edit. No model or node auto-install."""
import inspect

SLOTS = tuple('abcdefghi')


def upstream():
    # Resolve at execution, after ComfyUI has loaded all custom node packs.
    import nodes
    cls = nodes.NODE_CLASS_MAPPINGS.get('Krea2EditGroundedEncode')
    module = inspect.getmodule(cls) if cls else None
    if module is None or any(not callable(getattr(module, name, None)) for name in
                             ('_fit_encode_image', '_to_4d', 'krea2_edit_forward')):
        raise RuntimeError('TimeForest 多图编辑需要兼容的 comfyui-krea2edit；请核对配套说明并重启 ComfyUI。')
    return module, cls()


def references(values):
    if any(key not in {'image_' + slot for slot in SLOTS} for key in values):
        raise ValueError('未知参考输入；最多支持图 A—I')
    rows = [(slot, values.get('image_' + slot)) for slot in SLOTS
            if values.get('image_' + slot) is not None]
    if not {'a', 'b'}.issubset({slot for slot, _ in rows}):
        raise ValueError('请选择图片 A 和 B')
    return rows


def ports():
    return {'image_' + slot: ('IMAGE',) for slot in SLOTS}


class TimeForestKreaMultiRefEncode:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'clip': ('CLIP',), 'prompt': ('STRING', {'multiline': True}),
                             'image_a': ('IMAGE',), 'image_b': ('IMAGE',)},
                'optional': {**{k: v for k, v in ports().items() if k not in ('image_a', 'image_b')},
                             'grounding_px': ('INT', {'default': 768, 'min': 0, 'max': 2048}),
                             'system_prompt': ('STRING', {'default': '', 'multiline': True})}}

    RETURN_TYPES = ('CONDITIONING',)
    FUNCTION = 'encode'
    CATEGORY = 'TimeForest/Krea'

    def encode(self, clip, prompt, grounding_px=768, system_prompt='', **images):
        _, encoder = upstream()
        rows = references(images)
        prepared = [encoder._prep(image, grounding_px) for _, image in rows]
        # Keep the upstream chat wrapper; label sparse slots so deleting C does
        # not make the surviving D reference appear to be the third image C.
        template = encoder._template(len(rows), system_prompt)
        vision = '<|vision_start|><|image_pad|><|vision_end|>'
        template = template.replace(vision * len(rows), ''.join(
            'Image ' + slot.upper() + ': ' + vision for slot, _ in rows), 1)
        tokens = clip.tokenize(prompt, images=prepared, llama_template=template)
        return (clip.encode_from_tokens_scheduled(tokens),)


class TimeForestKreaMultiRefPatch:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'model': ('MODEL',), 'vae': ('VAE',), 'target_latent': ('LATENT',),
                             'image_a': ('IMAGE',), 'image_b': ('IMAGE',)},
                'optional': {**{k: v for k, v in ports().items() if k not in ('image_a', 'image_b')},
                             'ref_boost': ('FLOAT', {'default': 4.0, 'min': 0.0, 'max': 20.0}),
                             'ref_boost_a': ('FLOAT', {'default': 1.0, 'min': 0.0, 'max': 20.0}),
                             'fit_mode': (['fit', 'crop (legacy)'], {'default': 'fit'})}}

    RETURN_TYPES = ('MODEL',)
    FUNCTION = 'patch'
    CATEGORY = 'TimeForest/Krea'

    def patch(self, model, vae, target_latent, ref_boost=4.0, ref_boost_a=1.0,
              fit_mode='fit', **images):
        import comfy.patcher_extension
        module, _ = upstream()
        rows = references(images)
        cache = {}
        def prepare(height, width):
            return [model.model.process_latent_in(module._fit_encode_image(
                image, vae, height, width, cache, (slot, height, width), fit_mode))
                for slot, image in rows]
        height, width = target_latent['samples'].shape[-2:]
        primed = prepare(height, width)  # VAE work finishes before sampling.
        def wrapper(executor, x, timesteps, context, *args, **kwargs):
            options = kwargs.get('transformer_options')
            if options is None:
                options = next((value for value in reversed(args) if isinstance(value, dict)), {})
            current = module._to_4d(x).shape[-2:]
            sources = primed if tuple(current) == (height, width) else prepare(*current)
            return module.krea2_edit_forward(executor.class_obj, x, timesteps, context,
                sources, options, ref_boost=ref_boost, ref_boost_a=ref_boost_a,
                ref_native=fit_mode == 'fit', pos_mode='stride1' if fit_mode == 'fit' else 'anchor')
        cloned = model.clone()
        options = cloned.model_options.setdefault('transformer_options', {})
        comfy.patcher_extension.add_wrapper_with_key(
            comfy.patcher_extension.WrappersMP.DIFFUSION_MODEL, 'krea2_edit', wrapper, options)
        return (cloned,)


NODE_CLASS_MAPPINGS = {cls.__name__: cls for cls in
                      (TimeForestKreaMultiRefEncode, TimeForestKreaMultiRefPatch)}
NODE_DISPLAY_NAME_MAPPINGS = {
    'TimeForestKreaMultiRefEncode': 'TimeForest Krea 多图语义编码（A—I）',
    'TimeForestKreaMultiRefPatch': 'TimeForest Krea 多图参考（A—I）',
}
