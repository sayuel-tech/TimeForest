"""Single-character editing policy, based on the official Ref2VA six fields."""
VERSION = 2
SOURCE = 'MiniMax-AI/MiniMax-H3@d21241f0a4b3acbb34c97dae47fa417b7065e438'
FIELDS = {
    'subject_definitions': '<Subject 1> is the replacement performer defined by {PICTURE_LIST}. Use the referenced face, hair, body proportions, outfit, accessories and footwear. Several views within this image depict the same individual.\n<Video 1> is the source video being edited; it establishes the performance timeline, framing, camera movement and environment.',
    'summary': '[video editing + reference generation] The target video is an edited version of <Video 1>. Replace its main performer with <Subject 1> throughout, retaining the source action, camera and setting.',
    'retention_analysis': '<Subject 1> (appears throughout [Shot 1]): fully_preserved - maintain the identity and complete visible appearance from {PICTURE_LIST}.\n<Video 1> (performance and scene structure): partially_preserved - retain action order, timing, position, camera movement and environment while replacing the original performer and wardrobe.',
    'detailed_description': 'The target is a coherent character-replacement edit in the visual setting of the source video.\n[Shot 1] From the opening frame, <Subject 1> occupies the source performer’s position and follows the poses, expressions, gestures, steps and turns of <Video 1> in their original order and timing. Render the referenced face, hairstyle, proportions and complete outfit consistently through changing views. Preserve the source framing, camera path, background, lighting and contact with surrounding objects. Adapt shadows, reflections, hair and fabric motion to the replacement performer. Keep correct occlusion around hands and foreground objects. The character reference supplies appearance, not a starting-frame composition; render one performer rather than the reference sheet’s multiple views. Do not retain the original performer’s identity or costume.',
    'overall_soundscape': 'No generated dialogue or sound; the original audio is restored during final assembly.',
    'non_diegetic_music': 'N/A',
}
